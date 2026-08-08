"""Phase 1 faithful mdc_setting mock (fleet dict-of-dict, as-of snapshot).

Shape from `docs/datatables/hardware_mdc_setting.txt`: `{eqp_id: {beam_condition: value}}`
for the requested eqp + in-fab siblings. Values are correction-factor strings
near 1.0 (`result = MDC * raw`). Some tools carry extra conditions (3000V,
Valley). `as_of` perturbs values (snapshot-by-date) while the tool/condition
set stays stable per (eqp_id, fab_name).

Office counterpart (office-confirmed 2026-07-27), so home development knows what
it is standing in for: the snapshot is the Redis hash `mdc_setting` (field =
fab_name, value = that fab's whole map) and the history is dated MinIO JSON at
`hitachi_sem/cdsem/mdc_setting/YYYY/MM/DD/{fab_name}.json` — the same two-tier
shape as SCE, different names.

COVERAGE: MDC applies to EVERY fab, R3/R4 included. Do NOT copy the R3/R4
exclusion from `sce/mock.py` by analogy — the two differ exactly here, and the
consequence is not cosmetic: for SCE an absent fab is normal, for MDC it means
collection failed (`mdc/office_example.py` logs rather than returning a quiet
empty, pinned in tests/test_mdc_office.py). `sibling_eqp_ids` is fab-agnostic,
so this mock already emits for R3/R4 tools — deliberate, not an oversight.

TIMESTAMP GRAIN differs from the office on purpose. This mock places
recalibration events at real hours (`2026-05-11 04:00`) so the 시계열 chart has
something to lay out; the office archive is filed per DATE and its adapter emits
`00:00`. Same format string, different resolution — a time-of-day pattern here
is a Phase-1 fabrication, never an office property.
"""

from __future__ import annotations

import random

from datetime import datetime, timedelta

from back_dev_home.ebeam.hardware.providers._siblings import (
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


_TS_FMT = "%Y-%m-%d %H:%M"
# Random-walk band: the same envelope the snapshot values use.
_BAND_LO, _BAND_HI = 0.995, 1.006
# Walk origin far enough back to cover any plausible request window.
_WALK_ANCHOR = datetime(2025, 1, 1, 9, 0)


def build_mdc_history(
    eqp_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, str | float]]:
    """Timestamped MDC history for one tool across [start, end], ascending.

    Recalibration events land every 3-10 days; each event refreshes every
    beam_condition the tool carries (long format: one record per condition).
    Values drift as a clamped random walk inside the snapshot band. The walk
    always replays from a fixed anchor, so a given eqp_id yields identical
    values for the same dates regardless of the requested window.
    """
    struct_seed = seed_for(eqp_id) ^ 0x4D44_4332          # same tool/condition set as settings
    conds = _conditions_for(random.Random(struct_seed))
    rng = random.Random(struct_seed ^ 0x48495354)         # distinct history value stream
    values = {cond: rng.uniform(_BAND_LO, _BAND_HI) for cond in conds}

    records: list[dict[str, str | float]] = []
    moment = _WALK_ANCHOR
    while moment <= end:
        if moment >= start:
            for cond in conds:
                records.append(
                    {
                        "timestamp": moment.strftime(_TS_FMT),
                        "beam_condition": cond,
                        "mdc_value": round(values[cond], 6),
                    }
                )
        moment += timedelta(days=rng.randint(3, 10), hours=rng.randint(0, 5))
        for cond in conds:
            stepped = values[cond] + rng.gauss(0.0, 0.0012)
            values[cond] = min(_BAND_HI, max(_BAND_LO, stepped))
    return records
