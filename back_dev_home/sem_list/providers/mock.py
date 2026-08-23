"""Deterministic Phase 1 adapter for the SEM equipment list.

Office counterpart — schema of record: `docs/datatables/hitachi/sem_list.txt`.
THREE Redis keys, each a pandas DataFrame serialized to parquet:

    v3_df_sem_list      the FULL company roster — every tool, all tool types
    v3_df_sem_avail     the subset skewnono can actually reach
    v3_df_sem_version   columns [eqp_ip, version]

`v3_df_sem_avail` is a derived subset, not the roster (user-confirmed
2026-07-30). Every tool is assigned an `eqp_ip` when it is installed in the
fab and is FIREWALLED from that moment; it only enters `v3_df_sem_avail`
once IT opens that IP. So `v3_df_sem_list - v3_df_sem_avail` is exactly the
queue of firewall-exception requests, and "in the roster but unreachable" is
the normal initial state of every tool rather than an error.

`v3_df_sem_list` carries the same 8 identity columns as `v3_df_sem_avail`
minus `available` — fac_id, eqp_id, eqp_model_cd, eqp_grp_id, vendor_nm,
eqp_ip, fab_name, updt_dt (user-confirmed 2026-07-30). Not yet proven by a
real run, so `office_example._select_pending` still raises with the missing
column names if that turns out wrong — a diagnosable error beats an empty
screen. `PendingToolRow` mirrors exactly these 8: no `available` and no
`version`, because a pending tool is in neither of those keys.

`v3_df_sem_list` is a CURRENT SNAPSHOT of what is physically installed and on
the fab network right now (user-confirmed 2026-07-30), not an accumulating
history. There is no decommissioned or abandoned row sitting in it, so every
row in `v3_df_sem_list - v3_df_sem_avail` is actionable regardless of how
long ago it arrived — arrival age carries no signal about whether a firewall
request is still needed. `get_pending_tools()` must never filter or
de-emphasize by `updt_dt` age.

`get_sem_list()` serves the reachable fleet (the `_avail` + `_version` merge);
`get_pending_tools()` serves the difference. Contract details worth mirroring
here:

* `updt_dt` is the tool's FIRST ARRIVAL time at the fab, NOT a roster-update
  timestamp (user-confirmed 2026-07-30). It is imprecise for old tools and
  trustworthy for recent ones. Per the snapshot fact above it carries no
  staleness signal, so on the pending screen it is informational only.
* `version` is a FREE-FORM STRING ("1A"), not a number — do not sort it
  numerically anywhere.
* `vendor_nm` is HITACHI or AMAT for the reachable fleet, and the office
  adapter raises on a third value there. `PendingToolRow` deliberately does
  NOT constrain it — a newly installed tool from a new vendor must appear on
  the 미연결 screen instead of 502-ing it.
* `available` arrives as any of on/off/true/false/1/0 and is normalized to
  "On"/"Off". This mock emits the normalized form directly. Pending tools
  have no `available` at all.
* the fleet carries no `tool_type` column — it is derived from `eqp_model_cd`.
  Backend `_tool_specs.model_to_tool_type` and frontend `classifyToolType`
  both resolve all four tool types (cd-sem/hv-sem/veritysem/provision) and
  are kept in agreement by a shared fixture (see `_tool_specs.py`). "CD/HV
  only" is expressed by naming the scope — `in SEM_TOOL_TYPES` when the code
  holds a tool_type, `in SEM_TOOL_SLUGS` when it holds a URL slug — never by
  a `None` check, since a resolved AMAT tool would wrongly pass that.
  Note that the CD/HV-scoped ebeam features do NOT each re-filter this roster
  by `SEM_TOOL_TYPES`: several (`storage`, `lateral_recipe`) select rows with
  `model_to_tool_type(...) == tool_type` for the single requested family, and
  the scope is enforced one level up, by their routes refusing any slug
  outside `SEM_TOOL_SLUGS` with a 400. Both spellings are correct; what is
  wrong is a route that lets an AMAT slug reach an `== tool_type` filter,
  because that filter then happily matches the AMAT rows below and answers
  200 with fabricated data for a family that has no adapter.

THIS IS THE FLEET IDENTITY SOURCE, and that has a consequence for home runs.
`storage`, `lateral_recipe`, `hardware/sharpness`, `hardware/reso_center` and
`hardware/mdc` all resolve eqp_id -> eqp_ip / fab_name through this roster, so
those office adapters REFUSE to run while sem_list is on mock: a fabricated IP
matches zero documents and is indistinguishable from "no data". Turning one of
them onto office therefore means turning sem_list on too.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Literal

from back_dev_home.sem_list.contracts import PendingToolRow, SemListRow


# The fabs actually in operation (user-confirmed 2026-08-03). M12 used to sit
# where M10 is and was never a real fab — it made every screen that groups by
# facility show a column nobody could reconcile against the floor.
FAC_IDS = ["M10", "M11", "M14", "M15", "M16", "R3"]
FAB_SUFFIXES = ["A", "B", "C"]

# Fleet identity is keyed on the TOOL FAMILY, not the vendor. Both families in
# scope today are Hitachi: CD-SEM is the CG/GT-series, HV-SEM is the TP-series.
# AMAT enters only as VeritySEM/Provision, which are their own tool types
# (`classifyToolType` in front-dev-home/app/utils/toolType.ts) rather than
# HV-SEM, and are deferred
# to 2027. Models and eqp_id prefixes mirror TOOL_SPECS in _tool_specs.py.
CDSEM_MODELS = ["CG6300", "CG6320", "CG6340", "CG6360", "CG6380", "GT2000", "GT2000S"]
CDSEM_EQP_PREFIXES = ["ECXDX", "ECDX", "HCDX"]

HVSEM_MODELS = ["TP3000", "TP3500", "TP4000", "TP4500"]
HVSEM_EQP_PREFIXES = ["PCD", "MCD", "ACD", "VCD"]

# AMAT tools, deferred to 2027. They belong in the inventory and both
# classifiers resolve them (to 'veritysem' / 'provision'), but they are NOT
# CD/HV-SEM, so the tool-scoped ebeam views never show them: those routes only
# accept `SEM_TOOL_SLUGS` (cdsem/hvsem) and answer 400 to an AMAT slug, so the
# rows below are never selected there. The 미연결 screen is the exception: it groups
# by tool type too, but shows AMAT under its own filter chip — their
# firewall requests get filed too, just not this year. Kept rare here
# because at the old ~50% they crowded the CD/HV-SEM pages down to half a
# fleet. The prefix pool is unverified; nothing classifies by prefix (it only
# builds eqp_ids), so it is cosmetic.
AMAT_MODELS = ["PROVISION_10", "PROVISION_20", "VERITYSEM_4", "VERITYSEM_5"]
AMAT_EQP_PREFIXES = ["PCD", "MCD", "ACD", "VCD"]

# Fleet mix. AMAT stays small; the rest splits CD-SEM / HV-SEM roughly 7:3.
AMAT_SHARE = 0.10
CDSEM_SHARE = 0.62

EQP_GRP_PREFIXES = ["G-ECD-", "G-MCD-", "G-KCD-", "G-MDS-", "G-PCD-", "G-ACD-"]

# Newly installed tools awaiting an IT firewall exception. An explicit table,
# not a random draw: what this fixture has to stand in for is the SHAPE of an
# arrival batch — a few fab x model cells holding several tools each — and a
# uniform random draw produces a matrix of all 1s that never exercises the
# aggregation. Counts and ids are invented; only the shape is claimed.
#
#                fab_name  fac_id  eqp_model_cd     prefix  count  days_ago
_PENDING_CLUSTERS = [
    ("M16A", "M16", "CG6380", "ECDX", 2, 8),
    ("M16B", "M16", "GT2000", "ECDX", 4, 15),
    ("M14B", "M14", "TP4000", "PCD", 5, 22),
    # 400 days old and still unreachable. Not stale — v3_df_sem_list is a
    # live snapshot, so this row cannot be an abandoned roster entry — it is
    # exactly the embarrassing case this screen exists to surface: a tool
    # that has waited over a year for its firewall exception.
    ("M16A", "M16", "VERITYSEM_4", "VCD", 2, 400),
    # No fab assignment yet — exercises the 미배정 bucket. Kept on a different
    # row from the 400-day-old one so each edge case is reachable on its own.
    ("", "M11", "PROVISION_10", "ACD", 1, 30),
]


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
        # Arrival time, so the fleet's values span years — a roster of tools
        # that all arrived within 90 days would teach that this column is a
        # recency signal, which is exactly the misreading the docs used to
        # encode. Values change freely: check_contract.py compares key sets
        # and value TYPES, never value equality.
        updt_dt = (
            now - timedelta(days=rng.randint(0, 2555))
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


def _generate_pending(
    taken: set[str], seed: int = 43
) -> list[PendingToolRow]:
    """The 14 roster tools skewnono cannot reach yet.

    ``taken`` is the connected fleet's eqp_id set. Ids are re-rolled on
    collision rather than drawn from a reserved numeric range, so the
    disjointness invariant holds even if the connected generator's id scheme
    changes later.
    """
    rng = random.Random(seed)
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    used = set(taken)
    rows: list[PendingToolRow] = []

    for fab_name, fac_id, model, prefix, count, days_ago in _PENDING_CLUSTERS:
        vendor_nm = "AMAT" if model in AMAT_MODELS else "HITACHI"
        for _ in range(count):
            eqp_id = f"{prefix}{rng.randint(100, 999)}"
            while eqp_id in used:
                eqp_id = f"{prefix}{rng.randint(100, 999)}"
            used.add(eqp_id)

            ip_prefix = "177" if rng.random() < 0.5 else "197"
            rows.append(PendingToolRow(
                fac_id=fac_id,
                eqp_id=eqp_id,
                eqp_model_cd=model,
                eqp_grp_id=f"{rng.choice(EQP_GRP_PREFIXES)}{rng.randint(1, 3):02d}",
                vendor_nm=vendor_nm,
                # Always present: assigned at fab installation.
                eqp_ip=(
                    f"{ip_prefix}.{rng.randint(1, 254)}"
                    f".{rng.randint(1, 254)}.{rng.randint(1, 254)}"
                ),
                fab_name=fab_name,
                updt_dt=(
                    now - timedelta(days=days_ago)
                ).isoformat().replace("+00:00", "Z"),
            ))

    return rows


def get_sem_list() -> list[SemListRow]:
    return _generate_rows()


def get_pending_tools() -> list[PendingToolRow]:
    return _generate_pending({row["eqp_id"] for row in _generate_rows()})
