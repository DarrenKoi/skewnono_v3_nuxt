# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 adapter for the office SEM equipment source (Redis).

The office Redis stores the SEM fleet under the key ``v3_df_sem_list`` as a
``pandas.DataFrame`` serialized to **parquet** (``df.to_parquet()``). This
adapter fetches the raw bytes, deserializes them (parquet via pyarrow, with
JSON/pickle fallbacks), and normalizes every row to ``SemListRow``; callers
and routes must not need to know the source format.

Connection settings come from ``REDIS_HOST`` / ``REDIS_PORT`` /
``REDIS_PASSWORD`` in ``back_dev_home/.env`` (same vars the health feature
uses). At the office: fill in .env, `cp office_example.py office.py`, set
``SKEWNONO_SEM_LIST_PROVIDER=office``, then run the Verify command in
MIGRATION.md.
"""

import os
import pickle
from io import BytesIO, StringIO

import pandas as pd
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from back_dev_home.sem_list.contracts import SemListRow

_REDIS_KEY = "v3_df_sem_list"

_REQUIRED_COLUMNS = frozenset(
    {
        "fac_id",
        "eqp_id",
        "eqp_model_cd",
        "eqp_grp_id",
        "vendor_nm",
        "eqp_ip",
        "fab_name",
        "updt_dt",
        "available",
        "version",
    }
)

_VALID_VENDORS = {"HITACHI", "AMAT"}
_AVAILABLE_MAP = {"on": "On", "off": "Off", "true": "On", "false": "Off", "1": "On", "0": "Off"}


def _redis_client() -> redis.Redis:
    host = os.environ.get("REDIS_HOST")
    if not host:
        raise RuntimeError(
            "REDIS_HOST is not set. back_dev_home/.env is only loaded by the "
            "Flask app factory (and tests via conftest.py) — for standalone "
            "runs use `python -m back_dev_home.sem_list.providers.office` "
            "from the repo root, or call "
            "load_dotenv('back_dev_home/.env') before importing this module."
        )
    return redis.Redis(
        host=host,
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD"),
        # The value is a serialized DataFrame (binary), so keep raw bytes.
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


def _deserialize_dataframe(raw: bytes) -> pd.DataFrame:
    """Deserialize the DataFrame stored under ``v3_df_sem_list``.

    The office writes the fleet as **parquet** (``df.to_parquet()``), read
    back here via the pyarrow engine. The JSON and pickle branches are kept
    as fallbacks for other keys/writers; delete them if you never need them.
    """
    # Parquet: magic bytes b"PAR1" at the head (and tail). This is the
    # confirmed office format. Parquet stores text columns as UTF-8, so the
    # strings come back as Python str already.
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
        raise RuntimeError(
            f"Could not unpickle Redis key {_REDIS_KEY!r} "
            f"(first bytes: {raw[:16].hex(' ')!r}, length {len(raw)}). "
            f"Real error -> {type(exc).__name__}: {exc}. "
            "If this is a numpy/pandas version mismatch (e.g. "
            "\"No module named 'numpy._core'\" means the writer used numpy>=2 "
            "but this venv has numpy<2 — upgrade numpy), align versions. "
            "If the value is compressed (gzip 1f8b / zlib 789c / zstd 28b52ffd) "
            "or parquet (PAR1), add that branch before pickle.loads."
        ) from exc

    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, dict):  # e.g. df.to_dict() pickled
        return pd.DataFrame(obj)
    raise TypeError(
        f"Redis key {_REDIS_KEY!r} unpickled to {type(obj).__name__}, "
        "expected a DataFrame or dict"
    )


def _to_text(value) -> str:
    """Coerce a cell to str, decoding raw bytes as UTF-8.

    Parquet returns text as str, but a bytes/binary column would otherwise
    stringify to "b'...'"; decode it as UTF-8 so Korean and other non-ASCII
    values survive intact.
    """
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8")
    return str(value)


def _as_iso_string(value) -> str:
    if hasattr(value, "isoformat"):  # pandas Timestamp / datetime
        return value.isoformat()
    return _to_text(value)


def _normalize(df: pd.DataFrame) -> list[SemListRow]:
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Redis key {_REDIS_KEY!r} DataFrame is missing columns: "
            f"{sorted(missing)} (got {sorted(df.columns)})"
        )

    rows: list[SemListRow] = []
    for rec in df.to_dict(orient="records"):
        vendor = _to_text(rec["vendor_nm"]).strip().upper()
        if vendor not in _VALID_VENDORS:
            raise ValueError(
                f"Unexpected vendor_nm {rec['vendor_nm']!r} for eqp_id "
                f"{rec['eqp_id']!r}; contract allows {sorted(_VALID_VENDORS)}"
            )
        available = _AVAILABLE_MAP.get(_to_text(rec["available"]).strip().lower())
        if available is None:
            raise ValueError(
                f"Unexpected available {rec['available']!r} for eqp_id "
                f"{rec['eqp_id']!r}; contract allows On/Off"
            )
        rows.append(
            SemListRow(
                fac_id=_to_text(rec["fac_id"]),
                eqp_id=_to_text(rec["eqp_id"]),
                eqp_model_cd=_to_text(rec["eqp_model_cd"]),
                eqp_grp_id=_to_text(rec["eqp_grp_id"]),
                vendor_nm=vendor,
                eqp_ip=_to_text(rec["eqp_ip"]),
                fab_name=_to_text(rec["fab_name"]),
                updt_dt=_as_iso_string(rec["updt_dt"]),
                available=available,
                version=int(rec["version"]),
            )
        )
    return rows


def get_sem_list() -> list[SemListRow]:
    raw = _redis_client().get(_REDIS_KEY)
    if raw is None:
        raise LookupError(
            f"Redis key {_REDIS_KEY!r} not found — check REDIS_HOST/REDIS_PORT/"
            "REDIS_PASSWORD in back_dev_home/.env and that the fleet job has "
            "populated the key."
        )
    df = _deserialize_dataframe(raw)
    if df.empty:
        return []
    return _normalize(df)


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.sem_list.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    # The `-m` form already requires cwd == repo root, so load .env with a
    # plain cwd-relative path instead of anything derived from __file__.
    from dotenv import load_dotenv

    load_dotenv("back_dev_home/.env")
    fleet = get_sem_list()
    print(f"{len(fleet)} rows from Redis key {_REDIS_KEY!r}")
    if fleet:
        print("first row:", fleet[0])
