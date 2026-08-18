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
    """The N배화 tolerance knob's travel, in MONITOR-WAFER nanometres.

    These are not absolute nanometres, and reading them as absolute is the
    mistake this docstring exists to prevent. The client converts the knob to a
    fraction of the fab's action limit (CD의 1%) at the 15 nm monitor wafer, then
    applies that fraction against each cell's OWN measured CD — so the effective
    allowance scales with pattern size, exactly as the action limit does.

    Worked example at `max`: 0.20 nm is 1.333x the action limit, which is
    0.20 nm on the monitor wafer, 0.424 nm at a 31.8 nm CD, and 0.907 nm at
    68 nm. A cell can therefore pass a pair well above 0.20 nm without any
    ceiling having been violated.

    user-confirmed 2026-08-16, twice and in two directions: `max` stays 0.20
    (do not raise it to Kawada 2009's ±0.25), AND 0.20 is itself a monitor-wafer
    figure that scales rather than an absolute cap. Both answers are needed —
    the first alone reads as "0.20 is a hard limit", which it is not.
    """

    min: float
    max: float
    step: float


# The knob's travel and its default, declared ONCE beside the type whose
# docstring explains what the numbers mean. Both providers import these rather
# than restating them: a mock and an office adapter that disagreed about the
# slider's bounds would render the same payload against two different scales,
# and nothing about either screen would look wrong.
TOLERANCE_RANGE: ToleranceRange = {"min": 0.01, "max": 0.2, "step": 0.005}
DEFAULT_TOLERANCE = 0.05


class TttmRecipeRow(TypedDict):
    """One recipe this fab has actually MEASURED, and how much evidence it has.

    Not a catalogue entry. The recipe registry in Redis lists every recipe that
    exists, and on this screen a recipe nobody ran carries no information at
    all — picking one can only ever answer "no data". So the picker is fed from
    measurement history instead, and each row says how much history there is.
    """

    # The value to hand back as `?recipe_id=`. The `class/recipe` full_name
    # where the source carries one, because that is also the key the axis map
    # scopes by and the identity `recent_runs` contrasts within — a picker
    # offering a bare recipe_name would name something the rest of the pipeline
    # keys differently.
    recipe_id: str
    fab_name: str
    runs: int
    # Distinct tools that ran it. ONE means no pair exists, so no direct skew
    # can come out of it however many runs there are — the client dims those
    # rather than letting the user pick a recipe that cannot answer.
    tools: int


class TttmRecipeList(TypedDict):
    tool_slug: ToolSlug
    fab_name: str
    fetched_at: str
    # Descending by evidence (tools, then runs), so the recipes that can
    # actually support a comparison sort to the top of the picker.
    rows: list[TttmRecipeRow]


class TttmCheckPayload(TypedDict):
    tool_slug: ToolSlug
    fab_name: str
    recipe_id: str | None
    # The measured feature this whole payload is about. None = every parameter
    # the recipe filter left standing, folded together as before.
    #
    # Only meaningful INSIDE a recipe: a parameter name ("Para_13") is a row of
    # one recipe's idp_image_info, and the same name in another recipe measures
    # something else entirely. routes.py refuses `parameter` without
    # `recipe_id` for exactly that reason — the PAIR is the key, not the name.
    #
    # It narrows the ROWS the pairwise skew is computed from, which is why it
    # can change a group verdict rather than merely relabel one: two tools that
    # agree once every feature is folded together can disagree on one feature.
    parameter: str | None
    available: bool
    fetched_at: str
    summary: str
    tools: list[ToolRef]
    # Both are MONITOR-WAFER nm, scaled per cell by the client — see
    # ToleranceRange's docstring before treating either as an absolute limit.
    current_tolerance: float  # default 0.05 (nm at the 15 nm monitor wafer)
    tolerance_range: ToleranceRange  # {min:0.01, max:0.20, step:0.005}
    occupied_cells: list[CellSkew]
    production_corroboration: ProductionCorroboration
    fleet_today: FleetToday
    trend: list[TrendPoint]
    epoch_markers: list[EpochMarker]
    mdc_history: list[MdcHistoryEntry]
    raw: NotRequired[dict[str, object]]


# "TTTM 미반영" — production corroboration cannot be computed without a
# comparison, so the unavailable branch reports the absence rather than a level.
UNAVAILABLE_NOTE = "TTTM 미반영"


def unavailable_payload(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
    parameter: str | None,
    summary: str,
    tools: list[ToolRef],
) -> "TttmCheckPayload":
    """The documented "nothing to compare" answer — not an error.

    Hoisted beside the contract for the same reason ``TOLERANCE_RANGE`` above
    is: both providers must answer this branch identically, and they cannot be
    trusted to do so separately. This function was a ~40-line copy in each of
    `providers/mock.py` and `providers/office_example.py`, and on 2026-08-18 the
    copies diverged in the worst available way — the office template grew a
    ``tools`` parameter and a docstring promising to carry the roster, then
    returned a hardcoded ``[]``. The mock had the identical change and honoured
    it, so the whole home suite stayed green while the office served a blank
    control rail. One definition makes that unrepresentable rather than merely
    tested for.

    Echoes the fab, recipe and parameter it was asked about: the client files
    the response under the triple it requested, so blanking them here would
    label one fab's empty state with another's.

    ``tools`` is the ROSTER, and it is REQUIRED — an empty comparison is not an
    empty fab. The client builds its tool picker from this list, and that picker
    shares a rail with the recipe picker the user needs in order to leave an
    empty answer. Pass the fab's fleet on every branch; only the genuinely
    empty-roster branch (no tool of this family in this fab) passes ``[]``, and
    it does so by passing a fleet that IS empty rather than by opting out. The
    parameter is undefaulted deliberately, the same guard
    `data.get_tttm_check` uses on its own arguments: `office.py` is a gitignored
    COPY, so a copy made before this existed fails with a TypeError instead of
    silently serving a blank roster again.

    What must stay empty is the COMPARISON — `occupied_cells`, the fleet matrix
    and the trend — because that is the "comparison of nothing" this branch
    exists to refuse.
    """
    return {
        "tool_slug": tool_slug,  # type: ignore[typeddict-item]
        "fab_name": fab_name,
        "recipe_id": recipe_id,
        "parameter": parameter,
        "available": False,
        "fetched_at": "",
        "summary": summary,
        "tools": tools,
        "current_tolerance": DEFAULT_TOLERANCE,
        "tolerance_range": TOLERANCE_RANGE,  # type: ignore[typeddict-item]
        "occupied_cells": [],
        "production_corroboration": {
            "level": "low",
            "note": UNAVAILABLE_NOTE,
            "detail": [],
        },
        "fleet_today": {
            "matrix": {"tools": [], "values": []},
            "consensus_deviation": [],
            "median_cd_nm": None,
        },
        "trend": [],
        "epoch_markers": [],
        "mdc_history": [],
    }
