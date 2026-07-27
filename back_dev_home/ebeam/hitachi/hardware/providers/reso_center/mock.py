"""Phase 1 faithful reso_center (`category: "reso_center_log"`) mock.

Raw doc shape from `docs/datatables/hardware_reso_center_data.txt`: center coordinates
(`CenterX`/`CenterY`) plus three resolution scalars, then the metadata tail.
`BestReso` is the best-focus resolution (the minimum over the focus sweep);
`ResoIScenter` is the resolution at center focus, so it sits at or above
`BestReso`. `ResoDelta` is their difference (`ResoIScenter - BestReso`, >= 0),
derived here rather than rolled independently so the three stay consistent.

Focus Sweep is intentionally not modeled — the wide `Resolution_Range*` objects
were dropped along with the sweep chart. Deterministic per eqp_id; ascending
time.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
    eqp_ip_for,
    fac_id_for,
    seed_for,
)


__all__ = ["build_reso_center_docs"]


_BEAM_CONDITIONS: tuple[str, ...] = ("HR0800_IP0080", "HR0500_IP0080")
_DAILY_HOURS: tuple[int, ...] = (7, 19)


def _timestamps(rng: random.Random, start: datetime, end: datetime) -> list[datetime]:
    moments: list[datetime] = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        for hour in _DAILY_HOURS:
            moment = day.replace(hour=hour, minute=rng.choice([5, 25, 55]))
            if start <= moment <= end:
                moments.append(moment)
        day += timedelta(days=1)
    moments.sort()
    return moments


def _build_doc(
    rng: random.Random,
    *,
    eqp_id: str,
    fab_name: str | None,
    eqp_ip: str,
    fac_id: str,
    moment: datetime,
    beam_condition: str,
) -> dict:
    best = round(rng.uniform(2.90, 3.10), 2)
    # Center focus is at or worse than best focus, so ResoIScenter >= BestReso
    # and ResoDelta (their difference) is a small non-negative degradation.
    reso_is_center = round(best + rng.uniform(0.0, 0.12), 2)
    reso_delta = round(reso_is_center - best, 2)
    doc: dict = {
        "category": "reso_center_log",
        "CenterX": round(rng.uniform(-1.5, 1.5), 2),
        "CenterY": round(rng.uniform(-1.5, 1.5), 2),
        "BestReso": best,
        "ResoIScenter": reso_is_center,
        "ResoDelta": reso_delta,
        "beam_condition": beam_condition,
        "timestamp": moment.strftime("%Y-%m-%dT%H:%M:%S"),
        "timestamp_date": moment.strftime("%Y-%m-%d"),
        "eqp_id": eqp_id,
        "eqp_ip": eqp_ip,
        "fac_id": fac_id,
        "fab_name": fab_name,
    }
    return doc


def build_reso_center_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    rng = random.Random(seed_for(eqp_id) ^ 0x5253_4332)  # distinct stream from bsm
    eqp_ip = eqp_ip_for(eqp_id)
    fac_id = fac_id_for(fab_name)
    docs: list[dict] = []
    for moment in _timestamps(rng, start, end):
        for beam_condition in _BEAM_CONDITIONS:
            docs.append(
                _build_doc(
                    rng,
                    eqp_id=eqp_id,
                    fab_name=fab_name,
                    eqp_ip=eqp_ip,
                    fac_id=fac_id,
                    moment=moment,
                    beam_condition=beam_condition,
                )
            )
    docs.sort(key=lambda d: (d["timestamp"], d["beam_condition"]))
    return docs
