"""Shared Redis plumbing for office adapters (Phase 2/3).

Every office adapter needs the same three pieces of plumbing, which used to
live as drifting copies in each ``providers/office_example.py``:

* :func:`load_env_file` — lazy ``back_dev_home/.env`` loading so a standalone
  run (``python -m ... .providers.office``) works without the Flask factory.
* :func:`redis_client` — one cached, fail-fast Redis client per process.
* :func:`read_dataframe` — parquet-first DataFrame deserialization with a
  diagnostic error instead of a bare unpickle traceback.

Feature-specific normalization (text coercion, column mapping, contract
shaping) stays in each adapter — only the plumbing is shared.
"""

import os
import pickle
import sys
from functools import lru_cache
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry


def load_env_file(required_var: str = "REDIS_HOST") -> None:
    """Load ``back_dev_home/.env`` for standalone / bare-import runs.

    The Flask app factory and conftest.py already load it; this is the
    fallback when an adapter module is imported directly (script,
    ``python -m``, notebook). Try the repo-root-relative path first (honors
    "run from the repo root"), then the .env sitting next to the
    ``back_dev_home`` package — the latter works no matter the current
    working directory. ``override=False`` (the default) keeps any value
    already set by Flask/pytest. ``required_var`` is the env var whose
    presence proves the first attempt succeeded (REDIS_HOST for Redis-only
    adapters, OPENSEARCH_HOST for OpenSearch ones).
    """
    from dotenv import load_dotenv

    load_dotenv("back_dev_home/.env")
    if os.environ.get(required_var):
        return
    pkg = sys.modules.get("back_dev_home")  # already imported by any adapter
    pkg_file = getattr(pkg, "__file__", None)
    if pkg_file:
        load_dotenv(Path(pkg_file).with_name(".env"))


@lru_cache(maxsize=1)
def redis_client() -> redis.Redis:
    """One Redis client (and connection pool) per process, fail-fast.

    Cached so requests reuse the pool instead of opening a fresh TCP
    connection each time; redis-py re-establishes dropped pool connections
    per command, so reuse is safe across backend restarts. The RuntimeError
    below is not cached (lru_cache does not cache exceptions), so a
    misconfigured first call can recover once the env is fixed.
    """
    host = os.environ.get("REDIS_HOST")
    if not host:
        load_env_file("REDIS_HOST")
        host = os.environ.get("REDIS_HOST")
    if not host:
        raise RuntimeError(
            "REDIS_HOST is not set. Run from the repo root so back_dev_home/.env "
            "is found, or set REDIS_HOST/REDIS_PORT/REDIS_PASSWORD in the "
            "environment before calling this adapter."
        )
    return redis.Redis(
        host=host,
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD"),
        # Values are serialized DataFrames (binary), so keep raw bytes.
        decode_responses=False,
        # Fail fast on a wrong host/port: 5s connect timeout, one retry.
        # (redis-py 8 defaults to 3 retries with backoff — a bad config
        # would otherwise hang ~60s before erroring.)
        socket_connect_timeout=5,
        socket_timeout=10,
        retry=Retry(NoBackoff(), retries=1),
    )


def _looks_like_json(raw: bytes) -> bool:
    return raw.lstrip()[:1] in (b"{", b"[")


def read_dataframe(raw: bytes, key: str) -> pd.DataFrame:
    """Deserialize a DataFrame stored under ``key``.

    The office writes DataFrames as **parquet** (``df.to_parquet()``), read
    back via the pyarrow engine; JSON and pickle branches are fallbacks for
    other keys/writers. All failures raise bare :class:`LookupError` —
    upstream data problem — which the app factory maps to a JSON 502.
    """
    # Parquet: magic bytes b"PAR1" at the head (and tail). Parquet stores
    # text columns as UTF-8, so strings come back as Python str already.
    if raw[:4] == b"PAR1":
        return pd.read_parquet(BytesIO(raw), engine="pyarrow")

    # JSON: only when it actually looks like JSON. Do NOT fall back to
    # raw.decode('utf-8') on arbitrary binary — that turns a real unpickling
    # failure into a misleading UnicodeDecodeError and hides the true cause.
    if _looks_like_json(raw):
        return pd.read_json(StringIO(raw.decode("utf-8")))

    try:
        obj = pickle.loads(raw)
    except Exception as exc:
        raise LookupError(
            f"Could not deserialize Redis key {key!r} "
            f"(first bytes: {raw[:16].hex(' ')!r}, length {len(raw)}). "
            f"Real error -> {type(exc).__name__}: {exc}. "
            "If this is a numpy/pandas version mismatch (e.g. "
            "\"No module named 'numpy._core'\" means the writer used numpy>=2 "
            "but this venv has numpy<2 — upgrade numpy), align versions. "
            "If the value is compressed (gzip 1f8b / zlib 789c / zstd 28b52ffd) "
            "add that branch before pickle.loads."
        ) from exc

    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, dict):  # e.g. df.to_dict() pickled
        return pd.DataFrame(obj)
    raise LookupError(
        f"Redis key {key!r} deserialized to {type(obj).__name__}, "
        "expected a DataFrame or dict"
    )
