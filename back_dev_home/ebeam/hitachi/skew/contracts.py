"""Canonical tool-to-tool skew API contract (Phase-1).

The route returns RAW per-cell pairwise skew matrices + a current tolerance.
The client computes N배화 (maximal-clique) grouping; the server never groups.
Office swaps `data.py` to produce these same shapes from real statistics.
"""

from typing import Literal, NotRequired, TypedDict


ToolSlug = Literal["cdsem", "hvsem"]
Tier = Literal["direct", "predicted"]
Confidence = Literal["High", "Med", "Low"]
Axis = Literal["X", "Y"]
ProductionLevel = Literal["high", "mid", "low"]
EpochKind = Literal["hard", "soft"]


class ToolRef(TypedDict):
    eqp_id: str
    label: str


class SkewMatrixBlock(TypedDict):
    # `tools` indexes both axes of `values`. `values` is symmetric, diagonal 0.
    # A null cell means that tool-pair has no data in this cell (not TTTM-able).
    tools: list[str]
    values: list[list[float | None]]


class CellSkew(TypedDict):
    cell_id: str
    beam_condition: str
    axis: Axis
    cd_band: str  # one of "<25" | "25-50" | "50-100" | "100-200" | ">=200"
    mdc_epoch: str
    tier: Tier
    confidence: Confidence
    labels: list[str]  # e.g. ["특수각 포함"] — informational flags
    direct_skew_matrix: SkewMatrixBlock | None
    predicted_skew_matrix: SkewMatrixBlock | None


class ProductionOverlapRow(TypedDict):
    pair: str  # "EQP01·EQP02"
    overlap: float  # 0..1 distribution-overlap score


class ProductionCorroboration(TypedDict):
    level: ProductionLevel
    note: str  # always "TTTM 미반영"
    detail: list[ProductionOverlapRow]


class ConsensusDeviation(TypedDict):
    eqp_id: str
    deviation: float  # tool − consensus (nm), signed


class FleetToday(TypedDict):
    matrix: SkewMatrixBlock
    consensus_deviation: list[ConsensusDeviation]


class TrendPoint(TypedDict):
    eqp_id: str
    date: str  # YYYY-MM-DD
    skew: float


class EpochMarker(TypedDict):
    eqp_id: str
    date: str
    kind: EpochKind  # hard = MDC changed (epoch reset); soft = BM/PM, MDC unchanged
    mdc_changed: bool
    label: str


class MdcHistoryEntry(TypedDict):
    eqp_id: str
    beam_condition: str
    axis: Axis
    date: str
    old_value: float
    new_value: float


class ToleranceRange(TypedDict):
    min: float
    max: float
    step: float


class SkewCheckPayload(TypedDict):
    tool_slug: ToolSlug
    fab_id: str
    recipe_id: str | None
    available: bool
    fetched_at: str
    summary: str
    tools: list[ToolRef]
    current_tolerance: float  # default 0.05 (nm)
    tolerance_range: ToleranceRange  # {min:0.01, max:0.20, step:0.005}
    occupied_cells: list[CellSkew]
    production_corroboration: ProductionCorroboration
    fleet_today: FleetToday
    trend: list[TrendPoint]
    epoch_markers: list[EpochMarker]
    mdc_history: list[MdcHistoryEntry]
    raw: NotRequired[dict[str, object]]
