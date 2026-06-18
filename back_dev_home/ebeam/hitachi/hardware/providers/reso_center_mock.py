"""Phase 1 faithful reso_center (`category: "reso_center_log"`) mock.

Raw doc shape from `docs/datatables/reso_center_data.txt`: center coordinates +
resolution scalars, a 5-offset `Resolution_Range`, and `Raw`/`Smooth` focus
sweeps (dict keyed by the 5 offsets, each -> 5 numbers), plus the metadata tail.
Deterministic per eqp_id; ascending time.
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


_OFFSETS: list[str] = ["-10", "-5", "0", "5", "10"]
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


def _sweep(rng: random.Random, best: float) -> dict[str, list[float]]:
    """Per-offset 5-number resolution curve, minimised near offset 0."""
    out: dict[str, list[float]] = {}
    for off in _OFFSETS:
        penalty = abs(int(off)) * 0.012
        base = best + penalty
        out[off] = [round(base + rng.uniform(-0.02, 0.02), 4) for _ in range(5)]
    return out


def _smooth(raw: dict[str, list[float]]) -> dict[str, list[float]]:
    """Lightly smoothed copy (3-pt moving mean per offset series)."""
    out: dict[str, list[float]] = {}
    for off, values in raw.items():
        sm: list[float] = []
        for i in range(len(values)):
            lo = max(0, i - 1)
            hi = min(len(values), i + 2)
            window = values[lo:hi]
            sm.append(round(sum(window) / len(window), 4))
        out[off] = sm
    return out


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
    raw = _sweep(rng, best)
    doc: dict = {
        "category": "reso_center_log",
        "CenterX": round(rng.uniform(-1.5, 1.5), 2),
        "CenterY": round(rng.uniform(-1.5, 1.5), 2),
        "BestReso": best,
        "ResoIScenter": round(best + rng.uniform(-0.02, 0.02), 2),
        "ResoDelta": round(rng.uniform(0.02, 0.12), 2),
        "Resolution_Range": list(_OFFSETS),
        "Resolution_Range_Raw": raw,
        "Resolution_Range_Smooth": _smooth(raw),
        "beam_condition": beam_condition,
        "timestamp": moment.strftime("%Y-%m-%dT%H:%M:%S"),
        "timestamp_date": moment.strftime("%Y-%m-%d"),
        "eqp_id": eqp_id,
        "eqp_ip": eqp_ip,
        "fac_id": fac_id,
        "fab_name": fab_name,
        "fdc_category": "reso_center_log",
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
