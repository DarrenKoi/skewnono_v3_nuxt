# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 adapter for the office SEM equipment source (Redis).

The office Redis stores the SEM fleet across three keys, each a
``pandas.DataFrame`` serialized to **parquet** (``df.to_parquet()``):

* ``v3_df_sem_list``    — the FULL company roster — every tool, all tool types.
* ``v3_df_sem_avail``    — the fleet skewnono can actually reach: a DERIVED
  subset of the roster, WITHOUT a ``version`` column.
* ``v3_df_sem_version`` — columns ``[eqp_ip, version]``; ``version`` is a
  free-form string (digits + letters, e.g. ``"1A"``).

``get_sem_list()`` fetches ``v3_df_sem_avail`` and ``v3_df_sem_version``,
LEFT-merges the version onto the fleet by ``eqp_ip`` (keeping every fleet row
exactly once — rows with no matching version get ``""``), and normalizes to
``SemListRow``. ``get_pending_tools()`` diffs ``v3_df_sem_list`` against
``v3_df_sem_avail`` on ``eqp_id`` to surface the roster tools skewnono cannot
reach yet, normalized to ``PendingToolRow``. Callers and routes must not need
to know the source format.

Connection settings come from ``REDIS_HOST`` / ``REDIS_PORT`` /
``REDIS_PASSWORD`` in ``back_dev_home/.env`` (same vars the health feature
uses). At the office: fill in .env, then `cp office_example.py office.py` — that
file's existence is the switch, no env var needed — and run the Verify
command in MIGRATION.md.
"""

import pandas as pd
import redis

from back_dev_home._runtime.office_redis import (
    read_dataframe as _deserialize_dataframe,
    redis_client as _redis_client,
)
from back_dev_home.sem_list.contracts import PendingToolRow, SemListRow

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


def _text_or_blank(value) -> str:
    """Cell as stripped text; "" when missing, never the string "nan".

    A parquet-backed DataFrame stores an unassigned cell as NaN/None, and
    `_to_text` would otherwise stringify it to the literal "nan" — invisible
    at home, where the mock can only ever emit "". This also covers the
    `_normalize` LEFT-merge case: a fleet row with no matching version row
    carries NaN, which must become an empty string too.
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
                version=_text_or_blank(rec["version"]),
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


_ROSTER_KEY = "v3_df_sem_list"

# No `available` and no `version`: both live in keys a pending tool is not in.
_PENDING_REQUIRED_COLUMNS = frozenset(
    {
        "fac_id",
        "eqp_id",
        "eqp_model_cd",
        "eqp_grp_id",
        "vendor_nm",
        "eqp_ip",
        "fab_name",
        "updt_dt",
    }
)


def _iso_or_blank(value) -> str:
    """updt_dt as ISO text; "" when missing (NaN/None/NaT).

    A separate wrapper rather than teaching `_as_iso_string` this guard,
    because `_as_iso_string` is also used by `_normalize` (the `get_sem_list`
    path), which is out of scope here and must not change behavior.
    """
    if pd.isna(value):
        return ""
    return _as_iso_string(value)


def _normalize_pending(df: pd.DataFrame) -> list[PendingToolRow]:
    """Shape roster rows into the contract.

    Note what this does NOT do, unlike `_normalize`: it does not validate
    `vendor_nm` against a known set, and it does not map `available`. A tool
    we have not onboarded may legitimately carry a vendor we have never seen,
    and rejecting it would empty the one screen meant to reveal it.

    Every field goes through `_text_or_blank` / `_iso_or_blank` so a missing
    office cell becomes "" rather than the literal string "nan" — most
    importantly `fab_name` (bucketed as 미배정 by the UI) and `eqp_ip` (the
    firewall-request deliverable, where a fake "nan" value must never appear).
    """
    return [
        PendingToolRow(
            fac_id=_text_or_blank(rec["fac_id"]),
            eqp_id=_text_or_blank(rec["eqp_id"]),
            eqp_model_cd=_text_or_blank(rec["eqp_model_cd"]),
            eqp_grp_id=_text_or_blank(rec["eqp_grp_id"]),
            vendor_nm=_text_or_blank(rec["vendor_nm"]).upper(),
            eqp_ip=_text_or_blank(rec["eqp_ip"]),
            fab_name=_text_or_blank(rec["fab_name"]),
            updt_dt=_iso_or_blank(rec["updt_dt"]),
        )
        for rec in df.to_dict(orient="records")
    ]


def _select_pending(
    roster: pd.DataFrame, connected: pd.DataFrame
) -> list[PendingToolRow]:
    """Roster minus reachable, diffed on ``eqp_id``.

    ``eqp_id`` and not ``eqp_ip``: the id is the tool's name and every roster
    row has one, whereas an ip can be reassigned. Kept separate from
    :func:`get_pending_tools` so it is testable without a Redis.
    """
    missing = _PENDING_REQUIRED_COLUMNS - set(roster.columns)
    if missing:
        raise ValueError(
            f"Redis key {_ROSTER_KEY!r} DataFrame is missing columns: "
            f"{sorted(missing)} (got {sorted(roster.columns)})"
        )
    # No separate eqp_id guard for the roster: _PENDING_REQUIRED_COLUMNS
    # already contains it, so the check above has covered it.
    if "eqp_id" not in connected.columns:
        raise ValueError(
            f"Redis key {_REDIS_KEY!r} has no 'eqp_id' column to diff against "
            f"(got {sorted(connected.columns)})."
        )

    if roster.empty:
        return []
    pending = roster[~roster["eqp_id"].isin(set(connected["eqp_id"]))]
    if pending.empty:
        return []
    return _normalize_pending(pending)


def get_pending_tools() -> list[PendingToolRow]:
    client = _redis_client()
    roster = _load_dataframe(client, _ROSTER_KEY)
    connected = _load_dataframe(client, _REDIS_KEY)
    return _select_pending(roster, connected)


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.sem_list.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    # _redis_client loads back_dev_home/.env itself if the env isn't set.
    fleet = get_sem_list()
    print(f"{len(fleet)} rows from Redis key {_REDIS_KEY!r}")
    if fleet:
        print("first row:", fleet[0])
