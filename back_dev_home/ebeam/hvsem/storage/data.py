import random
from datetime import date, datetime, timedelta, timezone
from typing import TypedDict


class StorageRow(TypedDict):
    eqp_id: str
    eqp_ip: str
    fac_id: str
    total: str
    used: str
    avail: str
    percent: str
    storage_mt: str
    rcp_counts: int
    rcp_counts_mt: str
    storage_mt_date: str
    fab_name: str
    eqp_model_cd: str


FAC_IDS = ["M10", "M11", "M14", "M15", "M16", "R3"]
FAB_SUFFIXES = ["A", "B", "C"]

# HV-SEM scope: only AMAT TP-series. PROVISION_* and VERITYSEM_* are
# their own tool families (deferred to 2027 per the project roadmap)
# and Hitachi CG* is CD-SEM — none belong on this endpoint per
# classifyToolType() in useSemListApi.ts.
EQP_MODELS = ["TP3000", "TP3500", "TP4000", "TP4500"]
EQP_PREFIXES = ["PCD", "MCD", "ACD", "VCD"]

IP_PREFIXES = ["177", "197"]


def _format_size_gb(value_gb: float) -> str:
    if value_gb < 1024:
        return f"{int(value_gb)}G"
    return f"{round(value_gb / 1024, 1)}T"


def _iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _generate_rows(n_rows: int = 300, seed: int = 42) -> list[StorageRow]:
    rng = random.Random(seed)
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    rows: list[StorageRow] = []

    for _ in range(n_rows):
        fac_id = rng.choice(FAC_IDS)
        if fac_id == "R3" and rng.random() < 0.3:
            fab_name = "R4"
        else:
            fab_name = fac_id + rng.choice(FAB_SUFFIXES)

        model = rng.choice(EQP_MODELS)
        eqp_prefix = rng.choice(EQP_PREFIXES)

        eqp_id = f"{eqp_prefix}{rng.randint(100, 999)}"

        ip_prefix = rng.choice(IP_PREFIXES)
        eqp_ip = f"{ip_prefix}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"

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

        days_ago = rng.uniform(0, 7)
        storage_mt = now - timedelta(
            days=days_ago,
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
        rcp_counts_mt = storage_mt + timedelta(
            hours=rng.uniform(-0.5, 0.5),
            microseconds=rng.randint(0, 999999)
        )

        rows.append(StorageRow(
            eqp_id=eqp_id,
            eqp_ip=eqp_ip,
            fac_id=fac_id,
            total=total_label,
            used=used_label,
            avail=avail_label,
            percent=percent_label,
            storage_mt=_iso_z(storage_mt),
            rcp_counts=rcp_counts,
            rcp_counts_mt=_iso_z(rcp_counts_mt),
            storage_mt_date=storage_mt.date().isoformat(),
            fab_name=fab_name,
            eqp_model_cd=model
        ))

    return rows


def get_storage(fac_ids: list[str] | None = None) -> list[StorageRow]:
    rows = _generate_rows()

    if not fac_ids:
        return rows

    normalized = {fac_id.strip().upper() for fac_id in fac_ids if fac_id.strip()}
    if not normalized:
        return rows

    return [row for row in rows if row["fac_id"] in normalized]


# ---------------------------------------------------------------------------
# Storage Unreachable: daily snapshots of tools missing from storage inventory.
# The source shape mirrors Phase 2 data: {"YYYY-MM-DD": dataframe-like rows}.
# ---------------------------------------------------------------------------


class UnavailableSnapshotRow(TypedDict):
    eqp_id: str
    eqp_ip: str
    fac_id: str
    fab_name: str
    eqp_model_cd: str


class UnavailableRow(UnavailableSnapshotRow):
    missing_days_streak: int


class StorageUnavailableSnapshot(TypedDict):
    latest_date: str
    rows: list[UnavailableRow]


MOCK_UNAVAILABLE_LATEST_DATE = date(2026, 5, 26)
MOCK_UNAVAILABLE_DAYS = 8


def _generate_unavailable_tool_pool(
    n_tools: int,
    rng: random.Random
) -> list[UnavailableSnapshotRow]:
    rows: list[UnavailableSnapshotRow] = []

    for idx in range(n_tools):
        fac_id = rng.choice(FAC_IDS)
        if fac_id == "R3" and rng.random() < 0.3:
            fab_name = "R4"
        else:
            fab_name = fac_id + rng.choice(FAB_SUFFIXES)

        eqp_prefix = rng.choice(EQP_PREFIXES)
        ip_prefix = rng.choice(IP_PREFIXES)

        rows.append(UnavailableSnapshotRow(
            eqp_id=f"{eqp_prefix}{5000 + idx}",
            eqp_ip=f"{ip_prefix}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}",
            fac_id=fac_id,
            fab_name=fab_name,
            eqp_model_cd=rng.choice(EQP_MODELS),
        ))

    return rows


def _generate_unavailable_snapshots(
    n_tools: int = 84,
    n_latest_rows: int = 60,
    seed: int = 43
) -> dict[str, list[UnavailableSnapshotRow]]:
    rng = random.Random(seed)
    tools = _generate_unavailable_tool_pool(n_tools, rng)
    latest_date = MOCK_UNAVAILABLE_LATEST_DATE
    snapshot_dates = [
        latest_date - timedelta(days=offset)
        for offset in range(MOCK_UNAVAILABLE_DAYS - 1, -1, -1)
    ]
    snapshots: dict[str, list[UnavailableSnapshotRow]] = {
        snapshot_date.isoformat(): []
        for snapshot_date in snapshot_dates
    }

    latest_tools = tools[:n_latest_rows]
    historical_tools = tools[n_latest_rows:]

    for tool in latest_tools:
        streak_length = rng.randint(1, MOCK_UNAVAILABLE_DAYS)
        for offset in range(streak_length):
            snapshot_key = (latest_date - timedelta(days=offset)).isoformat()
            snapshots[snapshot_key].append(tool)

    for tool in historical_tools:
        last_missing_offset = rng.randint(1, MOCK_UNAVAILABLE_DAYS - 1)
        duration = rng.randint(1, min(3, MOCK_UNAVAILABLE_DAYS - last_missing_offset))
        for offset in range(last_missing_offset, last_missing_offset + duration):
            snapshot_key = (latest_date - timedelta(days=offset)).isoformat()
            snapshots[snapshot_key].append(tool)

    for snapshot_key, rows in snapshots.items():
        snapshots[snapshot_key] = sorted(rows, key=lambda row: row["eqp_id"])

    return snapshots


def _missing_days_streak(
    eqp_id: str,
    latest_date: date,
    eqp_ids_by_date: dict[str, set[str]]
) -> int:
    streak = 0
    cursor = latest_date

    while eqp_id in eqp_ids_by_date.get(cursor.isoformat(), set()):
        streak += 1
        cursor -= timedelta(days=1)

    return streak


def get_storage_unavailable(
    fac_ids: list[str] | None = None
) -> StorageUnavailableSnapshot:
    snapshots = _generate_unavailable_snapshots()
    latest_key = max(snapshots)
    latest_date = date.fromisoformat(latest_key)
    normalized = {
        fac_id.strip().upper()
        for fac_id in (fac_ids or [])
        if fac_id.strip()
    }
    eqp_ids_by_date = {
        snapshot_key: {row["eqp_id"] for row in rows}
        for snapshot_key, rows in snapshots.items()
    }
    rows: list[UnavailableRow] = []

    for row in snapshots[latest_key]:
        if normalized and row["fac_id"] not in normalized:
            continue

        rows.append(UnavailableRow(
            **row,
            missing_days_streak=_missing_days_streak(
                row["eqp_id"],
                latest_date,
                eqp_ids_by_date
            ),
        ))

    rows.sort(key=lambda row: (-row["missing_days_streak"], row["eqp_id"]))

    return {
        "latest_date": latest_key,
        "rows": rows,
    }
