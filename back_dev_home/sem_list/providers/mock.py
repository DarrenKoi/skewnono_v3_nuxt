"""Deterministic Phase 1 adapter for the SEM equipment list."""

import random
from datetime import datetime, timedelta, timezone
from typing import Literal

from back_dev_home.sem_list.contracts import SemListRow


FAC_IDS = ["M11", "M12", "M14", "M15", "M16", "R3"]
FAB_SUFFIXES = ["A", "B", "C"]

# Fleet identity is keyed on the TOOL FAMILY, not the vendor. Both families in
# scope today are Hitachi: CD-SEM is the CG/GT-series, HV-SEM is the TP-series.
# AMAT enters only as VeritySEM/Provision, which are their own tool types
# (`classifyToolType` in useSemListApi.ts) rather than HV-SEM, and are deferred
# to 2027. Models and eqp_id prefixes mirror TOOL_SPECS in _tool_specs.py.
CDSEM_MODELS = ["CG6300", "CG6320", "CG6340", "CG6360", "CG6380", "GT2000", "GT2000S"]
CDSEM_EQP_PREFIXES = ["ECXDX", "ECDX", "HCDX"]

HVSEM_MODELS = ["TP3000", "TP3500", "TP4000", "TP4500"]
HVSEM_EQP_PREFIXES = ["PCD", "MCD", "ACD", "VCD"]

# Deferred-to-2027 AMAT tools. They belong in the inventory but are NOT CD/HV-SEM,
# so `model_to_tool_type()` returns None and every tool-scoped view filters them
# out. Kept rare for exactly that reason — at the old ~50% they crowded the
# CD/HV-SEM pages down to half a fleet. The prefix pool is unverified; nothing
# classifies by prefix (it only builds eqp_ids), so it is cosmetic.
AMAT_MODELS = ["PROVISION_10", "PROVISION_20", "VERITYSEM_4", "VERITYSEM_5"]
AMAT_EQP_PREFIXES = ["PCD", "MCD", "ACD", "VCD"]

# Fleet mix. AMAT stays small; the rest splits CD-SEM / HV-SEM roughly 7:3.
AMAT_SHARE = 0.10
CDSEM_SHARE = 0.62

EQP_GRP_PREFIXES = ["G-ECD-", "G-MCD-", "G-KCD-", "G-MDS-", "G-PCD-", "G-ACD-"]


def _generate_rows(n_rows: int = 300, seed: int = 42) -> list[SemListRow]:
    rng = random.Random(seed)
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    rows: list[SemListRow] = []

    for _ in range(n_rows):
        fac_id = rng.choice(FAC_IDS)
        if fac_id == "R3":
            # R-class fabs are only R3 and R4 (no A/B/C suffix).
            fab_name = "R4" if rng.random() < 0.3 else "R3"
        else:
            fab_name = f"{fac_id}{rng.choice(FAB_SUFFIXES)}"

        # Pick the tool family first, then DERIVE the vendor from it — a TP
        # tool is Hitachi because of what it is, not by an independent coin
        # flip. Choosing vendor first is what previously stamped every HV-SEM
        # tool as AMAT.
        roll = rng.random()
        if roll < AMAT_SHARE:
            models, prefixes = AMAT_MODELS, AMAT_EQP_PREFIXES
        elif roll < AMAT_SHARE + CDSEM_SHARE:
            models, prefixes = CDSEM_MODELS, CDSEM_EQP_PREFIXES
        else:
            models, prefixes = HVSEM_MODELS, HVSEM_EQP_PREFIXES

        model = rng.choice(models)
        eqp_prefix = rng.choice(prefixes)
        vendor_nm: Literal["HITACHI", "AMAT"] = (
            "AMAT" if models is AMAT_MODELS else "HITACHI"
        )

        eqp_id = f"{eqp_prefix}{rng.randint(100, 999)}"
        eqp_grp_id = f"{rng.choice(EQP_GRP_PREFIXES)}{rng.randint(1, 3):02d}"

        ip_prefix = "177" if rng.random() < 0.5 else "197"
        eqp_ip = f"{ip_prefix}.{rng.randint(1, 254)}.{rng.randint(1, 254)}.{rng.randint(1, 254)}"
        updt_dt = (
            now - timedelta(days=rng.randint(0, 90))
        ).isoformat().replace("+00:00", "Z")
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
            # Free-form version string (digit + letter), e.g. "1A" — matches
            # the office shape. Occasionally "" to mirror fleet rows that have
            # no matching entry in the office version store.
            version="" if rng.random() < 0.05 else f"{rng.randint(1, 3)}{rng.choice('AB')}"
        ))

    return rows


def get_sem_list() -> list[SemListRow]:
    return _generate_rows()
