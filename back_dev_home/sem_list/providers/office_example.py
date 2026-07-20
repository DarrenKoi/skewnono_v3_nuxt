# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 adapter for the office SEM equipment source (Redis).

The office Redis stores the SEM fleet across two keys, each a
``pandas.DataFrame`` serialized to **parquet** (``df.to_parquet()``):

* ``v3_df_sem_avail``    — the fleet, WITHOUT a ``version`` column.
* ``v3_df_sem_version`` — columns ``[eqp_ip, version]``; ``version`` is a
  free-form string (digits + letters, e.g. ``"1A"``).

This adapter fetches both, LEFT-merges the version onto the fleet by
``eqp_ip`` (keeping every fleet row exactly once — rows with no matching
version get ``""``), and normalizes to ``SemListRow``; callers and routes
must not need to know the source format.

Connection settings come from ``REDIS_HOST`` / ``REDIS_PORT`` /
``REDIS_PASSWORD`` in ``back_dev_home/.env`` (same vars the health feature
uses). At the office: fill in .env, `cp office_example.py office.py`, set
``SKEWNONO_SEM_LIST_PROVIDER=office``, then run the Verify command in
MIGRATION.md.
"""

import os
import pickle
import sys
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from back_dev_home.sem_list.contracts import SemListRow

_REDIS_KEY = "v3_df_sem_avail"
_VERSION_KEY = "v3_df_sem_version"
_MERGE_KEY = "eqp_ip"

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


def _load_env_file() -> None:
    """Load back_dev_home/.env for standalone / bare-import runs.

    The Flask app factory and conftest.py already load it; this is the fallback
    when the module is imported directly (script, ``python -c``, notebook).
    Try the repo-root-relative path first (honors "run from the repo root"),
    then the .env sitting next to the ``back_dev_home`` package — the latter
    works no matter the current working directory. ``override=False`` (the
    default) keeps any value already set by Flask/pytest.
    """
    from dotenv import load_dotenv

    load_dotenv("back_dev_home/.env")
    if os.environ.get("REDIS_HOST"):
        return
    pkg = sys.modules.get("back_dev_home")  # already imported by this module
    pkg_file = getattr(pkg, "__file__", None)
    if pkg_file:
        load_dotenv(Path(pkg_file).with_name(".env"))


def _redis_client() -> redis.Redis:
    host = os.environ.get("REDIS_HOST")
    if not host:
        _load_env_file()
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


def _deserialize_dataframe(raw: bytes, key: str) -> pd.DataFrame:
    """Deserialize a DataFrame stored under ``key``.

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
            f"Could not unpickle Redis key {key!r} "
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
        f"Redis key {key!r} unpickled to {type(obj).__name__}, "
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


def _version_str(value) -> str:
    """Version as a string; "" when missing.

    After the LEFT merge, fleet rows with no matching version row carry NaN
    (pandas' missing-value marker), which must become an empty string.
    """
    if pd.isna(value):
        return ""
    return _to_text(value).strip()


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
                version=_version_str(rec["version"]),
            )
        )
    return rows


def _load_dataframe(client: redis.Redis, key: str) -> pd.DataFrame:
    raw = client.get(key)
    if raw is None:
        raise LookupError(
            f"Redis key {key!r} not found — check REDIS_HOST/REDIS_PORT/"
            "REDIS_PASSWORD in back_dev_home/.env and that the fleet job has "
            "populated the key."
        )
    return _deserialize_dataframe(raw, key)


def _attach_version(fleet: pd.DataFrame, versions: pd.DataFrame) -> pd.DataFrame:
    """LEFT-merge the version string onto the fleet by ``eqp_ip``.

    ``how="left"`` with the fleet on the left keeps every fleet row and never
    drops one. To also stop a fleet row from being *duplicated* when the
    version table has more than one row for the same ``eqp_ip``, collapse the
    version table to one row per ``eqp_ip`` first (keep the last).
    """
    if "version" in fleet.columns:
        return fleet  # already present — nothing to merge
    if _MERGE_KEY not in fleet.columns:
        raise ValueError(
            f"Cannot attach version: {_REDIS_KEY!r} has no {_MERGE_KEY!r} "
            f"column to merge on (got {sorted(fleet.columns)})."
        )
    if not {_MERGE_KEY, "version"} <= set(versions.columns):
        raise ValueError(
            f"{_VERSION_KEY!r} must have columns [{_MERGE_KEY!r}, 'version'], "
            f"got {sorted(versions.columns)}."
        )
    right = versions[[_MERGE_KEY, "version"]].drop_duplicates(
        subset=[_MERGE_KEY], keep="last"
    )
    return fleet.merge(right, on=_MERGE_KEY, how="left")


def get_sem_list() -> list[SemListRow]:
    client = _redis_client()
    fleet = _load_dataframe(client, _REDIS_KEY)
    versions = _load_dataframe(client, _VERSION_KEY)
    fleet = _attach_version(fleet, versions)
    if fleet.empty:
        return []
    return _normalize(fleet)


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.sem_list.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    # _redis_client loads back_dev_home/.env itself if the env isn't set.
    fleet = get_sem_list()
    print(f"{len(fleet)} rows from Redis key {_REDIS_KEY!r}")
    if fleet:
        print("first row:", fleet[0])
