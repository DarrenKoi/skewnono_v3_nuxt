"""Deterministic Phase 1 adapter for storage-page information.

Office counterpart — schema of record: `docs/datatables/storage_ppid.txt`.
Two Redis sources, refreshed by a 04:30 daily collector:

    v3_df_ppid_storage_cdsem   parquet DataFrame, one row per CD-SEM tool
    v3_df_ppid_storage_hvsem   same for HV-SEM
    v3_hitachi_sem_ppid_not_avail   HASH, field = %Y%m%d, value = list of IPs
                                    unreachable that day (both families mixed)

Vocabulary the office data assumes: "ppid" is a synonym for recipe_id, and the
key's `rcp_counts` is the ppid count — the hash above is a separate concern
despite the shared name. A failed capacity collection is a row whose
`storage_mt` and capacity strings are blank while `rcp_counts` still reports.

TWO OFFICE BEHAVIOURS THIS MOCK CANNOT SHOW, both worth knowing before reading
home output as representative:

* the DataFrame's own `fab_name`/`fac_id` are NOT trusted. The collector wrote
  fac-level names ("M16") into the fab column, so the sidebar's fab filter
  ("M16A") matched nothing and every fab except R3 rendered an empty table. The
  office adapter re-keys each row against the live `sem_list` roster by
  `eqp_ip`, falling back to the DF only when the fleet has no match. This mock
  builds its rows from sem_list already, so the bug has no home equivalent.
* the unavailable-IP hash is read via `hgetall` + max(date field), never by
  fetching "today". Fetching today returns empty before the day's collection
  runs, which reads as "nothing was unreachable" — the opposite of unknown.
  Older date fields then give the consecutive-miss streak.
"""

import random
from datetime import date, datetime, timedelta, timezone

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
from back_dev_home.sem_list.providers.mock import get_sem_list


def _format_size_gb(value_gb: float) -> str:
    if value_gb < 1024:
        return f"{int(value_gb)}G"
    return f"{round(value_gb / 1024, 1)}T"


def _iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _generate_rows(tool_slug: ToolSlug, seed: int = 42) -> list[StorageRow]:
    # sem_list is the single source of truth for the equipment fleet; storage is
    # per-tool monitoring data keyed off it. Deriving (rather than re-rolling)
    # eqp_id/eqp_ip/fac_id/fab_name/model keeps every dataset — sem_list, storage,
    # and the ppid-unavailable IP join — consistent for the same physical tools.
    tool_type = SLUG_TO_TOOL_TYPE[tool_slug]
    fleet = [
        tool for tool in get_sem_list()
        if model_to_tool_type(tool["eqp_model_cd"]) == tool_type
    ]

    rng = random.Random(seed)
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    rows: list[StorageRow] = []

    for tool in fleet:
        eqp_id = tool["eqp_id"]
        eqp_ip = tool["eqp_ip"]
        fac_id = tool["fac_id"]
        fab_name = tool["fab_name"]
        model = tool["eqp_model_cd"]

        # Sample timestamp drives both storage_mt and rcp_counts_mt; recipe
        # (ppid) counting is a separate collection path from storage capacity.
        sample_base = now - timedelta(
            days=rng.uniform(0, 7),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
            seconds=rng.randint(0, 59),
            microseconds=rng.randint(0, 999999)
        )

        # Tools cap at 50,000 recipes. Seed a realistic mix so the UI's
        # warning (>49,000) and critical (>49,800) tiers are exercised.
        rcp_roll = rng.random()
        if rcp_roll < 0.08:
            rcp_counts = rng.randint(49_801, 49_990)
        elif rcp_roll < 0.20:
            rcp_counts = rng.randint(49_001, 49_800)
        elif rcp_roll < 0.40:
            rcp_counts = rng.randint(35_000, 49_000)
        else:
            rcp_counts = rng.randint(2_000, 35_000)
        rcp_counts_mt = sample_base + timedelta(
            hours=rng.uniform(-0.5, 0.5),
            microseconds=rng.randint(0, 999999)
        )

        # ~8% of tools fail storage collection: storage_mt is None and the
        # capacity fields are blank, but recipe counts still report.
        if rng.random() < 0.08:
            rows.append(StorageRow(
                eqp_id=eqp_id,
                eqp_ip=eqp_ip,
                fac_id=fac_id,
                total="",
                used="",
                avail="",
                percent="",
                storage_mt=None,
                rcp_counts=rcp_counts,
                rcp_counts_mt=_iso_z(rcp_counts_mt),
                storage_mt_date="",
                fab_name=fab_name,
                eqp_model_cd=model
            ))
            continue

        # Capacity: 70% chance GB (500-999), 30% chance TB (1.0-2.0)
        if rng.random() < 0.7:
            total_gb_value = rng.randint(500, 999)
            total_label = f"{total_gb_value}G"
            total_value = float(total_gb_value)
        else:
            total_tb_value = round(rng.uniform(1.0, 2.0), 1)
            total_label = f"{total_tb_value}T"
            total_value = total_tb_value * 1024

        used_ratio = rng.uniform(0.2, 0.9)
        used_value = total_value * used_ratio
        avail_value = total_value - used_value

        used_label = _format_size_gb(used_value)
        avail_label = _format_size_gb(avail_value)
        percent_label = f"{int(used_ratio * 100)}%"

        rows.append(StorageRow(
            eqp_id=eqp_id,
            eqp_ip=eqp_ip,
            fac_id=fac_id,
            total=total_label,
            used=used_label,
            avail=avail_label,
            percent=percent_label,
            storage_mt=_iso_z(sample_base),
            rcp_counts=rcp_counts,
            rcp_counts_mt=_iso_z(rcp_counts_mt),
            storage_mt_date=sample_base.date().isoformat(),
            fab_name=fab_name,
            eqp_model_cd=model
        ))

    return rows


def get_storage(
    tool_slug: ToolSlug,
    fab_names: list[str] | None = None,
) -> list[StorageRow]:
    rows = _generate_rows(tool_slug)

    if not fab_names:
        return rows

    normalized = {fab_name.strip().upper() for fab_name in fab_names if fab_name.strip()}
    if not normalized:
        return rows

    return [row for row in rows if row["fab_name"].upper() in normalized]


# ---------------------------------------------------------------------------
# PPID not available: tools whose recipe/ppid endpoint could not be reached.
# Office source: Redis hash 'v3_hitachi_sem_ppid_not_avail',
#   hget(key, "%Y%m%d") -> not_avail_ip_list (list[str] of eqp_ip), kept 30 days.
# Only IPs are stored, so each IP is joined against sem_list to enrich. An IP
# with no sem_list match is DROPPED, matching the office adapter — such an IP is
# leftover cruft in the company system DB, not a roster gap worth surfacing
# (user-confirmed 2026-08-10).
# ---------------------------------------------------------------------------


MOCK_PPID_LATEST_DATE = date(2026, 5, 26)
MOCK_PPID_WINDOW_DAYS = 30


def _ymd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _generate_ppid_snapshots(tool_slug: ToolSlug, seed: int = 43) -> dict[str, list[str]]:
    """Redis-shaped mock: {"YYYYMMDD": [eqp_ip, ...]} for the last 30 days."""
    rng = random.Random(seed)
    tool_type = SLUG_TO_TOOL_TYPE[tool_slug]
    sem_rows = [
        row for row in get_sem_list()
        if model_to_tool_type(row["eqp_model_cd"]) == tool_type
    ]

    latest = MOCK_PPID_LATEST_DATE
    snapshots: dict[str, list[str]] = {
        _ymd(latest - timedelta(days=offset)): []
        for offset in range(MOCK_PPID_WINDOW_DAYS)
    }

    if sem_rows:
        failing = rng.sample(sem_rows, max(1, int(len(sem_rows) * 0.4)))
    else:
        failing = []
    n_current = len(failing) // 2

    # Currently unreachable: a streak ending at the latest date.
    for row in failing[:n_current]:
        streak = rng.randint(1, MOCK_PPID_WINDOW_DAYS)
        for offset in range(streak):
            snapshots[_ymd(latest - timedelta(days=offset))].append(row["eqp_ip"])

    # Failed earlier in the window then recovered (absent from the latest date).
    for row in failing[n_current:]:
        start = rng.randint(1, MOCK_PPID_WINDOW_DAYS - 1)
        duration = rng.randint(1, min(4, MOCK_PPID_WINDOW_DAYS - start))
        for offset in range(start, start + duration):
            snapshots[_ymd(latest - timedelta(days=offset))].append(row["eqp_ip"])

    # 로스터에 없는 IP(고아)는 만들지 않습니다. user-confirmed 2026-08-10:
    # 사무실에서 그런 IP 는 신호가 아니라 사내 시스템 DB 에 남은 찌꺼기이고,
    # office 어댑터도 sem_list 매칭이 없으면 행을 버립니다. 예전에는 여기서
    # 일부러 3개를 만들어 eqp_id="" 행으로 내보냈기 때문에, 집에서만 존재하는
    # "로스터 공백 신호" 를 화면이 다루게 돼 있었습니다.

    return snapshots


def _ppid_streak(eqp_ip: str, latest_date: date, ip_by_date: dict[str, set[str]]) -> int:
    streak = 0
    cursor = latest_date
    while eqp_ip in ip_by_date.get(_ymd(cursor), set()):
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def get_ppid_unavailable(
    tool_slug: ToolSlug,
    fab_names: list[str] | None = None,
) -> PpidUnavailableSnapshot:
    snapshots = _generate_ppid_snapshots(tool_slug)
    latest_key = max(snapshots)  # compact YYYYMMDD sorts chronologically
    latest_date = datetime.strptime(latest_key, "%Y%m%d").date()

    ip_by_date = {key: set(ips) for key, ips in snapshots.items()}
    sem_by_ip = {row["eqp_ip"]: row for row in get_sem_list()}

    normalized = {
        fab_name.strip().upper()
        for fab_name in (fab_names or [])
        if fab_name.strip()
    }

    rows: list[PpidUnavailableRow] = []
    for eqp_ip in snapshots[latest_key]:
        match = sem_by_ip.get(eqp_ip)
        fac_id = match["fac_id"] if match else ""
        fab_name = match["fab_name"] if match else ""
        eqp_id = match["eqp_id"] if match else ""
        eqp_model_cd = match["eqp_model_cd"] if match else ""

        # No sem_list match -> drop, like the office adapter. 위 스냅샷
        # 생성기가 고아를 만들지 않으므로 평소에는 걸리지 않지만, 로스터가
        # 줄어들면(장비 폐기) 여기가 두 provider 를 같은 답으로 유지합니다.
        if match is None:
            continue
        if normalized and fab_name.upper() not in normalized:
            continue

        rows.append(PpidUnavailableRow(
            eqp_id=eqp_id,
            eqp_ip=eqp_ip,
            fac_id=fac_id,
            fab_name=fab_name,
            eqp_model_cd=eqp_model_cd,
            missing_days_streak=_ppid_streak(eqp_ip, latest_date, ip_by_date),
        ))

    rows.sort(key=lambda row: (-row["missing_days_streak"], row["eqp_ip"]))

    return {
        "latest_date": latest_date.isoformat(),
        "rows": rows,
    }
