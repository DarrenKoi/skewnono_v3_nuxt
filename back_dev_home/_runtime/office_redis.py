"""Shared Redis plumbing for office adapters (Phase 2/3).

Every office adapter needs the same pieces of plumbing, which used to live as
drifting copies in each ``providers/office_example.py``:

* :func:`load_env_file` — lazy ``back_dev_home/.env`` loading so a standalone
  run (``python -m ... .providers.office``) works without the Flask factory.
* :func:`redis_client` — one cached, fail-fast Redis client per process.
* :func:`redis_client_or_none` — the same client, but "not configured" as a
  return value instead of an exception, for adapters that must degrade rather
  than fail.
* :data:`STORE_ERRORS` — the exception tuple meaning "the store is unusable
  right now".
* :func:`redis_text` — decode one value out of the byte-mode client.
* :func:`read_dataframe` — parquet-first DataFrame deserialization with a
  diagnostic error instead of a bare unpickle traceback.

Feature-specific normalization (column mapping, contract shaping, pandas-cell
coercion) stays in each adapter — only the plumbing is shared. Note the
distinction: :func:`redis_text` decodes a *Redis* value and is plumbing, while
e.g. ``storage``'s ``_text`` normalizes a *DataFrame cell* (NaN, Timestamp) and
is not.
"""

from __future__ import annotations

import os
import pickle
import sys
from functools import lru_cache
from io import BytesIO, StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

if TYPE_CHECKING:  # pandas is imported inside read_dataframe, not at module scope
    import pandas as pd


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


def redis_client_or_none() -> redis.Redis | None:
    """:func:`redis_client`, but unconfigured is ``None`` rather than a raise.

    For adapters that must degrade instead of failing — a decorative feature
    whose route has no error path, where a raise would break every page that
    calls it. Those adapters would otherwise have to ``except RuntimeError``
    around the client lookup, which couples them to the least specific
    exception type in the language and silently swallows unrelated bugs.

    Adapters that *should* fail loudly on missing config — anything enforcing
    policy — call :func:`redis_client` directly and let the app factory map the
    RuntimeError to a 503.
    """
    try:
        return redis_client()
    except RuntimeError:
        return None


# "The store is unusable right now." OSError covers socket-level failures
# redis-py lets through unwrapped. Defined here, next to the client that raises
# them, rather than per-adapter, so every adapter draws the outage boundary in
# the same place.
#
# This tuple is deliberately BROADER than what the app factory maps to a 503.
# The factory registers handlers for redis ConnectionError and TimeoutError
# only; a ResponseError (WRONGTYPE, bad arity) or a bare OSError matches
# neither, falls through to InternalServerError, and answers 500 — JSON, but
# saying "we have a bug" rather than "infrastructure is down, retry". Widening
# the factory instead would be wrong: ResponseError, DataError and WatchError
# usually ARE bugs, and the factory's own comment says subclasses of the adapter
# signal types "must stay real 500s".
#
# So the conversion belongs at the adapter, which is the only layer that knows
# a given call was reaching for the store. Catch STORE_ERRORS and re-raise via
# `unreachable()`. See tests/test_app_error_handlers.py for the full table.
STORE_ERRORS = (redis.exceptions.RedisError, OSError)


def unreachable(detail: str, exc: BaseException) -> RuntimeError:
    """Build the bare RuntimeError the app factory maps to a JSON 503.

    Use as ``raise unreachable("...", exc) from exc`` when a store call failed
    for an infrastructure reason. Returns rather than raises so the ``raise``
    stays visible at the call site.

    Must be EXACTLY ``RuntimeError``: ``back_dev_home/__init__.py`` checks
    ``type(err) is not RuntimeError`` and sends subclasses to a 500, on the
    grounds that a subclass is a programming bug rather than an adapter signal.
    Constructing it here is what guarantees no adapter accidentally sends a
    subclass and silently gets a 500 where it documented a 503.

    The driver's own type and message are folded into the text because the
    factory surfaces ``str(err)`` to the client, and "which redis error" is the
    first thing an operator wants from a 503.
    """
    return RuntimeError(f"{detail}: {type(exc).__name__}: {exc}")


def redis_text(value) -> str:
    """Decode one value from the byte-mode client.

    :func:`redis_client` is built with ``decode_responses=False`` because its
    original payloads were parquet DataFrames, so every hash field, set member
    and string comes back as ``bytes``. Adapters storing text rather than
    DataFrames need this on every read.
    """
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


def _looks_like_json(raw: bytes) -> bool:
    return raw.lstrip()[:1] in (b"{", b"[")


def _undeserializable(
    raw: bytes, key: str, exc: Exception, codec: str
) -> LookupError:
    """The one diagnostic every failed decode raises.

    Bare ``LookupError``, never a subclass: ``back_dev_home/__init__.py`` maps
    it to a JSON 502 with ``type(err) is not LookupError``, so a subclass would
    fall through to an opaque 500.

    The pickle wording is reproduced verbatim from when this was inlined in
    that branch — the hints are the ones that actually come up off a bad Redis
    value — and the codec is named only for the other decoders, so the pickle
    message stays byte-identical.
    """
    message = (
        f"Could not deserialize Redis key {key!r} "
        f"(first bytes: {raw[:16].hex(' ')!r}, length {len(raw)}). "
        f"Real error -> {type(exc).__name__}: {exc}. "
        "If this is a numpy/pandas version mismatch (e.g. "
        "\"No module named 'numpy._core'\" means the writer used numpy>=2 "
        "but this venv has numpy<2 — upgrade numpy), align versions. "
        "If the value is compressed (gzip 1f8b / zlib 789c / zstd 28b52ffd) "
        "add that branch before pickle.loads."
    )
    if codec != "pickle":
        message += (
            f" The value was routed to the {codec} decoder by its leading "
            "bytes, so a truncated or partially-written value fails here "
            "rather than reaching pickle."
        )
    return LookupError(message)


def read_dataframe(raw: bytes, key: str) -> pd.DataFrame:
    """Deserialize a DataFrame stored under ``key``.

    The office writes DataFrames as **parquet** (``df.to_parquet()``), read
    back via the pyarrow engine; JSON and pickle branches are fallbacks for
    other keys/writers. All failures raise bare :class:`LookupError` —
    upstream data problem — which the app factory maps to a JSON 502.

    pandas is imported here rather than at module scope so that adapters using
    only the Redis helpers do not pay a ~200-400ms pandas/pyarrow import to
    call :func:`redis_client`.
    """
    import pandas as pd

    # Parquet: magic bytes b"PAR1" at the head (and tail). Parquet stores
    # text columns as UTF-8, so strings come back as Python str already.
    #
    # Guarded like the pickle branch below: a truncated or partially-written
    # value still starts with PAR1, and pyarrow raises ArrowInvalid, which is
    # neither LookupError nor RuntimeError. The app factory matches those two
    # types exactly (see back_dev_home/__init__.py), so an unguarded raise here
    # escaped as an opaque 500 rather than the 502 this docstring promises.
    if raw[:4] == b"PAR1":
        try:
            return pd.read_parquet(BytesIO(raw), engine="pyarrow")
        except Exception as exc:
            raise _undeserializable(raw, key, exc, "parquet") from exc

    # JSON: only when it actually looks like JSON. Do NOT fall back to
    # raw.decode('utf-8') on arbitrary binary — that turns a real unpickling
    # failure into a misleading UnicodeDecodeError and hides the true cause.
    if _looks_like_json(raw):
        try:
            return pd.read_json(StringIO(raw.decode("utf-8")))
        except Exception as exc:
            raise _undeserializable(raw, key, exc, "JSON") from exc

    try:
        obj = pickle.loads(raw)
    except Exception as exc:
        raise _undeserializable(raw, key, exc, "pickle") from exc

    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, dict):  # e.g. df.to_dict() pickled
        return pd.DataFrame(obj)
    raise LookupError(
        f"Redis key {key!r} deserialized to {type(obj).__name__}, "
        "expected a DataFrame or dict"
    )
