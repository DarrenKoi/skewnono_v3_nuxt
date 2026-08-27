"""Phase-1 TTTM mock provider — generates a fleet-shaped payload per fab.

The fleet is NOT invented here. It is `sem_list` filtered to the requested
`fab_name` and to the tool family the slug names, exactly the way
`ebeam/storage/providers/mock.py` derives its rows, so the eqp_ids the skew
screen offers for selection are the same physical tools every other screen
shows for that fab. The previous version of this module read one hand-written
fixture (`__fixtures__/tttm_cdsem_r3.json`, five tools called `EQP01…EQP05`),
which meant every fab but R3 answered `available: false` and R3 itself offered
a roster no other page had ever heard of. `__fixtures__` is still written, but
now by `scripts/capture_fixtures.py` capturing this generator's output — the
frozen shape example for the office side, not an input.

Deliberate properties of the generated payload, so a later edit does not
flatten them by accident:

- **One latent bias per tool drives everything.** `consensus_deviation`,
  `fleet_today.matrix`, every cell matrix and the trend all derive from the
  same per-tool bias, so a tool that reads high against consensus also reads
  high against each of its partners. The old fixture had the two views
  disagree (documented there as a known departure); a generator has no reason
  to, and the frontend's N배화 grouping only means something when the pairwise
  numbers actually contain clusters.
- **The last tool of the roster is the drifted one.** It sits furthest from
  consensus and carries the widest pairwise skews; the tight cluster is what
  the N배화 recommendation is built from.
- **One pair fails over most of the knob's travel** — the first tool against
  the drifted one in the `-Y-` cell, pinned at 0.24 nm. Without it the
  tolerance control has no visible negative state at all. That cell is
  `direct`/`High` on purpose, so the failure reads as real rather than as
  low-confidence noise, and it is the Y axis only — an axis-specific drift is
  more plausible than a uniform one.

  The knob is CD-relative, so "fails" is not a comparison against 0.20 nm.
  0.24 nm in a 31.8 nm CD cell is 0.755x the action limit, and the knob spans
  0.067x–1.333x, so the pair shows red from 0.010 to about 0.113 nm — roughly
  54% of the slider — and passes above that. It deliberately does NOT fail at
  full travel: with the ceiling scaling too, a pair that failed at 1.333x
  would also be past its own PM/BM limit, which would collapse the very
  distinction the next bullet exists to teach.
- **The drifted tool's row is entirely null in the predicted cell.** That is
  the "no overlapping measurement" case the frontend must not place on the
  fleet map; see `utils/fleetMap.ts`.
- **The measured cells sit at three different CDs** (32.4 / 31.8 / 68.0 nm),
  and the third is in a different `cd_band` from the other two on purpose. The
  PM/BM limit is 1% of CD, so those cells carry limits of 0.324 / 0.318 /
  0.680 nm — spread wide enough that a screen quietly reusing one absolute
  limit is visibly wrong rather than plausibly close.
- **`bc3-X-lt25-e7` has `median_cd_nm: null`.** The office may return skew
  statistics with no CD beside them, and the client has a whole assumed-CD
  path for that (`resolveNominalCd` → monitor wafer, captions saying it
  assumed). Without a null here that path is dead code at home and the first
  time it runs is at the office. Its bias scale is the smallest of the four,
  so the cell does not quietly dismantle the N배화 recommendation the rest of
  the payload is built around.
- **The over-tolerance pair is still INSIDE its own PM/BM limit.** At the
  default knob 0.24 nm is over the cell's 0.106 nm allowance yet under its
  0.318 nm action limit. The contrast is the point: the tolerance knob is a
  matching goal for N배화, the action limit is fab policy about one tool
  against consensus, and a fixture at smaller CDs would teach them as one
  number.
- **`consensus_deviation` is kept inside ±0.15 nm**, the fab's tool management
  limit — a tool outside it goes to PM/BM (user-confirmed 2026-08-16). The
  widest is the drifted tool at -0.13, so the demo fleet is "all in spec, but
  one tool is close to the edge" rather than "one tool already needs PM". The
  frontend derives that limit as 1% of `fleet_today.median_cd_nm` (15.1 nm
  here, the monitor wafer → 0.151 nm) rather than from a constant, so raising
  the fleet CD raises the limit too. Pushing a deviation past it turns that
  tool red and says PM/BM, so move these knowing what you are asserting.
- **Every tool measures every day here; the office does not.** A fab runs a
  recipe on each tool on DIFFERENT days (office 확인 2026-08-27), so the
  office adapter reads `fleet_today` — and each day of `trend` — as the fleet
  AS OF that day, each tool at its own latest run, rather than one day's rows;
  one day's rows held one tool and emptied the grouping and the trend. This mock's dates never stagger, so that path only shows at the
  office; `tests/test_office_tttm_pm_planning.py` staggers the doubles.
- **A fab with fewer than two tools answers `available: false`.** One tool is
  not a comparison, and the frontend's picker refuses to drop below two
  anyway; some HV-SEM fabs really do hold a single tool.
- **The seed includes `recipe_id` AND `parameter`**, so picking either visibly
  recomputes — which is what the pickers promise. The numbers move; the shape
  does not. The mock still never checks that a parameter belongs to the
  recipe, because at the office the filter is a WHERE on real MSR rows and an
  unknown parameter simply matches nothing. What the mock has to stand in for
  is the consequence — that narrowing to one measured feature can move a tool
  in or out of the N배화 group — and it does that by re-seeding rather than by
  filtering a feature list.
- **`parameters` is the recipe's measured feature set**, read from the
  msr_file mock's per-recipe programs (`program_parameters`) — the same
  programs its mock pickles are generated from, so the picker offers exactly
  the names 스큐보아 shows for the same recipe. The office reads the same fact
  out of the runs' pickles. Seeded by the recipe alone, never by `parameter`:
  the list is what the filter is picked from.

OFFICE-VERIFY: `beam_condition` here is "BC1"/"BC2"/"BC3", and that vocabulary is
this mock's invention. The office emits an accelerating-voltage label derived
from the pickle's `meas_condition vac` ("500V"/"800V"), which is also what the
real MDC keys are built from ("500V_HR_0Deg" — see
docs/datatables/hitachi/hardware_mdc_setting.txt). The field is a free string in
contracts.py and `cellLabel()` just concatenates it with the axis, so both
render; but home teaches a vocabulary the office does not use, and the prose in
`utils/tttmCells.ts` is written around the mock's. Renaming these to voltages
would make home and office agree — deferred because it ripples through the
captured fixture and the frontend unit tests, not because "BC1" is right.

OFFICE-VERIFY: that per-parameter skew statistics exist at the grain the office
adapter needs. `parameter` is specified against `idp_image_info.Parameter` (the
recipe-search catalogue), but whether the skew source can be sliced by it — or
only by the (beam_condition, axis, cd_band) cell it already carries — is
unconfirmed until an office run.

OFFICE-VERIFY: every number here is fabricated. Real pairwise skew magnitudes
and the true spread across cells are unknown until an office run — item 3 of
`docs/research/2026-08-16-skew-tttm-feasibility.md` section 6.

OFFICE-VERIFY: `consensus` is assumed to be the **median** (the fab states the
rule against a median). The office adapter must not use a mean — one drifted
tool would drag the reference and shift every other tool's deviation.
"""

import random
import zlib
from datetime import date, timedelta
from functools import lru_cache
from statistics import median
from typing import NamedTuple

from back_dev_home.ebeam._tool_specs import SLUG_TO_TOOL_TYPE
from back_dev_home.ebeam.tttm.contracts import (
    DEFAULT_TOLERANCE,
    TOLERANCE_RANGE,
    unavailable_payload,
    CellSkew,
    TttmRecipeList,
    TttmRecipeRow,
    ConsensusDeviation,
    EpochMarker,
    MdcHistoryEntry,
    ProductionCorroboration,
    ProductionOverlapRow,
    SkewMatrixBlock,
    ToolRef,
    TrendPoint,
    TttmCheckPayload,
)
from back_dev_home.ebeam._analysis_window import window_days
from back_dev_home.sem_list.providers.mock import get_sem_list
from back_dev_home.sem_list.roster import fleet_rows


# Frozen "today" — the mock is a demo, and a payload whose dates move with the
# wall clock makes one screenshot impossible to compare against the next.
_TODAY = date(2026, 5, 31)
_FETCHED_AT = "2026-05-31T14:30:00"

# Monitor-wafer CD behind today's fleet check. 1% of it is the ±0.151 nm PM/BM
# line the frontend draws.
_FLEET_MEDIAN_CD_NM = 15.1

# From contracts.py — the one declaration, next to the docstring that explains
# why these are monitor-wafer figures rather than absolute nanometres.
_TOLERANCE_RANGE = TOLERANCE_RANGE
_CURRENT_TOLERANCE = DEFAULT_TOLERANCE
# The one pair pinned above `_TOLERANCE_RANGE["max"]`; see the module docstring.
_BREACH_SKEW = 0.24
_DRIFTED_DEVIATION = -0.13


class _CellSpec(NamedTuple):
    cell_id: str
    beam_condition: str
    axis: str
    cd_band: str
    # None is a real case, not a gap — see the `bc3` bullet in the module
    # docstring.
    median_cd_nm: float | None
    mdc_epoch: str
    tier: str
    confidence: str
    # Multiplies every tool's bias in this cell, so the cells are not four
    # copies of one matrix.
    bias_scale: float


_CELLS: tuple[_CellSpec, ...] = (
    _CellSpec("bc1-X-25-50-e7", "BC1", "X", "25-50", 32.4, "e7", "direct", "High", 0.9),
    _CellSpec("bc1-Y-25-50-e7", "BC1", "Y", "25-50", 31.8, "e7", "direct", "High", 1.1),
    _CellSpec("bc2-X-50-100-e7", "BC2", "X", "50-100", 68.0, "e7", "predicted", "Med", 1.0),
    # The null-CD cell. Its bias scale is the smallest of the four, so the
    # cell the client judges against the strictest (assumed) limit is also the
    # one carrying the tightest skews — an unknown CD narrows the recommendation
    # rather than deleting it.
    _CellSpec("bc3-X-lt25-e7", "BC3", "X", "<25", None, "e7", "direct", "Med", 0.6),
)


def _seed(
    tool_slug: str, fab_name: str, recipe_id: str | None, parameter: str | None
) -> int:
    # crc32, not hash(): PYTHONHASHSEED is randomised per process, so hash()
    # would hand a different fleet to every worker and to every restart.
    #
    # The separator is what keeps the parts from bleeding into each other:
    # without it recipe "AB" + parameter "C" and recipe "A" + parameter "BC"
    # would seed identically, so picking a different parameter would sometimes
    # visibly do nothing.
    key = f"{tool_slug}|{fab_name.upper()}|{recipe_id or ''}|{parameter or ''}"
    return zlib.crc32(key.encode("utf-8"))


def _fleet(tool_slug: str, fab_name: str) -> list[ToolRef]:
    """The fab's roster for this tool family, straight from sem_list.

    The roster law itself (fab_name-not-fac_id, dedupe by eqp_id, sorted so
    "the last tool is the drifted one" is a stable property of the fab) lives
    in sem_list/roster.py — pm_planning's mock derives the SAME fleet from it,
    and the pm-planning page joins the two payloads by eqp_id.
    """
    tool_type = SLUG_TO_TOOL_TYPE.get(tool_slug)  # type: ignore[arg-type]
    if tool_type is None:
        return []
    return [
        ToolRef(eqp_id=row["eqp_id"], label=row["eqp_id"], eqp_model_cd=row["eqp_model_cd"])
        for row in fleet_rows(get_sem_list(), fab_name=fab_name, tool_type=tool_type)
    ]


def _biases(rng: random.Random, fleet: list[ToolRef]) -> dict[str, float]:
    """Per-tool latent skew (nm) against the fleet consensus.

    Mostly tight, a few middling, one wide — a fleet whose tools all sit the
    same distance apart has no clusters, and the whole N배화 recommendation is
    about finding the cluster.
    """
    biases: dict[str, float] = {}
    for tool in fleet:
        draw = rng.random()
        if draw < 0.6:
            spread = 0.02
        elif draw < 0.9:
            spread = 0.06
        else:
            spread = 0.11
        biases[tool["eqp_id"]] = round(rng.uniform(-spread, spread), 3)
    # The drifted tool is pinned, not drawn: the demo has to show one tool near
    # (but inside) the ±0.15 nm management limit for every fab.
    biases[fleet[-1]["eqp_id"]] = _DRIFTED_DEVIATION
    return biases


def _matrix(
    ids: list[str],
    biases: dict[str, float],
    rng: random.Random,
    scale: float,
    *,
    null_id: str | None = None,
) -> SkewMatrixBlock:
    """|bias difference| + a little noise, symmetric with a zero diagonal.

    Built triangle-first and mirrored, so symmetry is structural rather than
    something a later edit could break — the client's maximal-clique grouping
    reads both halves and would silently produce different groups.
    """
    size = len(ids)
    values: list[list[float | None]] = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1, size):
            if null_id is not None and null_id in (ids[i], ids[j]):
                # "This pair was never measured together in this cell" — null,
                # not zero, which would read as a perfect match.
                values[i][j] = values[j][i] = None
                continue
            gap = abs(biases[ids[i]] - biases[ids[j]]) * scale
            skew = round(gap + rng.uniform(0.0, 0.02), 3)
            values[i][j] = values[j][i] = skew
    return SkewMatrixBlock(tools=list(ids), values=values)


def _cells(fleet: list[ToolRef], biases: dict[str, float], seed: int) -> list[CellSkew]:
    ids = [tool["eqp_id"] for tool in fleet]
    drifted = ids[-1]
    cells: list[CellSkew] = []
    for index, spec in enumerate(_CELLS):
        rng = random.Random(seed + 101 * (index + 1))
        predicted = spec.tier == "predicted"
        block = _matrix(
            ids,
            biases,
            rng,
            spec.bias_scale,
            null_id=drifted if predicted else None,
        )
        if spec.axis == "Y":
            # The one deliberate failure, pinned after the fact so it survives
            # any change to the bias distribution.
            drifted_index = ids.index(drifted)
            block["values"][0][drifted_index] = _BREACH_SKEW
            block["values"][drifted_index][0] = _BREACH_SKEW
        cells.append(
            CellSkew(
                cell_id=spec.cell_id,
                beam_condition=spec.beam_condition,
                axis=spec.axis,  # type: ignore[typeddict-item]
                cd_band=spec.cd_band,
                median_cd_nm=spec.median_cd_nm,
                mdc_epoch=spec.mdc_epoch,
                tier=spec.tier,  # type: ignore[typeddict-item]
                confidence=spec.confidence,  # type: ignore[typeddict-item]
                labels=["특수각 포함"] if predicted else [],
                direct_skew_matrix=None if predicted else block,
                predicted_skew_matrix=block if predicted else None,
            )
        )
    return cells


def _trend(
    fleet: list[ToolRef], biases: dict[str, float], rng: random.Random, window_weeks: int
) -> list[TrendPoint]:
    """One point per (tool, day) over the whole window — the office grain.

    The span follows `window_weeks` because that is the one thing the window
    knob visibly changes at home: the office gathers more runs, so its trend
    reaches further back; the mock has no runs to gather, so it draws the same
    per-day series over the same span. It used to be five weekly points over
    four weeks regardless of the request, which made the knob a no-op here and
    taught nothing about what widening the window does at the office.
    """
    days = window_days(window_weeks)
    dates = [(_TODAY - timedelta(days=back)).isoformat() for back in range(days - 1, -1, -1)]
    return [
        TrendPoint(
            eqp_id=tool["eqp_id"],
            date=day,
            skew=round(biases[tool["eqp_id"]] + rng.uniform(-0.015, 0.015), 3),
        )
        for tool in fleet
        for day in dates
    ]


def _markers(fleet: list[ToolRef]) -> list[EpochMarker]:
    markers = [
        EpochMarker(
            eqp_id=fleet[-1]["eqp_id"],
            date=(_TODAY - timedelta(days=3)).isoformat(),
            kind="hard",
            mdc_changed=True,
            label="PM + MDC 변경 (epoch 리셋)",
        )
    ]
    if len(fleet) > 2:
        markers.append(
            EpochMarker(
                eqp_id=fleet[1]["eqp_id"],
                date=(_TODAY - timedelta(days=4)).isoformat(),
                kind="soft",
                mdc_changed=False,
                label="BM (MDC 불변)",
            )
        )
    return markers


def _mdc_history(fleet: list[ToolRef]) -> list[MdcHistoryEntry]:
    drifted = fleet[-1]["eqp_id"]
    changed_on = (_TODAY - timedelta(days=3)).isoformat()
    return [
        MdcHistoryEntry(
            eqp_id=drifted,
            beam_condition="BC1",
            axis="X",
            date=changed_on,
            old_value=1.0012,
            new_value=1.0007,
        ),
        MdcHistoryEntry(
            eqp_id=drifted,
            beam_condition="BC1",
            axis="Y",
            date=changed_on,
            old_value=1.0009,
            new_value=1.0005,
        ),
    ]


def _corroboration(fleet: list[ToolRef], biases: dict[str, float]) -> ProductionCorroboration:
    """Production overlap for the three best-matched pairs.

    OFFICE-VERIFY: production data is not TTTM data, hence the permanent
    "TTTM 미반영" note. The overlap standing in here is derived from the same
    biases, which is a fabricated correlation — at the office the two come
    from genuinely different measurements and may disagree.
    """
    ids = [tool["eqp_id"] for tool in fleet]
    pairs = sorted(
        (abs(biases[a] - biases[b]), a, b)
        for i, a in enumerate(ids)
        for b in ids[i + 1:]
    )[:3]
    return ProductionCorroboration(
        level="mid",
        note="TTTM 미반영",
        detail=[
            ProductionOverlapRow(pair=f"{a}·{b}", overlap=round(0.9 - gap * 2, 2))
            for gap, a, b in pairs
        ],
    )


@lru_cache(maxsize=32)
def _measured_recipe_ids(tool_slug: str, fab_name: str, window_weeks: int) -> frozenset[str]:
    """Every recipe_id this fab has measured in the window, as a set, computed once.

    Cached because it cannot change within a process — the meas_hist mock's rows
    are `@lru_cache`d and its window anchor is a constant — while the membership
    question is asked on EVERY check that carries a recipe, including every
    valid pick. Uncached, the happy path re-filtered 600 rows, re-aggregated the
    per-recipe run/tool counts and re-sorted them, to answer one `in`.

    Keyed by the window even though this mock's rows do not move with it: the
    question is "would the picker for THIS request have offered it", and the
    picker is windowed. Answering from another window's list is the drift the
    check/recipes pairing exists to prevent.
    """
    return frozenset(
        row["recipe_id"] for row in get_tttm_recipes(tool_slug, fab_name, window_weeks)["rows"]
    )


def _meas_hist_rows(tool_slug: str, fab_name: str) -> list[dict]:
    """The fab's measured rows for this tool family, from the meas_hist mock.

    Home stands in for the office rule rather than inventing a list: the office
    reads recipes and parameters out of `meas_hist_{cdsem,hvsem}` and the run
    pickles, and the mock reads the same facts out of the same feature's mock
    universe. A hand-written list here would make the picker offer recipes the
    check has no rows for — which is the very failure sourcing from measurement
    history exists to remove.

    Imported lazily because meas_hist's mock builds its whole universe on first
    touch, and the check endpoint has no reason to pay for that.
    """
    from back_dev_home.meas_hist.providers.mock import get_meas_hist

    tool_type = SLUG_TO_TOOL_TYPE.get(tool_slug)  # type: ignore[arg-type]
    if tool_type is None:
        return []
    return get_meas_hist(tool_type=tool_type, fab_name=fab_name.strip().upper())["rows"]


def _row_recipe_id(row: dict) -> str:
    # full_name where present, for the same reason the office uses it: it is
    # what the axis map scopes by and what runs are contrasted within.
    return row.get("full_name") or row["recipe_name"]


@lru_cache(maxsize=64)
def _measured_parameters(tool_slug: str, fab_name: str, recipe_id: str) -> tuple[str, ...]:
    """Parameters the fab measured under `recipe_id`, sorted.

    The office reads the names off the recipe's run pickles; the mock reads
    them off the programs those mock pickles are generated from. The program
    key is the bare recipe name, so every row of one recipe answers alike and
    the first match is the whole answer. Cached for the same reason
    `_measured_recipe_ids` is — the mock universe is frozen.
    """
    from back_dev_home.msr_file.providers.mock import program_parameters

    for row in _meas_hist_rows(tool_slug, fab_name):
        if _row_recipe_id(row) == recipe_id:
            return tuple(sorted(program_parameters(row["recipe_name"], row["class_name"])))
    return ()


def get_tttm_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
    parameter: str | None,
    window_weeks: int,
) -> TttmCheckPayload:
    """Deterministic pairwise skew for one fab.

    `window_weeks` is echoed and drives the trend's span (see `_trend`), and
    nothing else: the cells, matrices and confidences are seeded from the
    scope, not gathered from runs, so a wider window cannot raise a cell from
    Med to High here the way it does at the office. Deliberately NOT faked —
    a confidence that climbed with the knob would teach that the window is a
    quality dial, when at the office it is an evidence-count dial whose effect
    on confidence depends on how often each tool actually ran.
    """
    fleet = _fleet(tool_slug, fab_name)
    if not fleet:
        return unavailable_payload(
            tool_slug,
            fab_name,
            recipe_id,
            parameter,
            f"{fab_name} 에는 이 계열의 장비가 없습니다.",
            # The one branch that really has no roster — `fleet` IS empty here,
            # so the empty roster is passed rather than the argument skipped.
            # (For the record: the 2026-08-18 office incident was NOT an omitted
            # argument. Both roster-bearing branches passed `tools=fleet`; the
            # copy's function BODY returned a hardcoded `[]` and discarded it.
            # Requiring the parameter is tidiness, not the cure — one shared
            # constructor is the cure.)
            tools=fleet,
            window_weeks=window_weeks,
        )
    if len(fleet) < 2:
        return unavailable_payload(
            tool_slug,
            fab_name,
            recipe_id,
            parameter,
            f"{fab_name} 에는 이 계열 장비가 1대뿐이라 장비간 스큐를 볼 수 없습니다.",
            tools=fleet,
            window_weeks=window_weeks,
        )

    # A recipe THIS FAB HAS NOT MEASURED answers unavailable, the way the office
    # adapter does when `recent_runs` comes back empty for the recipe filter.
    # The mock used to seed a full payload from any string it was handed, so a
    # recipe nobody ran produced a confident-looking comparison at home and an
    # empty one at the office — and a stale stored recipe, which is exactly this
    # case, was invisible until someone opened the page on the company network.
    # `get_tttm_recipes` is the same measured set the picker offers, so the two
    # cannot disagree about what "measured" means.
    if recipe_id and recipe_id not in _measured_recipe_ids(tool_slug, fab_name, window_weeks):
        return unavailable_payload(
            tool_slug,
            fab_name,
            recipe_id,
            parameter,
            f"{fab_name} 에 {recipe_id} 측정 이력이 없습니다 — "
            "측정한 recipe 중에서 고르시기 바랍니다.",
            tools=fleet,
            window_weeks=window_weeks,
        )

    seed = _seed(tool_slug, fab_name, recipe_id, parameter)
    biases = _biases(random.Random(seed), fleet)
    ids = [tool["eqp_id"] for tool in fleet]

    consensus = median(biases.values())
    deviations = [
        ConsensusDeviation(eqp_id=eqp_id, deviation=round(biases[eqp_id] - consensus, 3))
        for eqp_id in ids
    ]

    cells = _cells(fleet, biases, seed)
    direct = sum(1 for cell in cells if cell["tier"] == "direct")

    return {
        "tool_slug": tool_slug,  # type: ignore[typeddict-item]
        "fab_name": fab_name,
        "recipe_id": recipe_id,
        "parameter": parameter,
        # Recipe-local, so only inside a recipe — see the contract's comment.
        "parameters": list(_measured_parameters(tool_slug, fab_name, recipe_id)) if recipe_id else [],
        "window_weeks": window_weeks,
        "available": True,
        "fetched_at": _FETCHED_AT,
        "summary": (
            f"{fab_name} 장비 그룹 {len(fleet)}대 · 점유 셀 {len(cells)}개"
            f"(직접 {direct} · 예측 {len(cells) - direct}) 기준 추천입니다."
        ),
        "tools": fleet,
        "current_tolerance": _CURRENT_TOLERANCE,
        "tolerance_range": _TOLERANCE_RANGE,  # type: ignore[typeddict-item]
        "occupied_cells": cells,
        "production_corroboration": _corroboration(fleet, biases),
        "fleet_today": {
            "matrix": _matrix(ids, biases, random.Random(seed + 7), 1.0),
            "consensus_deviation": deviations,
            "median_cd_nm": _FLEET_MEDIAN_CD_NM,
        },
        "trend": _trend(fleet, biases, random.Random(seed + 11), window_weeks),
        "epoch_markers": _markers(fleet),
        "mdc_history": _mdc_history(fleet),
    }


def get_tttm_recipes(tool_slug: str, fab_name: str, window_weeks: int) -> TttmRecipeList:
    """Recipes this fab has MEASURED, derived from the meas_hist mock.

    See `_meas_hist_rows` for why the rows come from the meas_hist mock. The
    meas_hist mock has no per-row clock to window by, so `window_weeks` is
    echoed and the rows are the same for every window — at the office the
    counts shrink with the window and a recipe can drop off the list.
    """
    fab = fab_name.strip().upper()
    runs: dict[str, int] = {}
    tools: dict[str, set[str]] = {}
    for row in _meas_hist_rows(tool_slug, fab_name):
        recipe_id = _row_recipe_id(row)
        runs[recipe_id] = runs.get(recipe_id, 0) + 1
        tools.setdefault(recipe_id, set()).add(row["eqp_id"])

    rows = [
        TttmRecipeRow(
            recipe_id=recipe_id,
            fab_name=fab,
            runs=count,
            tools=len(tools[recipe_id]),
        )
        for recipe_id, count in runs.items()
    ]
    # Most evidence first, name as the tiebreak so the order is stable.
    rows.sort(key=lambda r: (-r["tools"], -r["runs"], r["recipe_id"]))
    return TttmRecipeList(
        tool_slug=tool_slug,  # type: ignore[typeddict-item]
        fab_name=fab_name,
        window_weeks=window_weeks,
        fetched_at=_FETCHED_AT,
        rows=rows,
    )
