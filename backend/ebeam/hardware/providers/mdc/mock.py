"""Phase 1 faithful mdc_setting mock (fleet dict-of-dict, as-of snapshot).

Shape from `docs/datatables/hitachi/hardware_mdc_setting.txt`: `{eqp_id: {beam_condition: value}}`
for the requested eqp + in-fab siblings. Values are correction-factor strings
near 1.0 (`result = MDC * raw`). Some tools carry extra conditions (3000V,
Valley). `as_of` perturbs values (snapshot-by-date) while the tool/condition
set stays stable per (eqp_id, fab_name).

Office counterpart (office-confirmed 2026-07-27), so home development knows what
it is standing in for: the snapshot is the Redis hash `mdc_setting` (field =
fab_name, value = that fab's whole map) and the history is dated MinIO JSON at
`hitachi_sem/cdsem/mdc_setting/YYYY/MM/DD/{fab_name}.json` — the same two-tier
shape as SCE, different names.

FAMILY: the office fab map mixes the fab's CD-SEM and HV-SEM tools
(user-confirmed 2026-09-30), and the office adapter cuts it to the selected
tool's family via the sem_list roster. This mock hands back that post-filter
cohort directly — the selected tool's same-fab, same-family tools from the mock
roster (`_siblings.sibling_eqp_ids`) — without modelling the mixed map. The
cohort still MIXES MODELS inside the family, as the office one does
(user-confirmed 2026-10-06: 비교 장비 listed other models); the page narrows it
to the models picked in 장비 선택, client-side.

COVERAGE: MDC applies to EVERY fab, R3/R4 included. Do NOT copy the R3/R4
exclusion from `sce/mock.py` by analogy — the two differ exactly here, and the
consequence is not cosmetic: for SCE an absent fab is normal, for MDC it means
collection failed (`mdc/office_example.py` logs rather than returning a quiet
empty, pinned in tests/test_mdc_office.py). `sibling_eqp_ids` is fab-agnostic,
so this mock already emits for R3/R4 tools — deliberate, not an oversight.

HISTORY GRAIN matches the office archive: one snapshot per collection DATE,
stamped `00:00` like the office adapter's `_ARCHIVE_TIME`, carrying every
condition whether or not it changed. So an unchanged value repeats date after
date, and a change shows only between two consecutive snapshots — what the
시계열 change log and `_office_mdc.py`'s epoch boundaries both rely on.
Values move only on recalibration days (every 3-10 days, a Phase-1 cadence).
Two further properties are guesses, marked so:
  - a recalibration moves each condition with probability `_STEP_PROB`, so
    0°/90° can change apart — OFFICE-VERIFY (whether a recal touches all).
  - `_GAP_RATE` of dates have no snapshot for any tool (a fab JSON that was
    never written, which the office adapter skips and logs) — OFFICE-VERIFY
    (how often collection actually misses).
"""

from __future__ import annotations

import random

from datetime import date, datetime, timedelta

from backend.ebeam.hardware.providers._siblings import (
    seed_for,
    sibling_eqp_ids,
)


__all__ = ["build_mdc_history", "build_mdc_settings"]


_BASE_CONDITIONS: tuple[str, ...] = (
    "800V_HR_0Deg",
    "800V_HR_90Deg",
    "500V_HR_0Deg",
    "500V_HR_90Deg",
)
_EXTRA_CONDITIONS: tuple[str, ...] = ("3000V_HR_0Deg", "Valley")


def _conditions_for(rng: random.Random) -> list[str]:
    conds = list(_BASE_CONDITIONS)
    # Some tools carry extra modes.
    if rng.random() < 0.4:
        conds.append(_EXTRA_CONDITIONS[0])
    if rng.random() < 0.25:
        conds.append(_EXTRA_CONDITIONS[1])
    return conds


def _value(rng: random.Random) -> str:
    return f"{rng.uniform(0.995, 1.006):.6f}"


def build_mdc_settings(
    eqp_id: str,
    fab_name: str | None,
    as_of: datetime,
) -> dict[str, dict[str, str]]:
    eqp_ids = sibling_eqp_ids(eqp_id, fab_name)
    # The as-of date shifts the snapshot deterministically.
    as_of_salt = int(as_of.strftime("%Y%m%d"))
    out: dict[str, dict[str, str]] = {}
    for tool in eqp_ids:
        struct_seed = seed_for(tool) ^ 0x4D44_4332          # stable tool/condition set
        conds = _conditions_for(random.Random(struct_seed))  # date-INDEPENDENT
        val_rng = random.Random(struct_seed ^ as_of_salt)    # date-perturbed values
        out[tool] = {cond: _value(val_rng) for cond in conds}
    return out


# The office adapter's `_ARCHIVE_TIME`: archive dates carry no time of day.
_ARCHIVE_TIME = "00:00"
# Random-walk band: the same envelope the snapshot values use.
_BAND_LO, _BAND_HI = 0.995, 1.006
# Walk origin far enough back to cover any plausible request window.
_WALK_ANCHOR = date(2025, 1, 1)
# OFFICE-VERIFY: both rates are Phase-1 guesses (see the module docstring).
_STEP_PROB = 0.7
_GAP_RATE = 0.06


def _collection_missed(day: date) -> bool:
    # Seeded by the date alone: a missing fab JSON drops the date for every tool.
    return random.Random(day.toordinal() ^ 0x4D445F47).random() < _GAP_RATE


def build_mdc_history(
    eqp_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, str | float]]:
    """Daily MDC snapshots for one tool across [start, end] dates, ascending.

    Long format: one record per (collection date, beam_condition). Values move
    only on recalibration days and repeat otherwise. The walk always replays
    from a fixed anchor, so a given eqp_id yields identical values for the same
    dates regardless of the requested window.
    """
    struct_seed = seed_for(eqp_id) ^ 0x4D44_4332          # same tool/condition set as settings
    conds = _conditions_for(random.Random(struct_seed))
    rng = random.Random(struct_seed ^ 0x48495354)         # distinct history value stream
    values = {cond: rng.uniform(_BAND_LO, _BAND_HI) for cond in conds}

    records: list[dict[str, str | float]] = []
    next_recal = _WALK_ANCHOR + timedelta(days=rng.randint(3, 10))
    day = _WALK_ANCHOR
    while day <= end.date():
        if day >= next_recal:
            for cond in conds:
                if rng.random() < _STEP_PROB:
                    stepped = values[cond] + rng.gauss(0.0, 0.0012)
                    values[cond] = min(_BAND_HI, max(_BAND_LO, stepped))
            next_recal = day + timedelta(days=rng.randint(3, 10))
        if day >= start.date() and not _collection_missed(day):
            for cond in conds:
                records.append(
                    {
                        "timestamp": f"{day.isoformat()} {_ARCHIVE_TIME}",
                        "beam_condition": cond,
                        "mdc_value": round(values[cond], 6),
                    }
                )
        day += timedelta(days=1)
    # Same key the office adapter re-sorts on, and the line every sibling
    # family (bsm, reso_center, sharpness, fdc) already carries. Without it the
    # per-moment order here is whatever _conditions_for produced, so the two
    # providers handed the page different sequences for identical data.
    records.sort(key=lambda r: (r["timestamp"], r["beam_condition"]))
    return records
