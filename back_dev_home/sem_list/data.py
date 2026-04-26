import random
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict


class SemListRow(TypedDict):
    fac_id: str
    eqp_id: str
    eqp_model_cd: str
    eqp_grp_id: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    eqp_ip: str
    fab_name: str
    updt_dt: str
    available: Literal["On", "Off"]
    version: int


FAC_IDS = ["M11", "M12", "M14", "M15", "M16", "R3"]
FAB_SUFFIXES = ["A", "B", "C"]

HITACHI_MODELS = ["CG6300", "CG6320", "CG6340", "CG6360", "CG6380", "GT2000", "GT2000S"]
AMAT_MODELS = [
    "TP3000", "TP3500", "TP4000", "TP4500",
    "PROVISION_10", "PROVISION_20",
    "VERITYSEM_4", "VERITYSEM_5"
]

HITACHI_EQP_PREFIXES = ["ECXDX", "ECDX", "HCDX"]
AMAT_EQP_PREFIXES = ["PCD", "MCD", "ACD", "VCD"]

EQP_GRP_PREFIXES = ["G-ECD-", "G-MCD-", "G-KCD-", "G-MDS-", "G-PCD-", "G-ACD-"]


def _generate_rows(n_rows: int = 300, seed: int = 42) -> list[SemListRow]:
    rng = random.Random(seed)
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    rows: list[SemListRow] = []

    for _ in range(n_rows):
        fac_id = rng.choice(FAC_IDS)
        if fac_id == "R3":
            # R-class fabs are only R3 and R4 (no A/B/C suffix); split roughly 70/30 within the R fac.
            fab_name = "R4" if rng.random() < 0.3 else "R3"
        else:
            fab_name = f"{fac_id}{rng.choice(FAB_SUFFIXES)}"

        vendor_nm: Literal["HITACHI", "AMAT"] = "HITACHI" if rng.random() < 0.5 else "AMAT"

        if vendor_nm == "HITACHI":
            model = rng.choice(HITACHI_MODELS)
            eqp_prefix = rng.choice(HITACHI_EQP_PREFIXES)
        else:
            model = rng.choice(AMAT_MODELS)
            eqp_prefix = rng.choice(AMAT_EQP_PREFIXES)

        eqp_id = f"{eqp_prefix}{rng.randint(100, 999)}"
        eqp_grp_id = f"{rng.choice(EQP_GRP_PREFIXES)}{rng.randint(1, 3):02d}"

        ip_prefix = "177" if rng.random() < 0.5 else "197"
        eqp_ip = f"{ip_prefix}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"

        updt_dt = (now - timedelta(days=rng.randint(0, 90))).isoformat().replace("+00:00", "Z")

        available: Literal["On", "Off"] = "On" if rng.random() < 0.9 else "Off"

        rows.append(SemListRow(
            fac_id=fac_id,
            eqp_id=eqp_id,
            eqp_model_cd=model,
            eqp_grp_id=eqp_grp_id,
            vendor_nm=vendor_nm,
            eqp_ip=eqp_ip,
            fab_name=fab_name,
            updt_dt=updt_dt,
            available=available,
            version=rng.randint(1, 3)
        ))

    return rows


def get_sem_list() -> list[SemListRow]:
    return _generate_rows()
