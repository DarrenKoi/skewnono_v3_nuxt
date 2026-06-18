"""Phase 1 faithful mdc_setting mock (fleet dict-of-dict, as-of snapshot).

Shape from `docs/datatables/mdc_setting.txt`: `{eqp_id: {beam_condition: value}}`
for the requested eqp + in-fab siblings. Values are correction-factor strings
near 1.0 (`result = MDC * raw`). Some tools carry extra conditions (3000V,
Valley). `as_of` perturbs values (snapshot-by-date) while the tool/condition
set stays stable per (eqp_id, fab_name).
"""

from __future__ import annotations

import random

from datetime import datetime

from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
    seed_for,
    sibling_eqp_ids,
)


__all__ = ["build_mdc_settings"]


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
        rng = random.Random(seed_for(tool) ^ 0x4D44_4332 ^ as_of_salt)
        conds = _conditions_for(rng)
        out[tool] = {cond: _value(rng) for cond in conds}
    return out
