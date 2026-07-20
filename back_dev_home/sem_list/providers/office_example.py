# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 adapter for the office SEM equipment source (Redis).

The office Redis stores the SEM fleet under the key ``v3_sem_list`` as a
serialized ``pandas.DataFrame``. This adapter fetches the raw bytes,
deserializes them (pickle first, JSON fallback), and normalizes every row
to ``SemListRow``; callers and routes must not need to know the source
format.

Connection settings come from ``REDIS_HOST`` / ``REDIS_PORT`` /
``REDIS_PASSWORD`` in ``back_dev_home/.env`` (same vars the health feature
uses). At the office: fill in .env, `cp office_example.py office.py`, set
``SKEWNONO_SEM_LIST_PROVIDER=office``, then run the Verify command in
MIGRATION.md.
"""

import os
import pickle
from io import StringIO

import pandas as pd
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from back_dev_home.sem_list.contracts import SemListRow

_REDIS_KEY = "v3_sem_list"

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


def _deserialize_dataframe(raw: bytes) -> pd.DataFrame:
    """Accept the common ways a DataFrame lands in Redis.

    Adjust at the office once the actual serialization is confirmed —
    delete the branches that don't apply.
    """
    try:
        obj = pickle.loads(raw)
    except Exception:
        # Not pickle — assume a JSON payload (df.to_json() or df.to_dict()).
        return pd.read_json(StringIO(raw.decode("utf-8")))

    if isinstance(obj, pd.DataFrame):
        return obj
    if isinstance(obj, dict):  # e.g. df.to_dict() pickled
        return pd.DataFrame(obj)
    raise TypeError(
        f"Redis key {_REDIS_KEY!r} unpickled to {type(obj).__name__}, "
        "expected a DataFrame or dict"
    )


def _as_iso_string(value) -> str:
    if hasattr(value, "isoformat"):  # pandas Timestamp / datetime
        return value.isoformat()
    return str(value)


def _normalize(df: pd.DataFrame) -> list[SemListRow]:
    missing = _REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Redis key {_REDIS_KEY!r} DataFrame is missing columns: "
            f"{sorted(missing)} (got {sorted(df.columns)})"
        )

    rows: list[SemListRow] = []
    for rec in df.to_dict(orient="records"):
        vendor = str(rec["vendor_nm"]).strip().upper()
        if vendor not in _VALID_VENDORS:
            raise ValueError(
                f"Unexpected vendor_nm {rec['vendor_nm']!r} for eqp_id "
                f"{rec['eqp_id']!r}; contract allows {sorted(_VALID_VENDORS)}"
            )
        available = _AVAILABLE_MAP.get(str(rec["available"]).strip().lower())
        if available is None:
            raise ValueError(
                f"Unexpected available {rec['available']!r} for eqp_id "
                f"{rec['eqp_id']!r}; contract allows On/Off"
            )
        rows.append(
            SemListRow(
                fac_id=str(rec["fac_id"]),
                eqp_id=str(rec["eqp_id"]),
                eqp_model_cd=str(rec["eqp_model_cd"]),
                eqp_grp_id=str(rec["eqp_grp_id"]),
                vendor_nm=vendor,
                eqp_ip=str(rec["eqp_ip"]),
                fab_name=str(rec["fab_name"]),
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
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    fleet = get_sem_list()
    print(f"{len(fleet)} rows from Redis key {_REDIS_KEY!r}")
    if fleet:
        print("first row:", fleet[0])
