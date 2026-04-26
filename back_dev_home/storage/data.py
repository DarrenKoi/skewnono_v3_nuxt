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

HITACHI_MODELS = ["CG6300", "CG6320", "CG6340", "CG6360", "CG6380"]
AMAT_MODELS = [
    "TP3000", "TP3500", "TP4000", "TP4500",
    "PROVISION_10", "PROVISION_20",
    "VERITYSEM_4", "VERITYSEM_5"
]

HITACHI_EQP_PREFIXES = ["ECXDX", "ECDX", "HCDX"]
AMAT_EQP_PREFIXES = ["PCD", "MCD", "ACD", "VCD"]

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

        vendor = "HITACHI" if rng.random() < 0.5 else "AMAT"
        if vendor == "HITACHI":
            model = rng.choice(HITACHI_MODELS)
            eqp_prefix = rng.choice(HITACHI_EQP_PREFIXES)
        else:
            model = rng.choice(AMAT_MODELS)
            eqp_prefix = rng.choice(AMAT_EQP_PREFIXES)

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
