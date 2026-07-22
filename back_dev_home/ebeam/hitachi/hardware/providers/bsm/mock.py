"""Phase 1 faithful beam_shape (`type: "total"`) mock for the hardware bsm panel.

Produces the raw doc shape documented in `docs/datatables/beam_shape.txt`:
per-degree length-16 arrays (Reso EB, Reso Detector, Noise, Focus offset,
Apature angle factor, Reso EB Focus) keyed alongside a 16-step `degree` axis,
plus the scalar summary fields and the metadata tail. Fabricated straight off
`metrics.BEAM_SHAPE_METRICS`, so a new registry entry appears in every doc.

This is SEPARATE from `bsm_mock.py` (kept for pm_planning's BM/PM gate). Here
we emit the faithful raw docs the hardware page reads directly.

Determinism mirrors the other providers: `random.Random` seeded from md5(eqp_id),
anchored to `_siblings.NOW`. `index2` docs are intentionally not emitted.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from back_dev_home.ebeam.hitachi.hardware.metrics import BEAM_SHAPE_METRICS
from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
    eqp_ip_for,
    fac_id_for,
    seed_for,
)


__all__ = ["build_beam_shape_docs"]


# 16 angular steps: 0.0, 22.5, ... 337.5
DEGREES: list[float] = [round(i * 22.5, 1) for i in range(16)]

# Beam conditions sampled per tool (mirrors the source `HR0800_IP0080` style).
_BEAM_CONDITIONS: tuple[str, ...] = ("HR0800_IP0080", "HR0500_IP0080")

# `category` values seen in the source ("I-diff_hp" etc.); one per beam_cond.
_CATEGORY_BY_COND: dict[str, str] = {
    "HR0800_IP0080": "I-diff_hp",
    "HR0500_IP0080": "I-diff_lp",
}

# Scheduled monitoring runs at roughly these slots each day (matches bsm_mock).
_DAILY_HOURS: tuple[int, ...] = (6, 14, 22)


def _round_for(low: float, high: float, value: float) -> float:
    """Round to a sensible precision for the metric's magnitude."""
    span = abs(high)
    if span < 0.01:
        return round(value, 6)
    if span < 1.0:
        return round(value, 5)
    return round(value, 4)


def _profile16(rng: random.Random, low: float, high: float) -> list[float]:
    """Length-16 per-degree array within [low, high] with organic wobble."""
    center = rng.uniform(low + (high - low) * 0.35, low + (high - low) * 0.65)
    wobble = (high - low) * 0.12
    out: list[float] = []
    for _ in DEGREES:
        v = min(high, max(low, center + rng.uniform(-wobble, wobble)))
        out.append(_round_for(low, high, v))
    return out


def _scalar(rng: random.Random, low: float, high: float) -> float:
    return _round_for(low, high, rng.uniform(low, high))


def _timestamps(rng: random.Random, start: datetime, end: datetime) -> list[datetime]:
    """3 measurements/day across [start, end], ascending."""
    moments: list[datetime] = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day <= end:
        for hour in _DAILY_HOURS:
            moment = day.replace(hour=hour, minute=rng.choice([0, 15, 30, 45]))
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
    doc: dict = {
        "category": _CATEGORY_BY_COND.get(beam_condition, "I-diff_hp"),
        "degree": list(DEGREES),
    }
    # Per-degree arrays + scalars straight off the registry.
    for metric in BEAM_SHAPE_METRICS:
        if metric["kind"] == "profile16":
            doc[metric["key"]] = _profile16(rng, metric["low"], metric["high"])
        else:
            doc[metric["key"]] = _scalar(rng, metric["low"], metric["high"])
    # `Reso EB Focus` is a per-degree array; `Reso EB Focus Range` a short list.
    doc["Reso EB Focus"] = _profile16(rng, 7.90, 9.00)
    doc["Reso EB Focus Range"] = [f"{rng.uniform(7.5, 8.5):.4f}"]
    # Faithful tail.
    doc["type"] = "total"
    doc["beam_condition"] = beam_condition
    doc["fdc_category"] = "bsi_beam_shape"
    doc["timestamp"] = moment.strftime("%Y-%m-%dT%H:%M:%S")
    doc["timestamp_date"] = moment.strftime("%Y-%m-%d")
    doc["eqp_ip"] = eqp_ip
    doc["eqp_id"] = eqp_id
    doc["fac_id"] = fac_id
    doc["fab_name"] = fab_name
    return doc


def build_beam_shape_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Ascending-time faithful `total` beam_shape docs across [start, end].

    One doc per (timestamp, beam_condition). Deterministic per eqp_id.
    """
    rng = random.Random(seed_for(eqp_id))
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
