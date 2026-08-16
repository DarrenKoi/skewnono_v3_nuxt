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
    # Model code as sem_list carries it (e.g. "CG6300", "TP4500").
    #
    # The picker groups its chips by this, because a fab holds up to ~18
    # CD-SEMs and matching tools by series is how a skew comparison is
    # actually scoped — the useful selection is rarely an arbitrary subset.
    # It is the raw code, not a family label: `model_to_tool_type()` answers
    # "cd-sem" for every CG and GT alike, so classifying here would collapse
    # the very distinction the grouping exists to show.
    eqp_model_cd: str


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
    # Median measured CD (nm) over the MSR rows this cell was built from, or
    # None when no CD came back with the skew statistics.
    #
    # This is the field that makes cells at different pattern sizes comparable.
    # The fab's tool-management limit is a RATIO of CD (1% — the familiar
    # ±0.15 nm is that ratio at the 15 nm monitor wafer), so a screen drawing
    # one absolute nm line across every cell is wrong by the CD ratio, roughly
    # 4x too strict in the 50-100 band. `cd_band` cannot stand in for it: a
    # band is a bucket, and 50-100 alone spans a 2x range of limits.
    #
    # Must fall inside `cd_band` when both are present — tests/test_contract.py
    # enforces that, because a median outside its own band means the two were
    # derived from different row sets.
    median_cd_nm: float | None
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
    # Median measured CD (nm) behind today's fleet numbers, or None if unknown.
    #
    # Unlike `CellSkew.median_cd_nm` this is a whole-fleet aggregate, so it only
    # means anything when today's measurements sit at one pattern size — which
    # is the normal case, because the daily fleet check runs the monitor wafer.
    # That is also where ±0.15 nm comes from: 1% of a ~15 nm CD. Under a recipe
    # filter it becomes that recipe's CD, and the PM/BM line moves with it.
    median_cd_nm: float | None


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


class TttmCheckPayload(TypedDict):
    tool_slug: ToolSlug
    fab_name: str
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
