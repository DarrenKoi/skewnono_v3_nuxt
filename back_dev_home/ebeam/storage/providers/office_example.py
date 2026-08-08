# TEMPLATE — copy to office.py at the office, then run. office.py is
# gitignored (back_dev_home/**/providers/office.py); this office_example.py
# is the tracked skeleton and the source of truth — edit it at home.
"""Phase 2/3 adapter for office storage sources (Redis).

Two data sources, both in the office Redis:

* ``get_storage`` — a per-tool parquet ``pandas.DataFrame`` under
  ``v3_df_ppid_storage_cdsem`` / ``v3_df_ppid_storage_hvsem``. Columns match
  the ``StorageRow`` contract; a failed capacity collection is a row whose
  ``storage_mt`` (and capacity strings) are null/blank while ``rcp_counts``
  still reports. ("ppid" in the key name = recipe/ppid *count* data, i.e.
  ``rcp_counts`` — not the unavailability below.) The DataFrame's own
  ``fab_name``/``fac_id`` columns are NOT trusted: the collection pipeline
  wrote fac-level names (``M16``), so the sidebar's fab_name filter
  (``M16A``) matched nothing and every fab except R3 rendered an empty
  스토리지 table. Each row is re-keyed against the live ``sem_list`` (the
  fleet source of truth) by ``eqp_ip``, falling back to the DF's values
  only when the fleet has no match.
* ``get_ppid_unavailable`` — a Redis **hash** ``v3_hitachi_sem_ppid_not_avail``
  whose field is a compact date (``%Y%m%d``) and whose value is the list of
  equipment IPs that were unreachable that day (CD-SEM and HV-SEM combined).
  Each IP is joined against the live ``sem_list`` to recover its equipment
  info and tool type, so the combined hash can be split per requested tool.

Connection settings come from ``REDIS_HOST`` / ``REDIS_PORT`` /
``REDIS_PASSWORD`` in ``back_dev_home/.env`` (same vars as sem_list/health).
At the office: ``cp office_example.py office.py``, then enable with
``SKEWNONO_STORAGE_PROVIDER=office`` and run the Verify command in MIGRATION.md.
"""

import ast
import json
from datetime import datetime, timedelta

import pandas as pd
import redis

from back_dev_home._runtime.office_redis import (
    read_dataframe as _deserialize_dataframe,
    redis_client as _redis_client,
)
from back_dev_home.ebeam._tool_specs import (
    SLUG_TO_TOOL_TYPE,
    ToolSlug,
    model_to_tool_type,
)
from back_dev_home.ebeam.storage.contracts import (
    PpidUnavailableRow,
    PpidUnavailableSnapshot,
    StorageRow,
)
from back_dev_home.sem_list.data import get_sem_list

_STORAGE_KEY: dict[str, str] = {
    "cdsem": "v3_df_ppid_storage_cdsem",
    "hvsem": "v3_df_ppid_storage_hvsem",
}
_PPID_HASH = "v3_hitachi_sem_ppid_not_avail"

_STORAGE_COLUMNS = (
    "eqp_id", "eqp_ip", "fac_id", "total", "used", "avail", "percent",
    "storage_mt", "rcp_counts", "rcp_counts_mt", "storage_mt_date",
    "fab_name", "eqp_model_cd",
)


# --------------------------------------------------------------------------
# Redis + deserialization
# --------------------------------------------------------------------------
def _is_missing(value) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _text(value) -> str:
    """Cell -> str; "" for null/NaN, ISO for timestamps, UTF-8 for bytes."""
    if _is_missing(value):
        return ""
    if hasattr(value, "isoformat"):  # pandas Timestamp / datetime
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8")
    return str(value)


def _opt_iso(value) -> str | None:
    """storage_mt: ISO string, or None when the capacity collection failed."""
    if _is_missing(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return _text(value).strip() or None


def _int(value, default: int = 0) -> int:
    if _is_missing(value):
        return default
    return int(float(value))


# --------------------------------------------------------------------------
# GET /api/<slug>/storage
# --------------------------------------------------------------------------
def _fleet_by_ip() -> dict[str, dict]:
    """sem_list rows keyed by eqp_ip — the same join get_ppid_unavailable uses."""
    fleet: dict[str, dict] = {}
    for row in get_sem_list():
        ip = str(row.get("eqp_ip", "")).strip()
        if ip:
            fleet.setdefault(ip, row)
    return fleet


def _normalize_storage(
    df: pd.DataFrame, key: str, fab_names: list[str] | None
) -> list[StorageRow]:
    missing = set(_STORAGE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"Redis key {key!r} DataFrame is missing columns: {sorted(missing)} "
            f"(got {sorted(df.columns)})"
        )

    fleet_by_ip = _fleet_by_ip()
    wanted = {f.strip().upper() for f in (fab_names or []) if f.strip()}
    rows: list[StorageRow] = []
    for rec in df.to_dict(orient="records"):
        fac_id = _text(rec["fac_id"])
        fab_name = _text(rec["fab_name"])
        # The storage pipeline's fab_name is fac-level; sem_list carries the
        # sidebar-grade fab_name (M16A vs M16), so the fleet match wins.
        match = fleet_by_ip.get(_text(rec["eqp_ip"]).strip())
        if match is not None:
            fab_name = str(match.get("fab_name") or "").strip() or fab_name
            fac_id = str(match.get("fac_id") or "").strip() or fac_id
        if wanted and fab_name.strip().upper() not in wanted:
            continue
        rows.append(StorageRow(
            eqp_id=_text(rec["eqp_id"]),
            eqp_ip=_text(rec["eqp_ip"]),
            fac_id=fac_id,
            total=_text(rec["total"]),
            used=_text(rec["used"]),
            avail=_text(rec["avail"]),
            percent=_text(rec["percent"]),
            storage_mt=_opt_iso(rec["storage_mt"]),
            rcp_counts=_int(rec["rcp_counts"]),
            rcp_counts_mt=_text(rec["rcp_counts_mt"]),
            storage_mt_date=_text(rec["storage_mt_date"]),
            fab_name=fab_name,
            eqp_model_cd=_text(rec["eqp_model_cd"]),
        ))
    return rows


def get_storage(
    tool_slug: ToolSlug,
    fab_names: list[str] | None = None,
) -> list[StorageRow]:
    key = _STORAGE_KEY.get(tool_slug)
    if key is None:
        raise ValueError(
            f"Unknown tool_slug {tool_slug!r}; expected one of {sorted(_STORAGE_KEY)}"
        )
    raw = _redis_client().get(key)
    if raw is None:
        raise LookupError(
            f"Redis key {key!r} not found — check REDIS_HOST/REDIS_PORT/"
            "REDIS_PASSWORD in back_dev_home/.env and that the storage job has "
            "populated the key."
        )
    df = _deserialize_dataframe(raw, key)
    if df.empty:
        return []
    return _normalize_storage(df, key, fab_names)


# --------------------------------------------------------------------------
# GET /api/<slug>/ppid-unavailable
# --------------------------------------------------------------------------
def _parse_ip_list(value) -> list[str]:
    """Hash value -> list of IP strings, tolerant of JSON / repr / CSV."""
    if isinstance(value, (bytes, bytearray)):
        value = bytes(value).decode("utf-8")
    value = str(value).strip()
    if not value:
        return []
    for parse in (json.loads, ast.literal_eval):
        try:
            parsed = parse(value)
        except (ValueError, SyntaxError):
            continue
        if isinstance(parsed, (list, tuple)):
            return [str(ip).strip() for ip in parsed if str(ip).strip()]
    return [ip.strip() for ip in value.split(",") if ip.strip()]


def _load_ppid_snapshots(client: redis.Redis) -> dict[str, list[str]]:
    """Redis hash -> {"YYYYMMDD": [eqp_ip, ...]} (CD-SEM + HV-SEM combined)."""
    raw = client.hgetall(_PPID_HASH)
    snapshots: dict[str, list[str]] = {}
    for field, value in raw.items():
        day = field.decode() if isinstance(field, (bytes, bytearray)) else str(field)
        snapshots[day] = _parse_ip_list(value)
    return snapshots


def _streak(eqp_ip: str, latest_key: str, ip_by_date: dict[str, set[str]]) -> int:
    """Consecutive days the IP stays present, counting back from latest_key."""
    streak = 0
    cursor = datetime.strptime(latest_key, "%Y%m%d")
    while eqp_ip in ip_by_date.get(cursor.strftime("%Y%m%d"), set()):
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def get_ppid_unavailable(
    tool_slug: ToolSlug,
    fab_names: list[str] | None = None,
) -> PpidUnavailableSnapshot:
    tool_type = SLUG_TO_TOOL_TYPE.get(tool_slug)
    if tool_type is None:
        raise ValueError(
            f"Unknown tool_slug {tool_slug!r}; expected one of "
            f"{sorted(SLUG_TO_TOOL_TYPE)}"
        )

    snapshots = _load_ppid_snapshots(_redis_client())
    if not snapshots:
        return {"latest_date": "", "rows": []}

    latest_key = max(snapshots)  # compact YYYYMMDD sorts chronologically
    latest_date = datetime.strptime(latest_key, "%Y%m%d").date()
    ip_by_date = {key: set(ips) for key, ips in snapshots.items()}

    sem_by_ip = {row["eqp_ip"]: row for row in get_sem_list()}
    wanted = {f.strip().upper() for f in (fab_names or []) if f.strip()}

    rows: list[PpidUnavailableRow] = []
    for eqp_ip in dict.fromkeys(snapshots[latest_key]):  # de-dup, keep order
        match = sem_by_ip.get(eqp_ip)
        # The hash is combined CD/HV; only rows resolving to THIS tool belong
        # here. An IP with no sem_list match can't be attributed to a tool, so
        # it is not shown under either tab.
        if match is None or model_to_tool_type(match["eqp_model_cd"]) != tool_type:
            continue
        fac_id = str(match["fac_id"])
        fab_name = str(match["fab_name"])
        if wanted and fab_name.strip().upper() not in wanted:
            continue
        rows.append(PpidUnavailableRow(
            eqp_id=str(match["eqp_id"]),
            eqp_ip=eqp_ip,
            fac_id=fac_id,
            fab_name=fab_name,
            eqp_model_cd=str(match["eqp_model_cd"]),
            missing_days_streak=_streak(eqp_ip, latest_key, ip_by_date),
        ))

    rows.sort(key=lambda row: (-row["missing_days_streak"], row["eqp_ip"]))
    return {"latest_date": latest_date.isoformat(), "rows": rows}


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.ebeam.storage.providers.office
    # (_redis_client loads back_dev_home/.env itself if the env isn't set.)
    from collections import Counter

    for _slug in ("cdsem", "hvsem"):
        _storage = get_storage(_slug)
        _ppid = get_ppid_unavailable(_slug)
        print(
            f"{_slug}: {len(_storage)} storage rows | "
            f"ppid latest_date={_ppid['latest_date']!r}, "
            f"{len(_ppid['rows'])} unavailable"
        )
        # Per-fab distribution — every sidebar fab should appear here, not
        # just R3. A fac-level name (e.g. plain "M16") means a row whose IP
        # is missing from sem_list kept the pipeline's raw label.
        print(f"  fabs: {dict(Counter(_row['fab_name'] for _row in _storage))}")
        if _storage:
            print("  storage[0]:", _storage[0])
        if _ppid["rows"]:
            print("  ppid[0]:", _ppid["rows"][0])
