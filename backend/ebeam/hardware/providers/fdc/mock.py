"""Phase 1 faithful network_fdc_cdsem mock.

Raw doc shape from `docs/datatables/hitachi/hardware_network_fdc_cdsem.txt`. One doc = one
(eqp_id, timestamp, values) where `values` begins with the `fdc_key` and then
follows that key's own layout:

  TemperatureEChuck        [key, '0', pos('1'|'2'|'3'), temp]
  SPMVoltages              [key, '0', A/B/C, '7','1','1', fit model, 107 nums]
                           (CG5000: no fit model token)
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
  The profile SHAPE (a single smooth dip) is OFFICE-VERIFY. CG5000 lines
  carry no fit-model token (office 확인 2026-09-29); that the three header
  numbers stay in front of its profile is OFFICE-VERIFY.
* LaserPower: x1/y1 are stable per tool; x2/y2 wander (drift that is noise).
* ContactpinConductionInfo: the judgment is Conduction / UnstableConduction /
  NotConduction ('Not', not 'Non': user-confirmed 2026-09-29). The spread of the first 4 numbers separates them (medians
  6.4 / - / 38.0, threshold ~15-20); the last number is a per-channel counter
  that only grows. values[3] is the pin number, 1-25 (user-confirmed
  2026-09-28). Class rates, the Unstable spread band and the events per log
  interval are OFFICE-VERIFY.

At the office the writer also stores typed side-fields derived from `values`
(`ops_index_mgmt/network_fdc_cdsem.side_fields`: temp_pos, temp_c, laser_x1,
laser_y1, spm_channel, spm_judgment, pin_channel, pin_no, pin_judgment,
pin_spread, pin_counter; office 확인 2026-09-28) for the fleet aggregations.
The per-tool adapter does not fetch them (`SOURCE_FIELDS`), so these docs
carry the seven fields the page sees. `build_fdc_fleet` applies the same
`side_fields` and emulates the aggregation OpenSearch would answer. Live
since 2026-09-28 (office 확인 2026-09-29). CG5000 docs get no spm_judgment,
so a CG5000 fleet row has every compared field empty; that is a normal row.
The sem_list mock has no CG5000 tool, so home never shows one (the office
roster does). Not emulated: the ~6.8% of docs written 2026-09-28
11:20-12:45 without side-fields (an old-code twin task wrote them first and
the create-dedup locked them).

The office index also holds byte-identical duplicates (the rollover alias
spans two backing indices). The office adapter strips them, so this mock
emits the post-adapter shape: no duplicates.

Deterministic per eqp_id; docs ascending by timestamp.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from functools import cache
from statistics import fmean

from backend.ebeam._tool_specs import TOOL_SPECS
from backend.ebeam.hardware.providers._siblings import (
    eqp_ip_for,
    seed_for,
)
from backend.ebeam.hardware.contracts import FdcFleet
from backend.ebeam.hardware.providers.fdc.fleet import (
    SPREAD_BIN_WIDTH,
    fab_roster,
    fleet_from_aggs,
)
from backend.sem_list.providers.mock import get_sem_list
from ops_index_mgmt.network_fdc_cdsem import side_fields


__all__ = ["build_fdc_docs", "build_fdc_fleet"]


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
# Conduction 6.4, NotConduction 38.0. Shares and the Unstable band OFFICE-VERIFY.
_CONTACTPIN_CLASSES: tuple[tuple[str, float, tuple[float, float]], ...] = (
    ("Conduction", 0.75, (2.0, 11.0)),
    ("UnstableConduction", 0.10, (14.0, 24.0)),
    ("NotConduction", 0.15, (28.0, 48.0)),
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
    no_fit_model = base.get("eqp_model_cd") == "CG5000"
    shapes = {ch: _spm_shape(rng) for ch in channels}
    out: list[dict] = []
    cursor = start + timedelta(hours=rng.randint(2, 12))
    while cursor <= end:
        for i, ch in enumerate(channels):
            moment = cursor + timedelta(minutes=i * 2, seconds=rng.randint(0, 50))
            if moment > end:
                continue
            fit_model = [] if no_fit_model else [rng.choice(["spline", "quartic"])]
            wobble = rng.gauss(1.0, 0.02)
            nums = [
                f"{scale * (v * wobble + rng.gauss(0.0, 0.03)):.4f}" for v in shapes[ch]
            ]
            token = rng.choice(["6", "7"])
            out.append(
                _doc(base, "SPMVoltages", moment, [ch, token, "1", "1", *fit_model, *nums])
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


def _epoch_ms(timestamp: str) -> float:
    # OpenSearch reads the offset-less KST wall clock as UTC; only differences
    # are used, so mirroring that reading is enough.
    return datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc).timestamp() * 1000


def _emulate_fleet_aggs(docs_by_tool: dict[str, list[dict]]) -> dict:
    """What OpenSearch answers for `fleet.fleet_aggs()` over these docs, whose
    side-fields are already applied: the same bucket JSON, so the shared
    `fleet_from_aggs` normalizer is what turns it into the contract."""
    def avg(values: list[float]) -> dict:
        return {"value": fmean(values) if values else None}

    tools: list[dict] = []
    margin: dict[str, Counter] = defaultdict(Counter)
    for eqp_id, docs in docs_by_tool.items():
        if not docs:
            continue
        days: dict[str, list[float]] = defaultdict(list)
        stamps: dict[str, set[str]] = defaultdict(set)
        channels: dict[str, list[tuple[float, int]]] = defaultdict(list)
        for doc in docs:
            if "temp_c" in doc:
                days[doc["timestamp"][:10]].append(doc["temp_c"])
            judgment = doc.get("pin_judgment")
            if judgment is not None:
                stamps[judgment].add(doc["timestamp"])  # cardinality(timestamp)
                if "pin_spread" in doc:
                    margin[judgment][math.floor(doc["pin_spread"] / SPREAD_BIN_WIDTH)] += 1
            if "pin_counter" in doc:
                channels[doc["pin_channel"]].append((_epoch_ms(doc["timestamp"]), doc["pin_counter"]))
        tools.append({
            "key": eqp_id,
            "temp_c": avg([d["temp_c"] for d in docs if "temp_c" in d]),
            "laser_x1": avg([d["laser_x1"] for d in docs if "laser_x1" in d]),
            "laser_y1": avg([d["laser_y1"] for d in docs if "laser_y1" in d]),
            "days": {"buckets": [
                {"key_as_string": day, "temp_c": avg(temps)} for day, temps in sorted(days.items())
            ]},
            "judgment": {"buckets": [
                {"key": j, "docs": {"value": len(ts)}} for j, ts in stamps.items()
            ]},
            "channels": {"buckets": [
                {
                    "key": ch,
                    "c_min": {"value": min(c for _, c in points)},
                    "c_max": {"value": max(c for _, c in points)},
                    "t_min": {"value": min(t for t, _ in points)},
                    "t_max": {"value": max(t for t, _ in points)},
                }
                for ch, points in channels.items()
            ]},
        })
    # A histogram agg fills the empty bins between the lowest and highest.
    bins = [b for counts in margin.values() for b in counts]
    margin_buckets = [
        {"key": j, "spread": {"buckets": [
            {"key": b * SPREAD_BIN_WIDTH, "doc_count": counts[b]}
            for b in range(min(counts), max(counts) + 1)
        ]}}
        for j, counts in margin.items()
    ] if bins else []
    return {"tools": {"buckets": tools}, "margin": {"buckets": margin_buckets}}


def build_fdc_fleet(fab_name: str, start: datetime, end: datetime) -> FdcFleet:
    """The fab's CD-SEM roster tools, aggregated like the office's one request."""
    roster = fab_roster(get_sem_list(), fab_name)
    docs_by_tool = {
        eqp_id: [{**doc, **side_fields(doc)} for doc in build_fdc_docs(eqp_id, fab_name, start, end)]
        for eqp_id in roster
    }
    return fleet_from_aggs(_emulate_fleet_aggs(docs_by_tool), roster)
