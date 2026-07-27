"""Phase 1 faithful network_fdc_cdsem mock.

Raw doc shape from `docs/datatables/hardware_network_fdc_cdsem.txt`. One doc = one
(eqp_id, timestamp, values) where `values` begins with the `fdc_key` and then
follows that key's own layout:

  TemperatureEChuck        [key, '0', pos('1'|'2'|'3'), temp]
  SPMVoltages              [key, '0', A/B/C, '7','1','1', judgment, ~100 nums]
  LaserPower               [key, '0', x1, y1, x2, y2]   (two differing scales)
  ContactpinConductionInfo [key, '0', A/B/C, n, judgment, 5 nums]

Deterministic per eqp_id; docs ascending by timestamp.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from back_dev_home.ebeam.hitachi._tool_specs import TOOL_SPECS
from back_dev_home.ebeam.hitachi.hardware.providers._siblings import (
    eqp_ip_for,
    seed_for,
)


__all__ = ["build_fdc_docs"]


_ABC: tuple[str, ...] = ("A", "B", "C")
_CDSEM_MODELS: list[str] = TOOL_SPECS["cdsem"]["eqp_models"]


def _model_for(rng: random.Random) -> str:
    return rng.choice(_CDSEM_MODELS)


def _fmt(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def _base(eqp_id: str, eqp_model_cd: str, fab_name: str | None, eqp_ip: str) -> dict:
    return {
        "eqp_id": eqp_id,
        "eqp_model_cd": eqp_model_cd,
        "fab_name": fab_name,
        "eqp_ip": eqp_ip,
    }


def _temperature_docs(
    rng: random.Random, base: dict, start: datetime, end: datetime
) -> list[dict]:
    """3-position temperature, sampled every few hours; positions clustered."""
    out: list[dict] = []
    cursor = start
    while cursor <= end:
        for pos in ("1", "2", "3"):
            moment = cursor + timedelta(minutes=int(pos) * rng.choice([1, 2, 3]))
            if moment > end:
                continue
            temp = round(rng.uniform(23.20, 23.60), 5)
            out.append(
                {
                    **base,
                    "fdc_key": "TemperatureEChuck",
                    "timestamp": _fmt(moment),
                    "values": ["TemperatureEChuck", "0", pos, f"{temp}"],
                }
            )
        cursor += timedelta(hours=rng.choice([4, 6, 8]))
    return out


def _spm_docs(
    rng: random.Random, base: dict, start: datetime, end: datetime
) -> list[dict]:
    """~100-point profile per A/B/C, judgment spline|quartic; sparse cadence."""
    out: list[dict] = []
    cursor = start + timedelta(hours=rng.randint(2, 12))
    while cursor <= end:
        for abc in _ABC:
            moment = cursor + timedelta(minutes=_ABC.index(abc) * 2)
            if moment > end:
                continue
            judgment = rng.choice(["spline", "quartic"])
            nums = [f"{rng.uniform(-1.5, 0.5):.4f}" for _ in range(100)]
            values = ["SPMVoltages", "0", abc, "7", "1", "1", judgment, *nums]
            out.append(
                {
                    **base,
                    "fdc_key": "SPMVoltages",
                    "timestamp": _fmt(moment),
                    "values": values,
                }
            )
        cursor += timedelta(days=rng.choice([1, 2, 3]))
    return out


def _laser_docs(
    rng: random.Random, base: dict, start: datetime, end: datetime
) -> list[dict]:
    """Two (x, y) pairs of different scale; sampled a few times/day."""
    out: list[dict] = []
    cursor = start
    while cursor <= end:
        moment = cursor.replace(hour=rng.choice([8, 16]), minute=rng.choice([0, 30]))
        if start <= moment <= end:
            x1 = f"{rng.uniform(0.70, 0.85):.2f}"
            y1 = f"{rng.uniform(0.68, 0.80):.2f}"
            x2 = f"{rng.randint(300_000_000, 360_000_000)}"
            y2 = f"{rng.randint(40_000_000, 50_000_000)}"
            out.append(
                {
                    **base,
                    "fdc_key": "LaserPower",
                    "timestamp": _fmt(moment),
                    "values": ["LaserPower", "0", x1, y1, x2, y2],
                }
            )
        cursor += timedelta(days=1)
    return out


def _contactpin_docs(
    rng: random.Random, base: dict, start: datetime, end: datetime
) -> list[dict]:
    """A/B/C conduction status + 5 numbers; clustered in time, weekly cadence."""
    out: list[dict] = []
    cursor = start + timedelta(hours=rng.randint(1, 20))
    while cursor <= end:
        for abc in _ABC:
            moment = cursor + timedelta(minutes=_ABC.index(abc) * 3)
            if moment > end:
                continue
            judgment = "Conduction" if rng.random() < 0.7 else "NotConduction"
            n = str(rng.randint(2, 6))
            nums = [
                f"{rng.uniform(-25.0, 25.0):.1f}",
                f"{rng.uniform(-5.0, 5.0):.1f}",
                f"{rng.uniform(0.0, 25.0):.1f}",
                f"{rng.uniform(0.0, 25.0):.1f}",
                f"{rng.randint(100000, 200000)}",
            ]
            values = ["ContactpinConductionInfo", "0", abc, n, judgment, *nums]
            out.append(
                {
                    **base,
                    "fdc_key": "ContactpinConductionInfo",
                    "timestamp": _fmt(moment),
                    "values": values,
                }
            )
        cursor += timedelta(days=rng.choice([5, 7, 9]))
    return out


def build_fdc_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    rng = random.Random(seed_for(eqp_id) ^ 0x4644_4332)  # distinct stream
    base = _base(eqp_id, _model_for(rng), fab_name, eqp_ip_for(eqp_id))
    docs: list[dict] = []
    docs += _temperature_docs(rng, base, start, end)
    docs += _spm_docs(rng, base, start, end)
    docs += _laser_docs(rng, base, start, end)
    docs += _contactpin_docs(rng, base, start, end)
    docs.sort(key=lambda d: (d["timestamp"], d["fdc_key"], str(d["values"][2:3])))
    return docs
