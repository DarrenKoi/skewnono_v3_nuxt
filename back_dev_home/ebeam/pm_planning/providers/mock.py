"""Mock provider for the pm-planning fleet snapshot.

This mock synthesizes a fab-scoped CD-SEM fleet snapshot: per-tool Up-gate
inputs and per-cell signed skew. This module is pm_planning's mock adapter —
`data.py` is the feature's single public import surface for routers and other
features; this module implements the mock behavior documented in
MIGRATION.md and is never imported directly except by `data.py`'s switch.
The future office implementation should keep the same public function and
TypedDict shape while replacing this generator with real data access.
"""

import hashlib
import json
import random
import statistics
from datetime import datetime, timedelta, timezone

from back_dev_home.ebeam._tool_specs import TOOL_SPECS
from back_dev_home.ebeam.hardware.providers.bm_pm.mock import build_bm_pm_data
from back_dev_home.ebeam.hardware.providers.pm_gate_bsm_mock import (
    build_bsm_data,
)
from back_dev_home.ebeam.hardware.providers.spec_range_mock import (
    bsm_in_spec,
    get_cd_monitoring_spec,
)
from back_dev_home.ebeam.pm_planning.contracts import (
    BeamCondition,
    CellSkew,
    ConsensusCell,
    EpochPoint,
    FleetPayload,
    GateBlock,
    ScanAxis,
    ToolBlock,
)


__all__ = ["BEAM_CONDITIONS", "AXES", "DEFAULTS", "get_pm_planning_fleet"]


BEAM_CONDITIONS: list[BeamCondition] = ["500V", "800V"]
AXES: list[ScanAxis] = ["X", "Y"]

DEFAULTS = {
    "focus_n": 3,
    "advisory_threshold": {"500V": 0.30, "800V": 0.40},
}

_CONSENSUS_BASE = {"500V": 16.0, "800V": 16.0}
_FLEET_SIZE = 8
_CD_PREFIXES = tuple(TOOL_SPECS["cdsem"]["eqp_prefixes"])

NOW = datetime(2026, 5, 24, 9, 0, tzinfo=timezone.utc)
FETCHED_AT = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")


def _seed_for(text: str) -> int:
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _fleet_eqp_ids(fab_name: str) -> list[str]:
    """Build a deterministic CD-SEM tool pool for a fab."""
    rng = random.Random(_seed_for(f"fleet::{fab_name.upper()}"))
    fab = fab_name.upper()
    ids = [
        f"{_CD_PREFIXES[i % len(_CD_PREFIXES)]}-{fab}-{i + 1:02d}"
        for i in range(_FLEET_SIZE)
    ]
    rng.shuffle(ids)
    return ids


def _tool_cells(eqp_id: str) -> list[CellSkew]:
    """Build per (beam x axis) signed skew and provisional consensus fields."""
    rng = random.Random(_seed_for(f"cells::{eqp_id}"))
    outlier = rng.random() < 0.34
    outlier_beam = rng.choice(BEAM_CONDITIONS)
    outlier_axis = rng.choice(AXES)

    cells: list[CellSkew] = []
    for beam in BEAM_CONDITIONS:
        base = _CONSENSUS_BASE[beam]
        for axis in AXES:
            skew = round(rng.gauss(0.0, 0.12), 3)
            if outlier and beam == outlier_beam and axis == outlier_axis:
                skew = round(rng.choice([-1, 1]) * rng.uniform(0.45, 0.75), 3)
            current = round(base + skew, 3)
            cells.append({
                "beam": beam,
                "axis": axis,
                "skew": skew,
                "current_value": current,
                "median": base,
                "gap": skew,
            })
    return cells


def _epoch_history(eqp_id: str) -> list[EpochPoint]:
    """Return a few past MDC epochs for this tool's own history."""
    rng = random.Random(_seed_for(f"epoch::{eqp_id}"))
    points: list[EpochPoint] = []
    mdc = round(rng.uniform(0.990, 1.010), 4)
    for index in range(3):
        days_ago = 60 * (3 - index) + rng.randint(0, 20)
        start = NOW - timedelta(days=days_ago)
        mdc = round(mdc + rng.uniform(-0.004, 0.004), 4)
        points.append({
            "epoch_start": start.date().isoformat(),
            "mdc": mdc,
            "bsm_sharpness_avg": round(rng.uniform(7.90, 8.00), 3),
        })
    return points


def _latest_daily_bsm(eqp_id: str) -> tuple[float, float]:
    """Return most-recent daily BSM sharpness/noise averages."""
    bsm = build_bsm_data(eqp_id)
    daily = next(
        category
        for category in bsm["categories"]
        if category["key"] == "daily"
    )
    summary = daily["summary"]
    if not summary:
        return (7.95, 6.80)
    latest = summary[0]
    return (float(latest["sharpness_avg"]), float(latest["noise_avg"]))


def _latest_pm_at(eqp_id: str) -> str | None:
    """Return most-recent completed PM job_end from the BM/PM mock."""
    data = build_bm_pm_data(eqp_id, NOW)
    for row in data["past"]:
        if row.get("category") == "PM":
            return str(row["job_end"]).replace(" ", "T")
    return None


def _build_gate(eqp_id: str) -> GateBlock:
    rng = random.Random(_seed_for(f"gate::{eqp_id}"))
    spec = get_cd_monitoring_spec(eqp_id)
    value = round(spec["target"] + rng.gauss(0.0, 0.18), 3)
    cd_ok = spec["lower"] <= value <= spec["upper"]

    sharpness, noise = _latest_daily_bsm(eqp_id)
    bsm_ok = bsm_in_spec(sharpness, noise)
    verdict = "up" if cd_ok and bsm_ok else "hold"

    return {
        "cd_monitoring_value": value,
        "cd_spec_lower": spec["lower"],
        "cd_spec_upper": spec["upper"],
        "cd_in_spec": cd_ok,
        "bsm_in_spec": bsm_ok,
        "bsm_sharpness_avg": sharpness,
        "bsm_noise_avg": noise,
        "post_pm_at": _latest_pm_at(eqp_id),
        "prev_post_delta": round(rng.gauss(0.0, 0.08), 3),
        "mdc_changed": rng.random() < 0.4,
        "verdict": verdict,
    }


def _apply_fleet_median(tools: list[ToolBlock]) -> list[ConsensusCell]:
    """Replace each provisional median/gap with the fleet median per cell."""
    consensus: list[ConsensusCell] = []
    for beam in BEAM_CONDITIONS:
        for axis in AXES:
            values = [
                cell["current_value"]
                for tool in tools
                for cell in tool["cells"]
                if cell["beam"] == beam and cell["axis"] == axis
            ]
            median = round(statistics.median(values), 3) if values else _CONSENSUS_BASE[beam]
            consensus.append({"beam": beam, "axis": axis, "consensus": median})
            for tool in tools:
                for cell in tool["cells"]:
                    if cell["beam"] == beam and cell["axis"] == axis:
                        cell["median"] = median
                        cell["gap"] = round(cell["current_value"] - median, 3)
    return consensus


def get_pm_planning_fleet(fab_name: str) -> FleetPayload:
    """Return a deterministic fab-scoped CD-SEM fleet snapshot."""
    fab = fab_name.upper()
    tools: list[ToolBlock] = [
        {
            "eqp_id": eqp_id,
            "gate": _build_gate(eqp_id),
            "cells": _tool_cells(eqp_id),
            "epoch_history": _epoch_history(eqp_id),
        }
        for eqp_id in _fleet_eqp_ids(fab)
    ]
    consensus = _apply_fleet_median(tools)

    return {
        "tool_type": "cd-sem",
        "fab_name": fab,
        "fetched_at": FETCHED_AT,
        "anchor_date": NOW.date().isoformat(),
        "beam_conditions": BEAM_CONDITIONS,
        "axes": AXES,
        "defaults": DEFAULTS,
        "consensus": consensus,
        "tools": tools,
    }


if __name__ == "__main__":
    a = get_pm_planning_fleet("M14")
    b = get_pm_planning_fleet("M14")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), (
        "fleet snapshot is not deterministic"
    )
    assert len(a["tools"]) == _FLEET_SIZE
    for tool in a["tools"]:
        assert len(tool["cells"]) == len(BEAM_CONDITIONS) * len(AXES)
        assert tool["gate"]["verdict"] in ("up", "hold")

    print(
        f"fab={a['fab_name']} tools={len(a['tools'])} "
        f"beams={a['beam_conditions']} defaults={a['defaults']}"
    )
    sample = a["tools"][0]
    print(f"sample tool: {sample['eqp_id']}")
    print(
        f"  gate: verdict={sample['gate']['verdict']} "
        f"cd={sample['gate']['cd_monitoring_value']} "
        f"in[{sample['gate']['cd_spec_lower']},{sample['gate']['cd_spec_upper']}] "
        f"bsm_in_spec={sample['gate']['bsm_in_spec']}"
    )
    for cell in sample["cells"]:
        print(
            f"  {cell['beam']:>5} {cell['axis']} "
            f"skew={cell['skew']:+.3f} gap={cell['gap']:+.3f}"
        )
    print(f"consensus: {a['consensus']}")
