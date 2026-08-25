# TEMPLATE — copy to office.py at the office, then run the Verify command.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office TTTM adapter — pairwise tool skew computed from real measurements.

The mock generates a payload from one latent bias per tool. This computes the
same shape from the four sources the feasibility study confirmed are connected
(``docs/research/2026-08-16-skew-tttm-feasibility.md`` section 1):

| payload part | source |
| --- | --- |
| ``tools`` | Redis ``v3_df_sem_avail`` via ``sem_list`` |
| every skew number | ``meas_hist_{cdsem,hvsem}`` -> MinIO ``dict_pkl`` CD values |
| ``mdc_epoch``, ``mdc_history``, hard ``epoch_markers`` | Redis ``mdc_setting`` + its MinIO archive |
| soft ``epoch_markers`` | OpenSearch ``fab_inform_notes`` |

HOW A SKEW IS ACTUALLY COMPUTED HERE — four rules, each of which is a way this
screen can lie if it is dropped.

1. **One run, one number.** ``_observations`` collapses every run to a median
   before anything tool-level sees it. An MSR holds hundreds of points of one
   wafer correlated at rho ~ 0.8; counting them as independent samples shrinks a
   standard error 10-25x and reports every pair in the fab as significantly
   skewed (feasibility note section 2.4).
2. **Recipe-centred contrast, and a recipe measured by ONE tool is discarded.**
   A tool's offset is the median of its run values minus that recipe's fleet
   median. Without the discard, a tool that only ran recipes nobody else ran
   centres against itself and reports 0.000 — which reads as "matches the fleet
   perfectly" and is the single most misleading output this screen can produce.
   The skewvoir lens refuses the same case (``contrastRecipes === 0``).
3. **Never across an MDC boundary.** ``result = MDC x actual``, so an MDC edit
   moves a tool's numbers without the tool having moved. Cells are keyed by
   epoch and their window starts at the fab's most recent MDC change for that
   beam and axis — a pooled comparison across one would report the edit as a
   tool difference.
4. **Median, never mean, everywhere.** Consensus, run values, offsets and CD.
   The fab states its own rule against a median; a mean lets one drifted tool
   drag the reference and shift every other tool's deviation.

★ THREE THINGS THIS ADAPTER CANNOT KNOW YET. Each degrades visibly rather than
quietly, which is the only reason it is safe to ship them unresolved.

1. **Measurement direction (X/Y) is not in the data we read.** Neither meas_hist
   nor the pickle carries it; the MDC keys do (``500V_HR_0Deg``) but nothing
   ties a measured row to one. ``resolve_axis`` recovers it from the parameter
   NAME **within its recipe** — the same scoping ``routes.py`` enforces on the
   ``parameter`` query arg, because one recipe's ``Para_13`` is not another's —
   and returns None when it cannot — in which case those rows are dropped
   and ``occupied_cells`` comes back **empty**, with the summary saying so. It
   never defaults to "X": the contract's ``Axis`` is a two-value Literal, so a
   default would be indistinguishable from a measured fact and an axis-specific
   drift — the thing TTTM exists to find — would average itself away. Fix in one
   line at the office with ``SKEWNONO_AXIS_PARAM_MAP``.
   ``fleet_today``, ``trend`` and the markers have no axis dimension and are
   unaffected, so the page is still useful while this is unresolved.
2. **Whether ``0Deg``/``90Deg`` means image rotation or measurement direction.**
   Item 4 of the feasibility note's office checklist. ``_office_mdc.split_condition``
   is the one line to change if it is rotation.
3. **``predicted`` tier is a BRIDGE, not a second measurement.** A pair with no
   shared recipe gets its skew from the difference of two independently centred
   offsets. That estimate does not carry the lot-to-lot component, so its true
   uncertainty is wider than a direct pair's — which is why the pair lands in
   ``predicted_skew_matrix`` and is labelled, and why the client should not
   treat it as equivalent evidence.

NOT DONE HERE, deliberately: there is no nightly rollup job yet, so this
computes on request over a bounded window (``WINDOW_DAYS`` x ``RUNS_PER_TOOL``
pickles, LRU-cached). That is fine for a lab page and will not scale to a fleet
dashboard — section 5.1 of the feasibility note is the fix, and until it exists
raising either constant multiplies MinIO GETs directly.

OFFICE-VERIFY (check these once, on the first office run — the staged
``__main__`` below prints what it actually found for every one of them):

* The index aliases are ``meas_hist_cdsem`` / ``meas_hist_hvsem``
  (``_office_meas_hist.INDEX``) and the MDC archive is under
  ``hitachi_sem/cdsem/mdc_setting`` (``_office_mdc.MDC_MINIO_BASE``).
* Exact matches go through ``.keyword`` sub-fields, and ``fab_name`` is matched
  upper-cased. If any of these is mapped as a bare ``keyword``, the suffix must
  be dropped — a term query on an analyzed parent matches NOTHING and answers
  200 with an empty fleet.
* ``0Deg``/``90Deg`` really is the measurement direction and not the image
  rotation (feasibility note section 6, item 4). If it is rotation, every
  cell's ``axis`` means something else; the fix is one line in
  ``_office_mdc.split_condition``.
* A QC/matching recipe that every tool runs actually exists. Item 1 of that
  same checklist, and the most important of them: without one, no pair is
  ``direct`` and the whole grid is bridged estimates.
* The parameter names carry a resolvable direction. They usually will not
  (``Para_13`` cannot), which is what ``SKEWNONO_AXIS_PARAM_MAP`` is for.
* Real pairwise skew magnitudes. Every number the mock ships is fabricated, so
  the first office run is also the first evidence about what ``tolerance_range``
  should span (item 3 of the checklist).

At the office: fill OPENSEARCH_* / REDIS_* in ``back_dev_home/.env`` and
``minio_handler/minio_config.py``, ``cp office_example.py office.py`` (that copy
IS the switch), make sure ``sem_list`` has one too, then run MIGRATION.md's
Verify.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from itertools import combinations
from statistics import median
from typing import Any, NamedTuple

from back_dev_home.ebeam._office_bm_pm import maintenance_events
from back_dev_home.ebeam._office_mdc import MdcChange, changes as mdc_changes
from back_dev_home.ebeam._office_meas_hist import (
    EQP_ID_KW,
    FAB_NAME_KW,
    FULL_NAME_KW,
    INDEX,
    TIME_FIELD,
    composite_buckets,
    get_anchor_time,
    query as _query,
    text as _text,
)
from back_dev_home.ebeam._office_msr_cd import (
    RunRef,
    beam_label,
    cd_band,
    has_pickle_clause,
    load_points,
    recent_runs,
    resolve_axis,
)
from back_dev_home.ebeam._tool_specs import SLUG_TO_TOOL_TYPE
from back_dev_home.ebeam.tttm.contracts import (
    DEFAULT_TOLERANCE,
    TOLERANCE_RANGE,
    unavailable_payload,
    CellSkew,
    ConsensusDeviation,
    EpochMarker,
    MdcHistoryEntry,
    ProductionCorroboration,
    ProductionOverlapRow,
    SkewMatrixBlock,
    ToolRef,
    TrendPoint,
    TttmCheckPayload,
    TttmRecipeList,
    TttmRecipeRow,
)
from back_dev_home.sem_list.data import get_sem_list
from back_dev_home.sem_list.roster import fleet_rows


__all__ = ["get_tttm_check", "get_tttm_recipes"]

_LOG = logging.getLogger(__name__)


# meas_hist keeps 60 days and the dict_pkl partitions are purged at 61, so this
# is the whole history that exists. A shorter window would be a choice; this is
# the ceiling.
WINDOW_DAYS = 60

# Runs opened per tool per request. 10 x ~18 tools = ~180 MinIO GETs, cached
# across requests by `load_points`. See the "NOT DONE HERE" note above before
# raising it.
RUNS_PER_TOOL = 10

# A cell needs this many runs from its tightest participant before its estimate
# is called High rather than Med. Below it the pair difference is one or two
# wafers apart, which is a snapshot, not a reproducible offset.
HIGH_CONFIDENCE_RUNS = 6

# Trend points are per (tool, day); a fab-wide 60-day series over 18 tools is
# already ~1000 points, so the series is capped at the most recent days.
TREND_DAYS = 30

_NOTE = "TTTM 미반영"


class _Observation(NamedTuple):
    """One (run x measured feature) reduced to one CD.

    The grain is per FEATURE, not per run, and that is load-bearing for the CD
    band. One run measures several parameters at different nominal CDs — the
    feasibility note's section 3.2 turns on exactly that ("한 실행 안에 서로 다른
    공칭 CD 를 가진 parameter 가 여러 개 들어 있습니다"), because it is the only
    clean way to identify a CD-dependent gain term. A run-level median across a
    31 nm feature and a 68 nm one lands in whichever band the mixture happens to
    fall in, and every cell downstream inherits an action limit drawn for a
    pattern size nobody measured. The contract law then still passes — band and
    median came from one row set — while the band means nothing.
    """

    eqp_id: str
    msr: str            # the RUN this came from — several rows share one
    recipe_key: str     # the recipe alone: what "shared production" means
    feature: str        # the measured parameter within it
    at: datetime
    beam: str
    axis: str
    value: float

    @property
    def contrast_key(self) -> str:
        """What two tools must have in COMMON before their CDs are comparable.

        The recipe is not enough. ``Para_13`` of one recipe and ``Para_14`` of
        the same recipe are different features at different nominal CDs, so
        centring them together puts the feature-to-feature difference into the
        tool offset.
        """
        return f"{self.recipe_key}\u241f{self.feature}"


class _CellKey(NamedTuple):
    beam: str
    axis: str
    band: str
    epoch: str


# ── roster ────────────────────────────────────────────────────────────────


def _fleet(tool_slug: str, fab_name: str) -> list[ToolRef]:
    """The fab's roster for this tool family — the law in sem_list/roster.py.

    Same source and same filter as pm_planning's office adapter, because the
    pm-tune page joins the two payloads BY eqp_id and a roster derived any other
    way intersects that join toward zero.
    """
    tool_type = SLUG_TO_TOOL_TYPE.get(tool_slug)  # type: ignore[arg-type]
    if tool_type is None:
        return []
    return [
        ToolRef(
            eqp_id=str(row["eqp_id"]),
            label=str(row["eqp_id"]),
            # The picker groups its chips by the raw model code, so an adapter
            # that omitted it flattens an 18-tool fab into one unreadable row.
            eqp_model_cd=str(row.get("eqp_model_cd", "")),
        )
        for row in fleet_rows(get_sem_list(), fab_name=fab_name, tool_type=tool_type)
    ]


# ── measurements ──────────────────────────────────────────────────────────


def _observations(
    runs: tuple[RunRef, ...], parameter: str | None
) -> tuple[list[_Observation], dict[str, int]]:
    """Every (run x feature x beam x axis) median, plus a count of what fell out.

    ``parameter`` narrows to one measured feature of the recipe. It is a WHERE
    on real rows here: an unknown name simply matches nothing, which is why the
    route can accept any string without a catalogue to validate it against.
    """
    observations: list[_Observation] = []
    dropped = {"no_axis": 0, "no_parameter": 0, "no_cd": 0}
    for run in runs:
        grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        matched_parameter = False
        for point in load_points(run.pkl):
            if parameter is not None and point.parameter != parameter:
                continue
            matched_parameter = True
            if point.cd_value is None:
                dropped["no_cd"] += 1
                continue
            axis = resolve_axis(point.parameter, run.recipe_key)
            if axis is None:
                dropped["no_axis"] += 1
                continue
            grouped[(point.parameter, beam_label(point.vac), axis)].append(
                point.cd_value
            )
        if parameter is not None and not matched_parameter:
            dropped["no_parameter"] += 1
        for (feature, beam, axis), values in grouped.items():
            if not beam:
                continue  # no accelerating voltage recorded: not a beam cell
            observations.append(
                _Observation(
                    eqp_id=run.eqp_id,
                    msr=run.msr,
                    recipe_key=run.recipe_key,
                    feature=feature,
                    at=run.at,
                    beam=beam,
                    axis=axis,
                    # Rounded HERE, before anything bands it. Banding a raw
                    # 24.9997 as "<25" and only then rounding the cell median
                    # to 25.0 breaks the contract law that a median must sit
                    # inside its own band — at the edge, and only at the edge,
                    # which is exactly where nobody looks.
                    value=round(median(values), 3),
                )
            )
    return observations, dropped


def _run_observations(
    runs: tuple[RunRef, ...], parameter: str | None
) -> tuple[list[_Observation], list[str]]:
    """One row per (run x feature), with no beam or axis attached — plus the
    sorted set of every named feature the runs carry.

    The second value is the picker's catalogue (``parameters`` on the payload).
    Collected in this same walk, BEFORE the ``parameter`` filter, because it is
    deliberately unfiltered — the list is what that filter is picked from — and
    a third pass over ~1000 points per run to gather it would be pure waste.
    Read from the same pickles the skew is computed from, so a name offered is
    one the filter can match. Unnamed points (stabilisation shots) carry CDs
    but no feature identity; they are kept by ``load_points`` and must not
    surface as a blank entry.

    ``fleet_today``, ``trend`` and ``production_corroboration`` have no axis
    dimension in the contract, so they must NOT be derived from the axis-keyed
    observations: when ``resolve_axis`` cannot read a direction out of the
    parameter names, those rows are dropped and the three axis-free views would
    empty out with them. They are the part of the page that still works while
    caveat 1 is unresolved, which is only true if they are computed from here.

    Still per FEATURE, for the same reason the axis-keyed grain is — centring a
    tool on a run-level median mixes the feature spread into its offset.
    Unnamed points (a recipe's stabilisation shots) carry real CDs but no
    feature identity to contrast on, so they are excluded here while
    ``load_points`` still returns them.
    """
    rows: list[_Observation] = []
    names: set[str] = set()
    for run in runs:
        grouped: dict[str, list[float]] = defaultdict(list)
        for point in load_points(run.pkl):
            if point.parameter:
                names.add(point.parameter)
            if parameter is not None and point.parameter != parameter:
                continue
            if not point.parameter or point.cd_value is None:
                continue
            grouped[point.parameter].append(point.cd_value)
        for feature, values in grouped.items():
            rows.append(
                _Observation(
                    eqp_id=run.eqp_id,
                    msr=run.msr,
                    recipe_key=run.recipe_key,
                    feature=feature,
                    at=run.at,
                    beam="",
                    axis="",
                    value=round(median(values), 3),
                )
            )
    return rows, sorted(names)


# ── the estimator ─────────────────────────────────────────────────────────


class _Offsets(NamedTuple):
    """Per-tool offsets, the evidence each pair shares, and who is reachable."""

    offset: dict[str, float]
    recipes: dict[str, set[str]]  # tool -> the CONTRAST keys it ran
    component: dict[str, int]     # tool -> its connected component id

    def shared(self, left: str, right: str) -> set[str]:
        return self.recipes.get(left, set()) & self.recipes.get(right, set())

    def connected(self, left: str, right: str) -> bool:
        """Is there any chain of shared work joining these two tools?

        Feasibility note 3.5: "성분이 여러 개면 그 경계를 넘는 비교는 화면에서
        '비교 불가'로 막아야 합니다." Two tools in DIFFERENT components each
        centred on their own recipes' medians, and those two medians are set by
        disjoint sets of tools — so the difference between the offsets is an
        artifact of two unrelated reference points, not a skew. Shipping it as
        a `predicted` number is worse than shipping nothing, because the
        client cannot tell the two apart.
        """
        left_component = self.component.get(left)
        return left_component is not None and left_component == self.component.get(right)


def _estimate(rows: list[_Observation]) -> _Offsets:
    """Recipe-centred per-tool offsets — rule 2 of the module docstring.

    A recipe only one tool ran carries no contrast: centring it removes exactly
    the number it contributed, so it can only ever say "this tool matches
    itself". Those recipes are dropped BEFORE the offset is taken, which is why
    a tool can come back with no offset at all — the honest answer for a tool
    that shares no work with the fleet, and the one the client renders as an
    unfilled matrix row rather than as agreement.
    """
    per_pair: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        per_pair[(row.eqp_id, row.contrast_key)].append(row.value)
    tool_recipe = {key: median(values) for key, values in per_pair.items()}

    tools_by_recipe: dict[str, set[str]] = defaultdict(set)
    for eqp_id, recipe in tool_recipe:
        tools_by_recipe[recipe].add(eqp_id)
    contrast = {recipe for recipe, tools in tools_by_recipe.items() if len(tools) >= 2}

    recipe_median = {
        recipe: median(
            [tool_recipe[(eqp_id, recipe)] for eqp_id in tools_by_recipe[recipe]]
        )
        for recipe in contrast
    }

    centered: dict[str, list[float]] = defaultdict(list)
    recipes: dict[str, set[str]] = defaultdict(set)
    for (eqp_id, recipe), value in tool_recipe.items():
        if recipe not in contrast:
            continue
        centered[eqp_id].append(value - recipe_median[recipe])
        recipes[eqp_id].add(recipe)

    return _Offsets(
        offset={eqp_id: median(values) for eqp_id, values in centered.items()},
        recipes=dict(recipes),
        component=_components(recipes),
    )


def _components(recipes: dict[str, set[str]]) -> dict[str, int]:
    """Connected components of the tool graph, joined by shared contrast keys.

    Two tools are adjacent when they measured the same feature of the same
    recipe. A component is then the set of tools whose offsets are all pinned
    to one another, directly or through intermediaries — the only set within
    which a bridged comparison means anything.
    """
    by_key: dict[str, set[str]] = defaultdict(set)
    for tool, keys in recipes.items():
        for key in keys:
            by_key[key].add(tool)

    parent = {tool: tool for tool in recipes}

    def find(tool: str) -> str:
        while parent[tool] != tool:
            parent[tool] = parent[parent[tool]]
            tool = parent[tool]
        return tool

    for tools in by_key.values():
        members = sorted(tools)
        for other in members[1:]:
            root_a, root_b = find(members[0]), find(other)
            if root_a != root_b:
                parent[root_b] = root_a

    labels: dict[str, int] = {}
    return {
        tool: labels.setdefault(find(tool), len(labels)) for tool in sorted(recipes)
    }


def _matrix(
    ids: list[str], offsets: _Offsets, *, direct: bool
) -> SkewMatrixBlock | None:
    """Symmetric |offset difference| matrix over the pairs of one tier.

    Built triangle-first and mirrored so symmetry is structural: the client's
    maximal-clique grouping reads both halves and would silently produce
    different groups from an asymmetric matrix.

    ``None`` cells are "this pair is not TTTM-able in this cell" — never zero,
    which reads as a perfect match. ``None`` for the whole block means the tier
    contributed no pair at all, which the contract makes independently nullable.
    """
    size = len(ids)
    values: list[list[float | None]] = [[None] * size for _ in range(size)]
    for index in range(size):
        values[index][index] = 0.0
    filled = False
    for i, j in combinations(range(size), 2):
        left, right = ids[i], ids[j]
        if left not in offsets.offset or right not in offsets.offset:
            continue
        is_direct = bool(offsets.shared(left, right))
        if is_direct != direct:
            continue
        if not direct and not offsets.connected(left, right):
            continue  # no path joins them — see _Offsets.connected
        skew = round(abs(offsets.offset[left] - offsets.offset[right]), 3)
        values[i][j] = values[j][i] = skew
        filled = True
    if not filled:
        return None
    return SkewMatrixBlock(tools=list(ids), values=values)


# ── epochs ────────────────────────────────────────────────────────────────


def _epoch_starts(
    epochs: list[MdcChange], window_start: datetime
) -> dict[tuple[str, str], date]:
    """The most recent MDC boundary per (beam voltage, axis) in this fab.

    The MDC key carries optics too (``500V_HR``) while a measured row carries
    only its accelerating voltage, so the match is on the VOLTAGE prefix. That
    widens the boundary — an edit to the Valley setting resets the 500 V epoch
    as a whole — and widening is the safe direction: it can only refuse a
    comparison that might have been fine, never allow one that spans an edit.
    """
    starts: dict[tuple[str, str], date] = {}
    for change in epochs:
        if change.axis is None:
            continue
        voltage = change.beam_condition.split("_")[0]
        key = (voltage, change.axis)
        if change.on > starts.get(key, window_start.date()):
            starts[key] = change.on
    return starts


def _epoch_label(started: date | None) -> str:
    return f"e{started:%Y%m%d}" if started else "e0"


# ── payload assembly ──────────────────────────────────────────────────────


def _cells(
    observations: list[_Observation],
    epoch_starts: dict[tuple[str, str], date],
) -> list[CellSkew]:
    """One cell per (beam, axis, CD band, MDC epoch) with data behind it."""
    grouped: dict[_CellKey, list[_Observation]] = defaultdict(list)
    for row in observations:
        boundary = epoch_starts.get((row.beam, row.axis))
        if boundary is not None and row.at.date() < boundary:
            continue  # before this fab's last MDC edit — rule 3
        grouped[
            _CellKey(row.beam, row.axis, cd_band(row.value), _epoch_label(boundary))
        ].append(row)

    cells: list[CellSkew] = []
    for key in sorted(grouped):
        rows = grouped[key]
        ids = sorted({row.eqp_id for row in rows})
        if len(ids) < 2:
            continue  # one tool is not a comparison
        offsets = _estimate(rows)
        direct = _matrix(ids, offsets, direct=True)
        predicted = _matrix(ids, offsets, direct=False)
        if direct is None and predicted is None:
            continue  # every pair lacked contrast; an empty cell says nothing

        # Distinct RUNS, not rows. A row is one (run x feature), so a single
        # run measuring six features would otherwise clear HIGH_CONFIDENCE_RUNS
        # on its own — the pseudo-replication the estimator is careful to avoid,
        # leaking back in through the number that vouches for it.
        runs_per_tool = min(
            len({row.msr for row in rows if row.eqp_id == eqp_id}) for eqp_id in ids
        )
        if direct is not None:
            confidence = "High" if runs_per_tool >= HIGH_CONFIDENCE_RUNS else "Med"
        else:
            confidence = "Low"

        labels = [f"실행 {len({row.msr for row in rows})}건 · 장비 {len(ids)}대"]
        if direct is None:
            labels.append("공통 recipe 없음 — 브리지 추정")

        cells.append(
            CellSkew(
                cell_id=f"{key.beam}-{key.axis}-{key.band}-{key.epoch}",
                beam_condition=key.beam,
                axis=key.axis,  # type: ignore[typeddict-item]
                cd_band=key.band,
                # The band was derived from these same values, so the median
                # cannot fall outside it — which is exactly the cross-field law
                # tests/test_contract.py checks, and the reason both come from
                # one row set rather than two frames.
                median_cd_nm=round(median([row.value for row in rows]), 3),
                mdc_epoch=key.epoch,
                tier="direct" if direct is not None else "predicted",
                confidence=confidence,  # type: ignore[typeddict-item]
                labels=labels,
                direct_skew_matrix=direct,
                predicted_skew_matrix=predicted,
            )
        )
    return cells


def _fleet_today(observations: list[_Observation], roster: list[str]) -> dict[str, Any]:
    """The most recent data day: pairwise matrix, deviations and its CD.

    "Today" is the latest day the fab actually produced measurements, not the
    wall clock — a Monday request would otherwise show an empty weekend.
    """
    rows = []
    if observations:
        latest = max(row.at.date() for row in observations)
        rows = [row for row in observations if row.at.date() == latest]
    if not rows:
        return {
            "matrix": SkewMatrixBlock(tools=[], values=[]),
            "consensus_deviation": [],
            "median_cd_nm": None,
        }

    ids = [eqp_id for eqp_id in roster if any(row.eqp_id == eqp_id for row in rows)]
    offsets = _estimate(rows)
    # DIRECT pairs only. The contract gives this block no tier dimension, so a
    # bridged estimate placed here would enter the client's grouping with the
    # same standing as a measured one — the failure section 4 of the
    # feasibility note names ("2-hop 브리지 추정치가 직접 측정과 동일한 자격으로
    # clique 에 들어갑니다"). A pair with no feature in common is null, which
    # the contract already defines as "not TTTM-able", not as agreement.
    size = len(ids)
    values: list[list[float | None]] = [[None] * size for _ in range(size)]
    for index in range(size):
        values[index][index] = 0.0
    for i, j in combinations(range(size), 2):
        left, right = ids[i], ids[j]
        if (
            left in offsets.offset
            and right in offsets.offset
            and offsets.shared(left, right)
        ):
            values[i][j] = values[j][i] = round(
                abs(offsets.offset[left] - offsets.offset[right]), 3
            )

    consensus = median(offsets.offset.values()) if offsets.offset else 0.0
    return {
        "matrix": SkewMatrixBlock(tools=ids, values=values),
        "consensus_deviation": [
            ConsensusDeviation(
                eqp_id=eqp_id, deviation=round(offsets.offset[eqp_id] - consensus, 3)
            )
            for eqp_id in ids
            if eqp_id in offsets.offset
        ],
        # None unless today's measurements sit at ONE pattern size, which is
        # what the contract says this field means ("the daily fleet check runs
        # the monitor wafer"). Unfiltered, a fab's day spans a 31 nm feature and
        # a 68 nm one, and their median is a number no wafer has: the client
        # divides by 1% of it to draw the action limit, so the line would land
        # between the two sizes and be wrong for both. Returning None sends it
        # to the monitor-wafer fallback, which at least says on screen that it
        # assumed.
        "median_cd_nm": _fleet_median_cd(rows),
    }


def _fleet_median_cd(rows: list[_Observation]) -> float | None:
    """Today's fleet CD, or None when the day spans more than one CD band."""
    if len({cd_band(row.value) for row in rows}) != 1:
        return None
    value = round(median([row.value for row in rows]), 3)
    return value if value > 0 else None


def _trend(
    observations: list[_Observation], anchor: datetime
) -> list[TrendPoint]:
    """Per (tool, day) offset over the recent window.

    Each day is centred on its OWN recipe set rather than on the window's, so a
    day when the fleet happened to run a different recipe mix does not read as a
    fleet-wide step. A day with no contrast simply produces no points.
    """
    cutoff = (anchor - timedelta(days=TREND_DAYS)).date()
    by_day: dict[date, list[_Observation]] = defaultdict(list)
    for row in observations:
        if row.at.date() >= cutoff:
            by_day[row.at.date()].append(row)

    points: list[TrendPoint] = []
    for day in sorted(by_day):
        offsets = _estimate(by_day[day])
        for eqp_id, offset in sorted(offsets.offset.items()):
            points.append(
                TrendPoint(eqp_id=eqp_id, date=day.isoformat(), skew=round(offset, 3))
            )
    return points


def _markers(
    epochs: list[MdcChange], fab: str, roster: list[str], start: datetime, anchor: datetime
) -> list[EpochMarker]:
    """MDC edits (hard) and maintenance that left MDC alone (soft).

    A BM/PM on a day the tool's MDC also changed is NOT emitted as a soft
    marker: it is the same event, and two markers on one date would read as two
    interruptions of the series.
    """
    hard_dates = {(change.eqp_id, change.on) for change in epochs}
    markers: list[EpochMarker] = [
        EpochMarker(
            eqp_id=change.eqp_id,
            date=change.on.isoformat(),
            kind="hard",
            mdc_changed=True,
            label=f"MDC 변경 {change.condition} (epoch 리셋)",
        )
        for change in epochs
        if change.eqp_id in roster
    ]

    for eqp_id, events in maintenance_events(fab, roster, start, anchor).items():
        for event in events:
            if event.category not in ("BM", "PM"):
                continue
            on = event.down_at[:10]
            try:
                when = date.fromisoformat(on)
            except ValueError:
                continue
            if (eqp_id, when) in hard_dates:
                continue
            markers.append(
                EpochMarker(
                    eqp_id=eqp_id,
                    date=on,
                    kind="soft",
                    mdc_changed=False,
                    label=f"{event.category} (MDC 불변)",
                )
            )
    markers.sort(key=lambda marker: (marker["date"], marker["eqp_id"]))
    return markers


def _mdc_history(epochs: list[MdcChange], roster: list[str]) -> list[MdcHistoryEntry]:
    """Every MDC edit in the window, one row per (tool, condition, date).

    Edits whose condition suffix is not a rotation are dropped: the contract's
    ``axis`` is a two-value Literal and this row is a table the engineer reads,
    so a made-up axis would be worse than an absent row.
    """
    return [
        MdcHistoryEntry(
            eqp_id=change.eqp_id,
            beam_condition=change.beam_condition,
            axis=change.axis,  # type: ignore[typeddict-item]
            date=change.on.isoformat(),
            old_value=round(change.old_value, 4),
            new_value=round(change.new_value, 4),
        )
        for change in epochs
        if change.axis is not None and change.eqp_id in roster
    ]


def _corroboration(observations: list[_Observation]) -> ProductionCorroboration:
    """How much production the best-overlapping pairs actually share.

    Jaccard over each pair's recipe sets — a real measurement of shared work,
    where the mock derives its overlap from the same biases it derives the skew
    from (a fabricated correlation, flagged as such in its own docstring). The
    two will therefore DISAGREE between home and office, which is correct:
    production overlap and skew are independent facts at the office.

    ``TTTM 미반영`` is permanent: production data is not TTTM data, and this
    number corroborates a grouping rather than contributing to it.
    """
    recipes: dict[str, set[str]] = defaultdict(set)
    for row in observations:
        recipes[row.eqp_id].add(row.recipe_key)

    scored: list[tuple[float, str, str]] = []
    for left, right in combinations(sorted(recipes), 2):
        union = recipes[left] | recipes[right]
        if not union:
            continue
        scored.append((len(recipes[left] & recipes[right]) / len(union), left, right))
    scored.sort(reverse=True)
    top = scored[:3]

    if not top:
        level = "low"
    else:
        best = top[0][0]
        level = "high" if best >= 0.6 else "mid" if best >= 0.25 else "low"

    return ProductionCorroboration(
        level=level,  # type: ignore[typeddict-item]
        note=_NOTE,
        detail=[
            ProductionOverlapRow(pair=f"{left}·{right}", overlap=round(score, 2))
            for score, left, right in top
        ],
    )


def _empty_cells_summary(
    fab_name: str,
    fleet_size: int,
    dropped: dict[str, int],
    rows: list[_Observation],
) -> str:
    """Why ``occupied_cells`` is empty, in the words that name the fix.

    Three distinct causes reach here and none of them is visible on screen:
    the parameter matched no row, no parameter carried a resolvable direction,
    or every recipe was run by a single tool so nothing had contrast. Blaming
    the axis for all three sends the next person to the wrong env var.
    """
    head = f"{fab_name} 장비 그룹 {fleet_size}대 · "
    tail = "장비 그룹 비교는 아래 fleet 지표로 보시기 바랍니다."
    if dropped["no_parameter"] and not rows:
        return (
            f"{head}선택한 parameter 를 측정한 이력이 없어 셀별 스큐를 "
            f"계산하지 못했습니다. {tail}"
        )
    if dropped["no_axis"] and not rows:
        _LOG.warning(
            "tttm: %d measured rows in %s had no resolvable axis; "
            "occupied_cells is empty. Set SKEWNONO_AXIS_PARAM_MAP.",
            dropped["no_axis"], fab_name,
        )
        return (
            f"{head}측정 방향(X/Y)을 확인할 수 없어 셀별 스큐를 계산하지 "
            f"못했습니다. {tail}"
        )
    _LOG.info(
        "tttm: %s has %d observations but no cell survived — no recipe and "
        "feature was measured by two tools in one epoch.",
        fab_name, len(rows),
    )
    return (
        f"{head}두 대 이상이 함께 측정한 recipe·parameter 가 없어 장비간 "
        f"비교가 성립하지 않습니다. {tail}"
    )


def get_tttm_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
    parameter: str | None,
) -> TttmCheckPayload:
    """Pairwise tool skew for one fab, optionally narrowed to one feature.

    ``parameter`` narrows the ROWS the skew is computed from to one measured
    feature of ``recipe_id``; it is never meaningful on its own, and the route
    refuses it without a recipe, so a non-null ``parameter`` always arrives with
    one. Both are echoed back — including on every unavailable branch.
    """
    fleet = _fleet(tool_slug, fab_name)
    if not fleet:
        return unavailable_payload(
            tool_slug, fab_name, recipe_id, parameter,
            f"{fab_name} 에는 이 계열의 장비가 없습니다.",
            # `fleet` IS empty here, so the empty roster is passed rather than
            # omitted — see unavailable_payload's docstring.
            tools=fleet,
        )
    if len(fleet) < 2:
        return unavailable_payload(
            tool_slug, fab_name, recipe_id, parameter,
            f"{fab_name} 에는 이 계열 장비가 1대뿐이라 장비간 스큐를 볼 수 없습니다.",
            tools=fleet,
        )

    roster = [tool["eqp_id"] for tool in fleet]
    anchor = get_anchor_time()
    start = anchor - timedelta(days=WINDOW_DAYS)
    runs = recent_runs(
        SLUG_TO_TOOL_TYPE[tool_slug],  # type: ignore[index]
        fab_name,
        roster,
        start,
        anchor,
        recipe=recipe_id,
        per_tool=RUNS_PER_TOOL,
    )
    if not runs.runs:
        scope = f"{recipe_id} " if recipe_id else ""
        return unavailable_payload(
            tool_slug, fab_name, recipe_id, parameter,
            f"{fab_name} 에 최근 {WINDOW_DAYS}일간 {scope}측정 이력이 없습니다.",
            tools=fleet,
        )

    cell_rows, dropped = _observations(runs.runs, parameter)
    fleet_rows_, measured_names = _run_observations(runs.runs, parameter)
    epochs = mdc_changes(fab_name, start, anchor)
    cells = _cells(cell_rows, _epoch_starts(epochs, start))

    direct = sum(1 for cell in cells if cell["tier"] == "direct")
    if cells:
        summary = (
            f"{fab_name} 장비 그룹 {len(fleet)}대 · 점유 셀 {len(cells)}개"
            f"(직접 {direct} · 예측 {len(cells) - direct}) 기준 추천입니다."
        )
    else:
        # An empty grid has three causes that render identically, and the user
        # reads all three as "these tools all match". Each one says which.
        summary = _empty_cells_summary(fab_name, len(fleet), dropped, cell_rows)

    return {
        "tool_slug": tool_slug,  # type: ignore[typeddict-item]
        "fab_name": fab_name,
        "recipe_id": recipe_id,
        "parameter": parameter,
        # Recipe-local names, so only inside a recipe: without one the runs
        # span every measured recipe and a pooled list would offer one name for
        # several different features. See the contract's field comment.
        "parameters": measured_names if recipe_id else [],
        "available": True,
        "fetched_at": anchor.isoformat(timespec="seconds"),
        "summary": summary,
        "tools": fleet,
        "current_tolerance": DEFAULT_TOLERANCE,
        "tolerance_range": TOLERANCE_RANGE,  # type: ignore[typeddict-item]
        "occupied_cells": cells,
        "production_corroboration": _corroboration(fleet_rows_),
        "fleet_today": _fleet_today(fleet_rows_, roster),  # type: ignore[typeddict-item]
        "trend": _trend(fleet_rows_, anchor),
        "epoch_markers": _markers(epochs, fab_name, roster, start, anchor),
        "mdc_history": _mdc_history(epochs, roster),
        # Diagnostics, not display data. `raw` is NotRequired by contract and
        # the client ignores it; it is here so an office run can tell an empty
        # grid caused by the axis gap from one caused by a recipe filter that
        # matched nothing, without re-running the module's __main__.
        "raw": {
            "window": [start.isoformat(), anchor.isoformat()],
            "runs": len(runs.runs),
            "runs_truncated_for": list(runs.truncated),
            "observations": {"cells": len(cell_rows), "fleet": len(fleet_rows_)},
            "dropped": dropped,
        },
    }


if __name__ == "__main__":  # pragma: no cover
    # Staged office diagnostic — run FROM THE REPO ROOT:
    #   .venv/bin/python -m back_dev_home.ebeam.tttm.providers.office cdsem R3
    #   .venv/bin/python -m ...tttm.providers.office cdsem R3 ADI/ADI_CD_BIAS_001
    #
    # Each stage prints what survived it, because "no cells" has four possible
    # causes that look identical on screen: no runs, no CD values, no resolvable
    # axis, and no recipe measured by two tools. The stage that drops to 0 IS
    # the answer.
    import sys

    from back_dev_home.ebeam._office_msr_cd import AXIS_ENV_VAR

    slug = sys.argv[1] if len(sys.argv) > 1 else "cdsem"
    fab = sys.argv[2] if len(sys.argv) > 2 else "R3"
    recipe = sys.argv[3] if len(sys.argv) > 3 else None
    param = sys.argv[4] if len(sys.argv) > 4 else None

    print(f"slug={slug} fab={fab} recipe={recipe!r} parameter={param!r}")

    print("\n--- 1. roster ---")
    tools = _fleet(slug, fab)
    print(f"  {len(tools)} tools: {[t['eqp_id'] for t in tools][:8]}")
    if len(tools) < 2:
        print("  fewer than two tools — the payload is `available: false` by design.")
        sys.exit(0)

    ids_ = [t["eqp_id"] for t in tools]
    anchor_ = get_anchor_time()
    start_ = anchor_ - timedelta(days=WINDOW_DAYS)
    print(f"  window {start_.date()} .. {anchor_.date()}")

    print("\n--- 2. runs ---")
    found = recent_runs(
        SLUG_TO_TOOL_TYPE[slug],  # type: ignore[index]
        fab, ids_, start_, anchor_, recipe=recipe, per_tool=RUNS_PER_TOOL,
    )
    print(f"  {len(found.runs)} runs across {len(found.by_tool())} tools")
    print(f"  recipes: {sorted({run.recipe_key for run in found.runs})[:12]}")
    if found.truncated:
        print(f"  capped at {RUNS_PER_TOOL}/tool for {list(found.truncated)}")
    if not found.runs:
        sys.exit(1)

    print("\n--- 3. observations (pickles -> beam x axis medians) ---")
    obs, drops = _observations(found.runs, param)
    print(f"  {len(obs)} observations; dropped={drops}")
    if drops["no_axis"]:
        # Across EVERY run, not a sample: the naming varies per recipe, so a
        # three-run peek would send you back for a second pass.
        # Keyed by (recipe, parameter), because that PAIR is what an axis
        # belongs to — the same name under another recipe is another feature.
        pairs = sorted({
            (run.recipe_key, point.parameter)
            for run in found.runs
            for point in load_points(run.pkl)
            if point.parameter
            and resolve_axis(point.parameter, run.recipe_key) is None
        })
        print(f"  ★ {len(pairs)} (recipe, parameter) pair(s) with no direction:")
        for recipe_key, name in pairs:
            print(f"      {recipe_key:<32} {name}")
        print("    Paste this into back_dev_home/.env, correcting each axis:")
        print(
            f"    {AXIS_ENV_VAR}="
            + ",".join(f"{recipe_key}:{name}=X" for recipe_key, name in pairs)
        )
        print("    Globs work on both halves — e.g. ADI/*:*_HOR=X,*_VER=Y —")
        print("    and drop the 'recipe:' prefix for a rule that is fab-wide.")
    print(f"  beams: {sorted({o.beam for o in obs})}  axes: {sorted({o.axis for o in obs})}")

    print("\n--- 4. epochs + cells ---")
    changes_ = mdc_changes(fab, start_, anchor_)
    print(f"  {len(changes_)} MDC changes; boundaries={_epoch_starts(changes_, start_)}")
    built = _cells(obs, _epoch_starts(changes_, start_))
    print(f"  {len(built)} cells")
    for cell in built[:6]:
        print(
            f"    {cell['cell_id']:<28} tier={cell['tier']:<9} "
            f"conf={cell['confidence']:<4} cd={cell['median_cd_nm']}"
        )
    if obs and not built:
        print("  ★ observations exist but no cell survived — every recipe was run")
        print("    by a single tool, so nothing has contrast (rule 2).")

    print("\n--- 5. payload ---")
    result = get_tttm_check(slug, fab, recipe, param)
    print(f"  available={result['available']} cells={len(result['occupied_cells'])} "
          f"trend={len(result['trend'])} markers={len(result['epoch_markers'])}")
    print(f"  fleet_today.median_cd_nm={result['fleet_today']['median_cd_nm']}")
    print(f"  summary: {result['summary']}")


# ── the picker's recipe list ──────────────────────────────────────────────

# Only a run whose MSR landed can contribute CD values, and this list exists to
# offer recipes the check can actually answer for — so it filters exactly the
# way `recent_runs` does, through the SAME shared clause rather than a second
# spelling of it. A picker scoped more loosely than the payload it drives
# offers recipes that then come back empty, and that drift is invisible: the
# rows still render, they just resolve to nothing once selected.


def get_tttm_recipes(tool_slug: str, fab_name: str) -> TttmRecipeList:
    """Recipes this fab has MEASURED, with the evidence behind each.

    Deliberately NOT the Redis recipe registry (`v3_*_unique_rcp_list`), which
    recipe-search reads. That registry lists every recipe that EXISTS; on this
    screen a recipe nobody ran carries no information, and offering it can only
    ever answer "no data". The measured set is a fraction of the catalogue and
    is the only part worth showing here.

    One composite walk, not a `terms` agg: a fab's recipe count is unbounded, and
    `terms` truncates at `size` silently. `cardinality` on the tool axis is
    approximate by design, but it is approximate at cardinalities far above the
    ~20 tools a fab holds, so the "can this recipe support a pair at all"
    question it answers here is exact in practice.
    """
    tool_type = SLUG_TO_TOOL_TYPE.get(tool_slug)  # type: ignore[arg-type]
    fab = fab_name.strip().upper()
    fetched_at = get_anchor_time().isoformat(timespec="seconds")
    if tool_type is None:
        return TttmRecipeList(
            tool_slug=tool_slug,  # type: ignore[typeddict-item]
            fab_name=fab_name,
            fetched_at=fetched_at,
            rows=[],
        )

    anchor = get_anchor_time()
    start = anchor - timedelta(days=WINDOW_DAYS)
    clauses: list[dict[str, Any]] = [
        {"term": {FAB_NAME_KW: fab}},
        has_pickle_clause(),
        {
            "range": {
                TIME_FIELD: {
                    "gte": start.strftime("%Y-%m-%dT%H:%M:%S"),
                    "lte": anchor.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            }
        },
    ]
    buckets = composite_buckets(
        INDEX[tool_type],
        FULL_NAME_KW,
        {"tools": {"cardinality": {"field": EQP_ID_KW}}},
        _query(clauses),
    )

    rows = [
        TttmRecipeRow(
            recipe_id=recipe_id,
            fab_name=fab,
            runs=int(bucket.get("doc_count", 0)),
            tools=int(bucket.get("tools", {}).get("value", 0)),
        )
        for bucket in buckets
        if (recipe_id := _text(bucket.get("key", {}).get("group")))
    ]
    rows.sort(key=lambda row: (-row["tools"], -row["runs"], row["recipe_id"]))
    return TttmRecipeList(
        tool_slug=tool_slug,  # type: ignore[typeddict-item]
        fab_name=fab_name,
        fetched_at=fetched_at,
        rows=rows,
    )
