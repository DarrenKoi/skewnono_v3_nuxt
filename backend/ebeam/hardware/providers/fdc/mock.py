"""Phase 1 faithful network_fdc_cdsem mock.

Raw doc shape from `docs/datatables/hitachi/hardware_network_fdc_cdsem.txt`. One doc = one
(eqp_id, timestamp, values) where `values` begins with the `fdc_key` and then
follows that key's own layout:

  TemperatureEChuck        [key, '0', pos('1'|'2'|'3'), temp]
  SPMVoltages              [key, '0', A/B/C, '7','1','1', fit model, 107 nums]
  LaserPower               [key, '0', x1, y1, x2, y2]   (two differing scales)
  ContactpinConductionInfo [key, '0', A/B/C, pin, judgment, 4 nums, counter]

Calibrated to the office characterization run (office 확인 2026-09-28,
`docs/datatables/hitachi/hardware_fdc_sce_characterization.md`):

* Key coverage follows the model: CG6300 emits all four keys, GT2000/GT2000S
  no Contactpin, CG5000 SPMVoltages only. The other CG63xx models are assumed
  to follow CG6300 (OFFICE-VERIFY). An empty sub-tab is normal.
* TemperatureEChuck: a per-tool cadence with median 4-16 min, the 3 positions
  logged within +-30 s of each other (never the same second), position
  offsets under 0.02 degC. Tool means spread ~15x wider than within-tool
  noise, and a slow daily walk carries the drift. The idle stretches that keep
  the busiest tool near the office's 16.5k docs / 30 days, and the step size
  at BM/PM, are OFFICE-VERIFY.
* SPMVoltages: the profile is always 107 numbers; A/B/C never share a
  timestamp; some tools emit only two channels; the unit scale differs up to
  100x between tools. `spline`/`quartic` is the fit-model name, not a verdict.
  The profile SHAPE (a single smooth dip) is OFFICE-VERIFY.
* LaserPower: x1/y1 are stable per tool; x2/y2 wander (drift that is noise).
* ContactpinConductionInfo: the judgment is Conduction / UnstableConduction /
  NonConduction. The spread of the first 4 numbers separates them (medians
  6.4 / - / 38.0, threshold ~15-20); the last number is a per-channel counter
  that only grows. values[3] is the pin number, 1-25 (user-confirmed
  2026-09-28). Class rates, the Unstable spread band and the events per log
  interval are OFFICE-VERIFY.

At the office the writer (`ops_index_mgmt/network_fdc_cdsem.iter_bulk_actions`)
also stores typed side-fields derived from `values` (temp_pos, temp_c,
laser_x1, laser_y1, pin, first4_spread, counter) for the fleet aggregations.
The per-tool adapter does not fetch them (`SOURCE_FIELDS`), so these docs
carry the seven fields the page sees; `side_fields()` over them yields the
same set the office writes (pinned in tests/test_vendored_ops_index_mgmt.py).

The office index also holds byte-identical duplicates (the rollover alias
spans two backing indices). The office adapter strips them, so this mock
emits the post-adapter shape: no duplicates.

Deterministic per eqp_id; docs ascending by timestamp.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from functools import cache

from backend.ebeam._tool_specs import TOOL_SPECS
from backend.ebeam.hardware.providers._siblings import (
    eqp_ip_for,
    seed_for,
)
from backend.sem_list.providers.mock import get_sem_list


__all__ = ["build_fdc_docs"]


_ABC: tuple[str, ...] = ("A", "B", "C")
# CG5000 carries FDC rows at the office but is not in the cd-sem roster list.
_FDC_MODELS: list[str] = [*TOOL_SPECS["cdsem"]["eqp_models"], "CG5000"]

_ALL_KEYS = frozenset(
    {"TemperatureEChuck", "SPMVoltages", "LaserPower", "ContactpinConductionInfo"}
)
_KEYS_BY_MODEL: dict[str, frozenset[str]] = {
    "CG5000": frozenset({"SPMVoltages"}),
    "GT2000": _ALL_KEYS - {"ContactpinConductionInfo"},
    "GT2000S": _ALL_KEYS - {"ContactpinConductionInfo"},
}

SPM_PROFILE_LEN = 107

# (judgment, share, spread band of the first 4 numbers). Office medians:
# Conduction 6.4, NonConduction 38.0. Shares and the Unstable band OFFICE-VERIFY.
_CONTACTPIN_CLASSES: tuple[tuple[str, float, tuple[float, float]], ...] = (
    ("Conduction", 0.75, (2.0, 11.0)),
    ("UnstableConduction", 0.10, (14.0, 24.0)),
    ("NonConduction", 0.15, (28.0, 48.0)),
)
_CONTACTPIN_WEIGHTS = [share for _, share, _ in _CONTACTPIN_CLASSES]


@cache
def _roster_models() -> dict[str, str]:
    """eqp_id -> eqp_model_cd from the sem_list mock (first row wins; the
    roster repeats a few ids). The model decides which keys a tool emits, so
    it must be the one the tool selector shows, not an independent guess."""
    models: dict[str, str] = {}
    for row in get_sem_list():
        models.setdefault(row["eqp_id"], row["eqp_model_cd"])
    return models


def _fmt(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def _base(eqp_id: str, eqp_model_cd: str, fab_name: str | None, eqp_ip: str) -> dict:
    return {
        "eqp_id": eqp_id,
        "eqp_model_cd": eqp_model_cd,
        "fab_name": fab_name,
        "eqp_ip": eqp_ip,
    }


def _doc(base: dict, key: str, moment: datetime, values: list[str]) -> dict:
    return {**base, "fdc_key": key, "timestamp": _fmt(moment), "values": [key, "0", *values]}


def _temperature_docs(
    rng: random.Random, base: dict, start: datetime, end: datetime
) -> list[dict]:
    """3-position chuck temperature every few minutes, with idle stretches."""
    median_gap = rng.uniform(4.0, 16.0)  # minutes
    tool_mean = 23.40 + rng.gauss(0.0, 0.15)  # fleet spread
    offsets = {pos: rng.uniform(-0.009, 0.009) for pos in ("1", "2", "3")}
    noise = 0.01  # within-tool
    out: list[dict] = []
    cursor = start
    day = start.date()
    level = tool_mean
    while cursor <= end:
        if cursor.date() != day:  # the daily walk that carries the drift
            day = cursor.date()
            level += rng.gauss(0.0, 0.01)
            if rng.random() < 0.03:  # occasional step, BM/PM-like (OFFICE-VERIFY)
                level += rng.choice((-1, 1)) * rng.uniform(0.03, 0.08)
        moment = cursor
        for pos in ("1", "2", "3"):
            if moment > end:
                break
            temp = level + offsets[pos] + rng.gauss(0.0, noise)
            out.append(_doc(base, "TemperatureEChuck", moment, [pos, f"{temp:.5f}"]))
            moment += timedelta(seconds=rng.randint(3, 14))
        gap = median_gap * rng.uniform(0.7, 1.3)
        # Idle stretches: about half the wall clock logs nothing (OFFICE-VERIFY).
        if rng.random() < median_gap / 420.0:
            gap += rng.uniform(120.0, 720.0)
        cursor += timedelta(minutes=gap)
    return out


def _spm_shape(rng: random.Random) -> list[float]:
    """One channel's base profile: a smooth single dip on a gentle slope."""
    depth = rng.uniform(0.6, 1.4)
    center = rng.uniform(35.0, 70.0)
    width = rng.uniform(10.0, 22.0)
    slope = rng.uniform(-0.4, 0.4)
    return [
        -depth * math.exp(-(((i - center) / width) ** 2)) + slope * i / SPM_PROFILE_LEN
        for i in range(SPM_PROFILE_LEN)
    ]


def _spm_docs(
    rng: random.Random, base: dict, start: datetime, end: datetime
) -> list[dict]:
    """107-point profile per channel; tool-specific unit scale; sparse cadence."""
    scale = 10 ** rng.uniform(-1.0, 1.0)  # up to 100x between tools
    channels = _ABC if rng.random() < 0.75 else _ABC[:2]
    shapes = {ch: _spm_shape(rng) for ch in channels}
    out: list[dict] = []
    cursor = start + timedelta(hours=rng.randint(2, 12))
    while cursor <= end:
        for i, ch in enumerate(channels):
            moment = cursor + timedelta(minutes=i * 2, seconds=rng.randint(0, 50))
            if moment > end:
                continue
            fit_model = rng.choice(["spline", "quartic"])
            wobble = rng.gauss(1.0, 0.02)
            nums = [
                f"{scale * (v * wobble + rng.gauss(0.0, 0.03)):.4f}" for v in shapes[ch]
            ]
            token = rng.choice(["6", "7"])
            out.append(
                _doc(base, "SPMVoltages", moment, [ch, token, "1", "1", fit_model, *nums])
            )
        cursor += timedelta(days=rng.choice([1, 2, 3]))
    return out


def _laser_docs(
    rng: random.Random, base: dict, start: datetime, end: datetime
) -> list[dict]:
    """Stable (x1, y1) ratios per tool; (x2, y2) counts that wander."""
    x1_level = rng.uniform(0.70, 0.85)
    y1_level = rng.uniform(0.68, 0.80)
    x2 = float(rng.randint(300_000_000, 360_000_000))
    y2 = float(rng.randint(40_000_000, 50_000_000))
    out: list[dict] = []
    cursor = start
    while cursor <= end:
        moment = cursor.replace(hour=rng.choice([8, 16]), minute=rng.choice([0, 30]))
        x2 *= rng.gauss(1.0, 0.02)
        y2 *= rng.gauss(1.0, 0.02)
        if start <= moment <= end:
            x1 = f"{x1_level + rng.gauss(0.0, 0.004):.2f}"
            y1 = f"{y1_level + rng.gauss(0.0, 0.004):.2f}"
            out.append(
                _doc(base, "LaserPower", moment, [x1, y1, f"{x2:.0f}", f"{y2:.0f}"])
            )
        cursor += timedelta(days=1)
    return out


def _contactpin_numbers(rng: random.Random, spread: float) -> list[str]:
    """Four ascending numbers whose max - min is `spread` (the office samples
    read ascending: '-5.0', '-5.0', '0.0', '5.0')."""
    lo = rng.uniform(-8.0, 2.0) - spread / 2.0
    mid = sorted(lo + rng.uniform(0.0, spread) for _ in range(2))
    return [f"{v:.1f}" for v in (lo, *mid, lo + spread)]


def _contactpin_docs(
    rng: random.Random, base: dict, start: datetime, end: datetime
) -> list[dict]:
    """A/B/C conduction check, clustered in time; weekly-ish cadence."""
    counters = {ch: rng.randint(100_000, 200_000) for ch in _ABC}
    out: list[dict] = []
    cursor = start + timedelta(hours=rng.randint(1, 20))
    while cursor <= end:
        for i, ch in enumerate(_ABC):
            moment = cursor + timedelta(minutes=i * 3)
            if moment > end:
                continue
            judgment, _, (low, high) = rng.choices(_CONTACTPIN_CLASSES, weights=_CONTACTPIN_WEIGHTS)[0]
            counters[ch] += rng.randint(5, 60)  # events since the last log
            values = [
                ch,
                str(rng.randint(1, 25)),  # pin
                judgment,
                *_contactpin_numbers(rng, rng.uniform(low, high)),
                str(counters[ch]),
            ]
            out.append(_doc(base, "ContactpinConductionInfo", moment, values))
        cursor += timedelta(days=rng.choice([5, 7, 9]))
    return out


_BUILDERS = {
    "TemperatureEChuck": _temperature_docs,
    "SPMVoltages": _spm_docs,
    "LaserPower": _laser_docs,
    "ContactpinConductionInfo": _contactpin_docs,
}


def build_fdc_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    rng = random.Random(seed_for(eqp_id) ^ 0x4644_4332)  # distinct stream
    model = _roster_models().get(eqp_id) or rng.choice(_FDC_MODELS)
    base = _base(eqp_id, model, fab_name, eqp_ip_for(eqp_id))
    keys = _KEYS_BY_MODEL.get(model, _ALL_KEYS)
    docs: list[dict] = []
    for key, build in _BUILDERS.items():
        if key in keys:
            docs += build(rng, base, start, end)
    docs.sort(key=lambda d: (d["timestamp"], d["fdc_key"], str(d["values"][2:3])))
    return docs
