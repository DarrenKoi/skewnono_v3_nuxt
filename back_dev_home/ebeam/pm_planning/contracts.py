"""Canonical pm-planning API contract.

The fleet snapshot carries per-tool Up-gate inputs and per-cell signed skew.
Ranking, threshold filtering, and bottom-N selection are client-side concerns,
so this contract ships raw values plus defaults instead of pre-ranked results.
"""

from typing import Literal, TypedDict


BeamCondition = Literal["500V", "800V"]
ScanAxis = Literal["X", "Y"]
GateVerdict = Literal["up", "hold"]


class GateBlock(TypedDict):
    cd_monitoring_value: float
    cd_spec_lower: float
    cd_spec_upper: float
    cd_in_spec: bool
    bsm_in_spec: bool
    bsm_sharpness_avg: float
    bsm_noise_avg: float
    post_pm_at: str | None
    prev_post_delta: float | None
    mdc_changed: bool
    verdict: GateVerdict


class CellSkew(TypedDict):
    beam: BeamCondition
    axis: ScanAxis
    skew: float
    current_value: float
    median: float
    gap: float


class EpochPoint(TypedDict):
    epoch_start: str
    mdc: float
    bsm_sharpness_avg: float


class ToolBlock(TypedDict):
    eqp_id: str
    gate: GateBlock
    cells: list[CellSkew]
    epoch_history: list[EpochPoint]


class ConsensusCell(TypedDict):
    beam: BeamCondition
    axis: ScanAxis
    consensus: float


class FleetDefaults(TypedDict):
    focus_n: int
    advisory_threshold: dict[str, float]


class FleetPayload(TypedDict):
    tool_type: str
    fab_name: str
    fetched_at: str
    anchor_date: str
    # How far back the monitor runs, BSM readings and PM events were gathered,
    # in weeks — echoed from `?window_weeks=` (one of
    # `_analysis_window.WINDOW_WEEKS_CHOICES`). pm-tune shares this axis with
    # the tttm check it joins against, so the two halves of that page describe
    # one span.
    window_weeks: int
    beam_conditions: list[BeamCondition]
    axes: list[ScanAxis]
    defaults: FleetDefaults
    consensus: list[ConsensusCell]
    tools: list[ToolBlock]
