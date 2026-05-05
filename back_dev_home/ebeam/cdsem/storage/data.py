import random
from datetime import datetime, timedelta, timezone
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

# CD-SEM scope: only Hitachi CG-series models. The AMAT inventory in
# this mock dataset is HV-SEM (TP*), VeritySEM, or Provision — none of
# which are CD-SEM per classifyToolType() in useSemListApi.ts — so it
# is excluded from this endpoint.
EQP_MODELS = ["CG6300", "CG6320", "CG6340", "CG6360", "CG6380"]
EQP_PREFIXES = ["ECXDX", "ECDX", "HCDX"]

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
        rcp_counts = rng.randint(50, 500)
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
# Storage Unreachable: tools whose storage info we tried to extract but failed.
# Distinct eqp_id range (5000-5999) so they never collide with inventory rows.
# ---------------------------------------------------------------------------


class UnavailableRow(TypedDict):
    eqp_id: str
    eqp_ip: str
    fac_id: str
    fab_name: str
    eqp_model_cd: str
    reason: str         # "unreachable" | "stale" | "never_reported" | "auth_failed"
    error_code: str     # ETIMEDOUT | E_STALE_DATA | E_NO_BASELINE | EAUTH
    last_attempt: str   # ISO Z, always recent (the sweep ran)
    last_success: str   # ISO Z, or "" when never reported


REASON_TO_ERROR = {
    "unreachable": "ETIMEDOUT",
    "stale": "E_STALE_DATA",
    "never_reported": "E_NO_BASELINE",
    "auth_failed": "EAUTH",
}

# Weights mirror what's plausible in the field: most failures are network blips
# and authentication drift; a smaller tail is true never-reported newcomers.
REASON_WEIGHTS = [
    ("unreachable", 0.42),
    ("stale", 0.28),
    ("auth_failed", 0.18),
    ("never_reported", 0.12),
]


def _weighted_reason(rng: random.Random) -> str:
    pick = rng.random()
    cumulative = 0.0
    for reason, weight in REASON_WEIGHTS:
        cumulative += weight
        if pick <= cumulative:
            return reason
    return REASON_WEIGHTS[-1][0]


def _last_success_for(reason: str, last_attempt: datetime, rng: random.Random) -> str:
    if reason == "never_reported":
        return ""
    if reason == "unreachable":
        delta = timedelta(days=rng.uniform(1, 3), hours=rng.randint(0, 23))
    elif reason == "stale":
        delta = timedelta(days=rng.uniform(7, 30), hours=rng.randint(0, 23))
    else:  # auth_failed
        delta = timedelta(days=rng.uniform(5, 14), hours=rng.randint(0, 23))
    return _iso_z(last_attempt - delta)


def _generate_unavailable_rows(n_rows: int = 60, seed: int = 43) -> list[UnavailableRow]:
    rng = random.Random(seed)
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    rows: list[UnavailableRow] = []

    for idx in range(n_rows):
        fac_id = rng.choice(FAC_IDS)
        if fac_id == "R3" and rng.random() < 0.3:
            fab_name = "R4"
        else:
            fab_name = fac_id + rng.choice(FAB_SUFFIXES)

        model = rng.choice(EQP_MODELS)
        eqp_prefix = rng.choice(EQP_PREFIXES)

        # Distinct numeric range from inventory generator (which uses 100-999).
        eqp_id = f"{eqp_prefix}{5000 + idx}"

        ip_prefix = rng.choice(IP_PREFIXES)
        eqp_ip = f"{ip_prefix}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"

        reason = _weighted_reason(rng)

        # last_attempt is always within the last hour — the sweep just ran.
        last_attempt_dt = now - timedelta(
            minutes=rng.randint(1, 59),
            seconds=rng.randint(0, 59),
        )

        rows.append(UnavailableRow(
            eqp_id=eqp_id,
            eqp_ip=eqp_ip,
            fac_id=fac_id,
            fab_name=fab_name,
            eqp_model_cd=model,
            reason=reason,
            error_code=REASON_TO_ERROR[reason],
            last_attempt=_iso_z(last_attempt_dt),
            last_success=_last_success_for(reason, last_attempt_dt, rng),
        ))

    return rows


def get_storage_unavailable(fac_ids: list[str] | None = None) -> list[UnavailableRow]:
    rows = _generate_unavailable_rows()

    if not fac_ids:
        return rows

    normalized = {fac_id.strip().upper() for fac_id in fac_ids if fac_id.strip()}
    if not normalized:
        return rows

    return [row for row in rows if row["fac_id"] in normalized]
