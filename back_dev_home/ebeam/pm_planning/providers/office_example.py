# TEMPLATE — copy to office.py at the office, then run the Verify command.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office pm-planning adapter — one fab's CD-SEM Up-gate snapshot from real data.

Five payload parts, four sources, all already connected for other features and
joined on ``eqp_id``:

| payload part | source | via |
| --- | --- | --- |
| the roster | Redis ``v3_df_sem_avail`` | ``sem_list.data`` + ``sem_list.roster`` |
| ``gate.cd_monitoring_value``, ``cells`` | ``meas_hist_cdsem`` -> MinIO ``dict_pkl`` | ``_office_msr_cd`` |
| ``gate.bsm_*`` | OpenSearch ``beam_shape_cdsem`` | this module |
| ``gate.post_pm_at`` | OpenSearch ``fab_inform_notes`` | ``_office_bm_pm`` |
| ``gate.mdc_changed``, ``epoch_history`` | Redis ``mdc_setting`` + MinIO archive | ``_office_mdc`` |

``providers/mock.py`` composes the same five from hardware's MOCK generators
(``pm_gate_bsm_mock``, ``bm_pm/mock``, ``spec_range_mock``). This module does
NOT import hardware's office adapters in return, for two reasons: they are
gitignored copies, so pm_planning would break on any machine where hardware had
not been ``cp``-ed; and they answer per-TOOL questions, while a fleet snapshot
wants one aggregation over ~18 tools rather than 18 round trips.

★ THREE THINGS THE MOCK KNOWS THAT THE OFFICE DOES NOT. Read these before
reading a number off this screen.

1. **CD monitoring is several recipes, found by prefix — not a configured
   name.** Each fab runs its own under its own name, and they all begin
   ``CD_MONITOR`` (user-confirmed 2026-08-18). They run periodically on the same
   tool with the same recipe, so their executions are ordinary meas_hist
   documents needing no separate source, and the default ``CD_MONITOR*``
   wildcard finds them. ``SKEWNONO_CD_MONITOR_RECIPE`` therefore usually needs
   no setting; reach for it only when a fab names one outside the prefix, or
   when a fab runs SEVERAL monitor recipes at different pattern sizes and
   pooling them would average two CDs into one gate reading. ``__main__``
   stage 2 prints what matched.

2. **The CD spec window is DERIVED, not ingested.** ``spec_range_mock`` uses a
   fabricated ±0.5 nm per tool. Here the window is the fleet's own median ±1%,
   because 1% of CD is the fab's stated action limit for one tool against
   consensus (user-confirmed 2026-08-16: ±0.15 nm at the 15 nm monitor wafer)
   and it is the only spec rule this repo actually knows. A real ingested spec
   should replace ``_cd_spec``; until then ``cd_in_spec`` means "agrees with its
   siblings", not "inside the fab's recorded window".

3. **The BSM acceptance band is RELATIVE, and deliberately not the mock's.**
   ``spec_range_mock.bsm_in_spec`` tests noise against 6.65–6.95, a band
   invented alongside ``pm_gate_bsm_mock``. The real sample doc in
   ``docs/datatables/hitachi/hardware_beam_shape.txt`` has ``Ave. Noise`` at 6.277 —
   outside it. Importing that band would mark every tool in the fab out of spec
   and hold the whole fleet, on a threshold nobody at the fab ever stated. So
   ``bsm_in_spec`` here is a robust outlier test against the fab's own fleet
   (median ± 3 x MAD per metric). Replace it the day a real band lands; do NOT
   "fix" it back to the mock's constants.

Volatile fields: ``fetched_at`` is stamped per request and ``anchor_date``
follows meas_hist ingestion, where the mock freezes both at
``2026-05-24T09:00:00Z``. A parity harness must scrub them rather than compare.

OFFICE-VERIFY (check these once, on the first office run — the staged
``__main__`` below prints what it actually found for every one of them):

* That this fab's CD-monitoring recipes really do start with ``CD_MONITOR``,
  and that there is only ONE pattern size among the ones that matched. Stage 2
  lists what the prefix found; if two monitor recipes measure different CDs,
  pin one with ``SKEWNONO_CD_MONITOR_RECIPE``.
* The index aliases ``beam_shape_cdsem`` and ``fab_inform_notes``, and that
  exact matches go through ``.keyword`` sub-fields with ``fab_name``
  upper-cased. A term query on an analyzed parent matches NOTHING and answers
  200 with an empty gate.
* That BSM sharpness is the mean of the ``Reso EB`` profile. The metric
  registry has an ``Ave. Noise`` scalar but no ``Ave. Reso EB``, so noise is
  read and sharpness is averaged — confirm the fab reads them the same way.
* Whether ``fab_inform_notes`` stores offset-less KST wall clock like the
  meas_hist indices. A stored ``Z`` slides ``post_pm_at`` by nine hours, which
  moves the before/after split behind ``prev_post_delta``.
* That the fleet-relative substitutes in note 2 and note 3 above are acceptable
  as an interim, and what the real CD spec window and BSM band are when they
  are found.

At the office: fill OPENSEARCH_* / REDIS_* in ``back_dev_home/.env`` and
``minio_handler/minio_config.py``, ``cp office_example.py office.py`` (that copy
IS the switch), make sure ``sem_list`` has one too, then run MIGRATION.md's
Verify.
"""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home.ebeam._office_bm_pm import latest_pm_by_tool, maintenance_events
from back_dev_home.ebeam._office_mdc import MdcChange, changes as mdc_changes
from back_dev_home.ebeam._office_meas_hist import (
    EQP_ID_KW,
    FAB_NAME_KW,
    KST,
    MAX_INNER_RESULT_WINDOW,
    aggregate,
    get_anchor_time,
    parse_dt,
    query as _query,
    text as _text,
    top_hits as _top_hits,
)
from back_dev_home.ebeam._analysis_window import DEFAULT_WINDOW_WEEKS, window_days
from back_dev_home.ebeam._office_msr_cd import (
    Point,
    RunRef,
    as_float as _as_float,
    beam_label,
    load_points,
    monitor_recipe_pattern,
    recent_runs,
    resolve_axis,
    run_median,
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
from back_dev_home.sem_list.data import get_sem_list
from back_dev_home.sem_list.roster import fleet_rows


__all__ = ["BEAM_CONDITIONS", "AXES", "DEFAULTS", "get_pm_planning_fleet"]

_LOG = logging.getLogger(__name__)


# The grid the contract advertises. A 3000 V run is real but has nowhere to go
# in a Literal["500V", "800V"], so it is dropped from `cells` (and said so in
# the log) rather than folded into one of these — averaging two beams together
# is the one thing a beam-keyed grid exists to prevent.
BEAM_CONDITIONS: list[BeamCondition] = ["500V", "800V"]
AXES: list[ScanAxis] = ["X", "Y"]

# Client-side ranking knobs; the backend ships raw values, per MIGRATION.md.
# Same numbers as the mock: these are UI defaults, not measurements.
DEFAULTS = {
    "focus_n": 3,
    "advisory_threshold": {"500V": 0.30, "800V": 0.40},
}

# How far back a "current" CD reading or BSM reading may come from is the
# request's `window_weeks` (`_analysis_window.py`, 1-4 weeks, shared with the
# tttm check that pm-tune joins this payload against). A tool idle for longer
# than the window drops out of the fleet — that is the window meaning what its
# label says, not a gap. It used to be a fixed 30 days. PM EVENTS are not
# windowed — see PM_LOOKBACK_DAYS below.

# Monitor runs opened per tool per WEEK of the window. 8/week holds a PM
# boundary (so `prev_post_delta` has a before AND an after) IF the monitor runs
# daily (OFFICE-VERIFY — meas_hist.txt only says CD_MONITOR recipes run
# 주기적으로); at the widest window that is 32 x ~18 tools = ~580 MinIO GETs.
# Scaled with the window for the reason tttm's cap is: a fixed cap behind a
# widening lookback makes the cap the real window.
RUNS_PER_TOOL_PER_WEEK = 8


def runs_per_tool(window_weeks: int) -> int:
    return RUNS_PER_TOOL_PER_WEEK * window_weeks


# How far back to look for the tool's last PM. Deliberately NOT the request
# window, and unchanged from before the window became selectable: `post_pm_at`
# answers "when was this tool last touched", which is a fact about the tool and
# not about how much evidence the user asked for. Windowed, a PM three weeks
# ago vanished at the 2-week default — `post_pm_at` went None, `prev_post_delta`
# with it, and pm-tune's "freshest out of PM" default pick moved — which the
# window request never asked for (oc-review 2026-08-26). Same reasoning as the
# MDC lookback below, at the span the 30-day window used to give it.
PM_LOOKBACK_DAYS = 30

# How far back to look for MDC epoch boundaries. Deliberately NOT the request
# window: MDC "자주 바뀌지는 않는다" (docs/datatables/hitachi/hardware_mdc_setting.txt)
# and the mock's own epoch_history spaces its three points 60+ days apart, so a
# weeks-long lookback would leave nearly every tool with an empty history and
# make the `mdc_changed` badge read as "never changed" rather than "not in the
# window". The archive walk is date-partitioned and cached, so the longer
# window costs one pass per fab per process.
EPOCH_LOOKBACK_DAYS = 240

# The fab's action limit for one tool against consensus, as a fraction of CD.
# user-confirmed 2026-08-16 — the familiar ±0.15 nm at the 15 nm monitor wafer
# IS this ratio. Not a guess, and not the mock's ±0.5 nm.
ACTION_LIMIT_RATIO = 0.01

# ── BSM (beam_shape_cdsem) ────────────────────────────────────────────────
# Same index and selectors as hardware/providers/bsm; the schema and the
# .keyword rules are in docs/datatables/hitachi/hardware_beam_shape.txt.
BSM_INDEX = "beam_shape_cdsem"
BSM_TYPE_KW = "type.keyword"
BSM_CATEGORY_KW = "fdc_category.keyword"
BSM_DOC_TYPE = "total"
BSM_FDC_CATEGORY = "bsi_beam_shape"
BSM_TIME = "timestamp"
# "Sharpness" is the Reso EB profile's own average — the metric registry has an
# `Ave. Noise` scalar but no `Ave. Reso EB`, so sharpness is averaged here while
# noise is read from the scalar whenever the doc carries one.
BSM_SHARPNESS_KEY = "Reso EB"
BSM_NOISE_SCALAR = "Ave. Noise"
BSM_NOISE_PROFILE = "Noise"
# Docs kept per tool. beam_shape runs ~3x/day
# (docs/datatables/hitachi/hardware_beam_shape.txt), so a 30-day window is ~90 docs per
# tool per beam condition and 40 silently cut the older half — the
# epoch-opening levels in `epoch_history` then came from whatever survived.
#
# 100 is not a preference, it is OpenSearch's `index.max_inner_result_window`,
# the ceiling on a top_hits sub-aggregation. An earlier 200 here answered 400
# `search_phase_execution_exception` and failed the whole page, which is why
# `_top_hits` now refuses an over-cap size at home instead. Truncation at the
# cap is DETECTED below rather than quietly served — that document's own rule
# ("상한에 닿으면 조용히 자르지 않고 감지합니다").
#
# If a fab genuinely needs more than 100, the fix is a narrower window or a
# date_histogram, NOT raising a cluster-wide setting for one screen.
BSM_DOCS_PER_TOOL = MAX_INNER_RESULT_WINDOW

# A fleet is uniform enough that "3 MADs out" is a real outlier; the floor stops
# a fleet whose readings happen to be identical from flagging the one tool that
# differs in the third decimal.
_ROBUST_Z = 3.0
_MAD_TO_SIGMA = 1.4826
_BSM_MAD_FLOOR = {"sharpness": 0.01, "noise": 0.01}

# One (timestamp, sharpness, noise) BSM reading. Both metrics are independently
# nullable: a doc whose array will not coerce is missing that metric, not the
# whole reading.
BsmReading = tuple[datetime, float | None, float | None]


# ── small numeric helpers ─────────────────────────────────────────────────


def _mean_of(values: Any) -> float | None:
    """Mean of a per-degree array, ignoring cells that will not parse.

    The source mixes floats and numeric strings inside one array
    (``[6.069593, '6.118456', ...]``), which is why this cannot be
    ``statistics.fmean`` over the raw list.
    """
    if not isinstance(values, (list, tuple)):
        return None
    numbers = [n for n in (_as_float(v) for v in values) if n is not None]
    return statistics.fmean(numbers) if numbers else None


def _mad(values: list[float], center: float, floor: float) -> float:
    if len(values) < 3:
        return float("inf")  # too few tools to call any of them an outlier
    spread = statistics.median(abs(value - center) for value in values)
    return max(spread * _MAD_TO_SIGMA, floor)


# ── source reads ──────────────────────────────────────────────────────────


def _fleet_rows(fab: str) -> list[dict[str, Any]]:
    """The fab's CD-SEM roster — the shared law in sem_list/roster.py."""
    return [dict(row) for row in fleet_rows(get_sem_list(), fab_name=fab, tool_type="cd-sem")]


def _bsm_by_tool(
    fab: str, eqp_ids: list[str], start: datetime, end: datetime
) -> dict[str, list[BsmReading]]:
    """Per tool, recent BSM readings, newest first.

    One aggregation for the whole fleet, and ``_source`` trimmed to three keys:
    a beam_shape doc carries a dozen 16-element arrays and the gate needs two of
    them.
    """
    if not eqp_ids:
        return {}
    clauses: list[dict[str, Any]] = [
        {"term": {BSM_TYPE_KW: BSM_DOC_TYPE}},
        {"term": {BSM_CATEGORY_KW: BSM_FDC_CATEGORY}},
        {"term": {FAB_NAME_KW: fab}},
        {"terms": {EQP_ID_KW: eqp_ids}},
        {
            "range": {
                BSM_TIME: {
                    "gte": start.strftime("%Y-%m-%dT%H:%M:%S"),
                    "lte": end.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            }
        },
    ]
    aggs = {
        "per_tool": {
            "terms": {"field": EQP_ID_KW, "size": len(eqp_ids)},
            "aggs": {
                "latest": _top_hits(
                    BSM_DOCS_PER_TOOL,
                    sort=[{BSM_TIME: "desc"}],
                    source=[
                        BSM_TIME,
                        BSM_SHARPNESS_KEY,
                        BSM_NOISE_SCALAR,
                        BSM_NOISE_PROFILE,
                    ],
                )
            },
        }
    }
    result = aggregate(BSM_INDEX, aggs, _query(clauses))

    readings: dict[str, list[BsmReading]] = {}
    for bucket in result.get("per_tool", {}).get("buckets", []):
        eqp_id = _text(bucket.get("key"))
        series: list[BsmReading] = []
        for hit in bucket.get("latest", {}).get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            try:
                at = parse_dt(_text(source.get(BSM_TIME)))
            except ValueError:
                continue
            noise = _as_float(source.get(BSM_NOISE_SCALAR))
            if noise is None:
                noise = _mean_of(source.get(BSM_NOISE_PROFILE))
            series.append((at, _mean_of(source.get(BSM_SHARPNESS_KEY)), noise))
        if bucket.get("doc_count", 0) > len(
            bucket.get("latest", {}).get("hits", {}).get("hits", [])
        ):
            _LOG.warning(
                "pm_planning: %s returned more than %d BSM docs for %s; the "
                "oldest were not read, so an epoch_history point may report a "
                "later level than the one its epoch opened at.",
                BSM_INDEX, BSM_DOCS_PER_TOOL, eqp_id,
            )
        readings[eqp_id] = series
    return readings


# ── per-tool reduction ────────────────────────────────────────────────────


def _named(points: tuple[Point, ...]) -> list[Point]:
    """Points of a named feature. The unnamed ones are stabilisation shots."""
    return [point for point in points if point.parameter]


def _run_value(run: RunRef) -> float | None:
    return run_median(_named(load_points(run.pkl)))


def _cell_values(runs: list[RunRef]) -> dict[tuple[str, str], float]:
    """Median CD per (beam, axis) across one tool's runs.

    Two levels of median, in this order and not the other: each run collapses to
    one number FIRST, so a run holding 300 points does not outvote a run holding
    30. Pooling the points instead would make the sample size the point count,
    which is the pseudo-replication trap the feasibility note calls the most
    realistic way for this screen to lie
    (``docs/research/2026-08-16-skew-tttm-feasibility.md`` section 2.4).
    """
    per_run: dict[tuple[str, str], list[float]] = {}
    dropped_beams: set[str] = set()
    for run in runs:
        grouped: dict[tuple[str, str], list[Point]] = {}
        for point in load_points(run.pkl):
            axis = resolve_axis(point.parameter, run.recipe_key)
            if axis is None:
                continue  # direction unknown — see resolve_axis's docstring
            beam = beam_label(point.vac)
            if beam not in BEAM_CONDITIONS:
                if beam:
                    dropped_beams.add(beam)
                continue
            grouped.setdefault((beam, axis), []).append(point)
        for key, points in grouped.items():
            value = run_median(points)
            if value is not None:
                per_run.setdefault(key, []).append(value)

    if dropped_beams:
        _LOG.info(
            "pm_planning: dropped beam condition(s) %s — the contract's grid is "
            "%s and a foreign beam has nowhere to be filed",
            ", ".join(sorted(dropped_beams)), "/".join(BEAM_CONDITIONS),
        )
    return {key: statistics.median(values) for key, values in per_run.items()}


def _prev_post_delta(runs: list[RunRef], post_pm_at: str | None) -> float | None:
    """CD after the last PM minus CD before it, or None when it cannot be told.

    ``runs`` arrives oldest-first. Both sides need at least one monitor run, so a
    PM at the edge of the window (or no PM at all) gives None — which the card
    renders by simply omitting the delta sentence.
    """
    if not post_pm_at:
        return None
    try:
        # Parsed, not string-compared. `run.at` carries a UTC tag (KST wall
        # clock, per parse_dt) while `post_pm_at` is the raw stored string with
        # no offset, so a lexical compare works only while their first 19
        # characters happen to line up — and fails silently the day
        # fab_inform_notes starts storing a `Z`, which this module's own
        # docstring records as UNVERIFIED.
        boundary = parse_dt(post_pm_at)
    except ValueError:
        return None
    before = [run for run in runs if run.at < boundary]
    after = [run for run in runs if run.at >= boundary]
    if not before or not after:
        return None
    before_values = [v for v in (_run_value(run) for run in before) if v is not None]
    after_values = [v for v in (_run_value(run) for run in after) if v is not None]
    if not before_values or not after_values:
        return None
    return round(statistics.median(after_values) - statistics.median(before_values), 3)


def _epoch_history(
    epochs: list[MdcChange], bsm: list[BsmReading]
) -> list[EpochPoint]:
    """The tool's last few MDC epochs, with the BSM level each one opened at.

    ``mdc`` is the value that epoch STARTED at (the change's new value): the
    contract carries one float per epoch while a tool holds four or more
    conditions, so this reports the edit that opened the epoch rather than
    pretending to summarise all of them.

    ``bsm_sharpness_avg`` averages the readings in the week after the change.
    An epoch with no BSM reading in that week gets 0.0, which the contract has
    no nullable alternative to — the chart draws a gap at zero rather than
    inventing a level.
    """
    points: list[EpochPoint] = []
    for change in epochs[-3:]:
        # UTC, not KST, and the nine hours matter. The office indices store
        # offset-less KST wall clock, and `parse_dt` labels that naive string
        # UTC — so every `at` here is a KST reading wearing a UTC tag. An
        # honestly-KST midnight would sit nine hours EARLIER than those
        # readings, pulling the previous evening's BSM into this epoch and
        # running the seven-day window nine hours long. Comparing tag-to-tag is
        # what keeps both sides on the same wall clock; it is the same
        # KST-as-UTC convention `_office_meas_hist` states for its own filters.
        opened = datetime.combine(change.on, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        after = sorted(
            (at, sharpness) for at, sharpness, _ in bsm
            if sharpness is not None and at >= opened
        )
        window = [
            sharpness for at, sharpness in after if at <= opened + timedelta(days=7)
        ]
        if not window and after:
            # BSM does not run every day, and an MDC edit does not wait for it.
            # The first reading AFTER the change still describes the level this
            # epoch opened at; 0.0 would draw the chart through the floor and
            # read as a collapsed beam.
            window = [after[0][1]]
        points.append(
            EpochPoint(
                epoch_start=change.on.isoformat(),
                mdc=round(change.new_value, 4),
                bsm_sharpness_avg=round(statistics.fmean(window), 3) if window else 0.0,
            )
        )
    return points


def _cd_spec(fleet_values: list[float]) -> tuple[float, float, float]:
    """(target, lower, upper) for the CD-monitoring gate — see docstring note 2."""
    if not fleet_values:
        return 0.0, 0.0, 0.0
    target = statistics.median(fleet_values)
    half = abs(target) * ACTION_LIMIT_RATIO
    return round(target, 3), round(target - half, 3), round(target + half, 3)


def _bsm_bands(
    readings: dict[str, list[BsmReading]],
) -> dict[str, tuple[float, float]]:
    """Fleet-relative acceptance bands for sharpness and noise — docstring note 3."""
    latest: dict[str, list[float]] = {"sharpness": [], "noise": []}
    for series in readings.values():
        if not series:
            continue
        _, sharpness, noise = series[0]
        if sharpness is not None:
            latest["sharpness"].append(sharpness)
        if noise is not None:
            latest["noise"].append(noise)

    bands: dict[str, tuple[float, float]] = {}
    for name, values in latest.items():
        if not values:
            # No fleet to compare against: pass everything rather than hold the
            # whole fab on an absence. The absence itself is visible as a 0.0
            # sharpness/noise on every gate.
            bands[name] = (float("-inf"), float("inf"))
            continue
        center = statistics.median(values)
        spread = _mad(values, center, _BSM_MAD_FLOOR[name]) * _ROBUST_Z
        bands[name] = (center - spread, center + spread)
    return bands


def _latest_value(runs: list[RunRef]) -> float | None:
    """The tool's most recent monitor reading (runs arrive oldest-first)."""
    for run in reversed(runs):
        value = _run_value(run)
        if value is not None:
            return value
    return None


def _build_gate(
    runs: list[RunRef],
    spec: tuple[float, float, float],
    bsm: list[BsmReading],
    bands: dict[str, tuple[float, float]],
    post_pm_at: str | None,
    mdc_changed: bool,
) -> GateBlock:
    current = _latest_value(runs)
    _, lower, upper = spec
    cd_ok = current is not None and lower <= current <= upper

    sharpness = next((s for _, s, _ in bsm if s is not None), None)
    noise = next((n for _, _, n in bsm if n is not None), None)
    sharp_lo, sharp_hi = bands["sharpness"]
    noise_lo, noise_hi = bands["noise"]
    bsm_ok = (
        sharpness is not None
        and noise is not None
        and sharp_lo <= sharpness <= sharp_hi
        and noise_lo <= noise <= noise_hi
    )

    return GateBlock(
        cd_monitoring_value=round(current, 3) if current is not None else 0.0,
        cd_spec_lower=lower,
        cd_spec_upper=upper,
        cd_in_spec=cd_ok,
        bsm_in_spec=bsm_ok,
        bsm_sharpness_avg=round(sharpness, 3) if sharpness is not None else 0.0,
        bsm_noise_avg=round(noise, 3) if noise is not None else 0.0,
        post_pm_at=post_pm_at,
        prev_post_delta=_prev_post_delta(runs, post_pm_at),
        mdc_changed=mdc_changed,
        # "up" only when BOTH checks passed — and a tool with no readings at all
        # holds, because an absent measurement is not a passed one.
        verdict="up" if (cd_ok and bsm_ok) else "hold",
    )


def _apply_fleet_median(tools: list[ToolBlock]) -> list[ConsensusCell]:
    """Fleet median per cell, then every tool's skew/median/gap rewritten to it.

    Identical law to the mock: consensus is the MEDIAN of the fleet's
    ``current_value`` in that cell, never the mean — one drifted tool would
    otherwise drag the reference and shift every other tool's gap.

    A cell no tool in the fab measured is left OUT of ``consensus`` rather than
    carrying a placeholder: the client pivots cells against the grid, and a
    consensus for a cell nobody measured is a line drawn through no data.
    """
    consensus: list[ConsensusCell] = []
    for beam in BEAM_CONDITIONS:
        for axis in AXES:
            values = [
                cell["current_value"]
                for tool in tools
                for cell in tool["cells"]
                if cell["beam"] == beam and cell["axis"] == axis
            ]
            if not values:
                continue
            median = round(statistics.median(values), 3)
            consensus.append(ConsensusCell(beam=beam, axis=axis, consensus=median))
            for tool in tools:
                for cell in tool["cells"]:
                    if cell["beam"] == beam and cell["axis"] == axis:
                        cell["median"] = median
                        cell["gap"] = round(cell["current_value"] - median, 3)
                        # The mock draws `skew` from its generator and `gap`
                        # from the fleet, and they agree by construction. With
                        # real data there is only one signed distance from
                        # consensus, so both carry it rather than one of them
                        # carrying a second, differently-derived number the
                        # screen would show beside it.
                        cell["skew"] = cell["gap"]
    return consensus


def _empty_payload(
    fab: str, fetched_at: str, anchor: datetime, window_weeks: int
) -> FleetPayload:
    """A fab with no CD-SEM roster. Empty, not an error — same as the mock."""
    return FleetPayload(
        tool_type="cd-sem",
        fab_name=fab,
        fetched_at=fetched_at,
        anchor_date=anchor.date().isoformat(),
        window_weeks=window_weeks,
        beam_conditions=BEAM_CONDITIONS,
        axes=AXES,
        defaults=DEFAULTS,  # type: ignore[typeddict-item]
        consensus=[],
        tools=[],
    )


def get_pm_planning_fleet(fab_name: str, window_weeks: int) -> FleetPayload:
    """One fab's CD-SEM Up-gate snapshot, joined across the four sources.

    ``window_weeks`` bounds the monitor runs and the BSM readings (one span,
    one label), and the per-tool run cap grows with it — see ``runs_per_tool``.
    PM events and MDC epochs keep their own longer lookbacks: both are facts
    about the tool rather than evidence the user sized.
    """
    fab = fab_name.strip().upper()
    eqp_ids = [str(row["eqp_id"]) for row in _fleet_rows(fab)]

    anchor = get_anchor_time()
    start = anchor - timedelta(days=window_days(window_weeks))
    fetched_at = datetime.now(KST).replace(microsecond=0).isoformat()

    if not eqp_ids:
        return _empty_payload(fab, fetched_at, anchor, window_weeks)

    runs = recent_runs(
        "cd-sem",
        fab,
        eqp_ids,
        start,
        anchor,
        recipe=monitor_recipe_pattern(),
        per_tool=runs_per_tool(window_weeks),
    )
    by_tool = runs.by_tool()
    bsm = _bsm_by_tool(fab, eqp_ids, start, anchor)
    bands = _bsm_bands(bsm)
    post_pm = latest_pm_by_tool(
        maintenance_events(fab, eqp_ids, anchor - timedelta(days=PM_LOOKBACK_DAYS), anchor)
    )

    epochs_by_tool: dict[str, list[MdcChange]] = {}
    for change in mdc_changes(fab, anchor - timedelta(days=EPOCH_LOOKBACK_DAYS), anchor):
        epochs_by_tool.setdefault(change.eqp_id, []).append(change)

    # The spec window is the fleet's own median, so every tool's latest reading
    # has to exist before any tool can be judged — the same "whole fleet first"
    # ordering _apply_fleet_median needs for the cells.
    spec = _cd_spec(
        [
            value
            for eqp_id in eqp_ids
            if (value := _latest_value(by_tool.get(eqp_id, []))) is not None
        ]
    )

    tools: list[ToolBlock] = [
        ToolBlock(
            eqp_id=eqp_id,
            gate=_build_gate(
                by_tool.get(eqp_id, []),
                spec,
                bsm.get(eqp_id, []),
                bands,
                post_pm.get(eqp_id),
                bool(epochs_by_tool.get(eqp_id)),
            ),
            cells=[
                CellSkew(
                    beam=beam,  # type: ignore[typeddict-item]
                    axis=axis,  # type: ignore[typeddict-item]
                    # Provisional; _apply_fleet_median rewrites all three below
                    # once every tool exists, exactly as the mock does.
                    skew=0.0,
                    current_value=round(value, 3),
                    median=round(value, 3),
                    gap=0.0,
                )
                for (beam, axis), value in sorted(
                    _cell_values(by_tool.get(eqp_id, [])).items()
                )
            ],
            epoch_history=_epoch_history(
                epochs_by_tool.get(eqp_id, []), bsm.get(eqp_id, [])
            ),
        )
        for eqp_id in eqp_ids
    ]
    consensus = _apply_fleet_median(tools)

    return FleetPayload(
        tool_type="cd-sem",
        fab_name=fab,
        fetched_at=fetched_at,
        anchor_date=anchor.date().isoformat(),
        window_weeks=window_weeks,
        beam_conditions=BEAM_CONDITIONS,
        axes=AXES,
        defaults=DEFAULTS,  # type: ignore[typeddict-item]
        consensus=consensus,
        tools=tools,
    )


if __name__ == "__main__":  # pragma: no cover
    # Staged office diagnostic — run FROM THE REPO ROOT with a real fab:
    #   .venv/bin/python -m back_dev_home.ebeam.pm_planning.providers.office R3
    #
    # It walks the four sources in the order the payload needs them and prints
    # what each returned, because an empty pm-tune page looks identical
    # whichever of them came back empty. The first stage printing 0 IS the bug —
    # and the two likeliest are named in the module docstring:
    # SKEWNONO_CD_MONITOR_RECIPE (stage 2) and SKEWNONO_AXIS_PARAM_MAP (stage 3).
    import sys

    from back_dev_home.ebeam._office_msr_cd import AXIS_ENV_VAR, MONITOR_RECIPE_ENV_VAR

    fab_arg = (sys.argv[1] if len(sys.argv) > 1 else "R3").upper()
    print(
        f"fab={fab_arg}  monitor recipe={monitor_recipe_pattern()!r} "
        f"(override with {MONITOR_RECIPE_ENV_VAR})"
    )

    print("\n--- 1. roster (sem_list) ---")
    ids = [str(row["eqp_id"]) for row in _fleet_rows(fab_arg)]
    print(f"  {len(ids)} CD-SEM tools: {ids[:8]}{' ...' if len(ids) > 8 else ''}")
    if not ids:
        print(
            "  EMPTY — check the fab_name spelling (M14A, not M14) and that "
            "sem_list is on the office provider."
        )
        sys.exit(1)

    anchor_at = get_anchor_time()
    weeks_arg = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_WINDOW_WEEKS
    window_start = anchor_at - timedelta(days=window_days(weeks_arg))
    print(
        f"  window: {window_start.date()} .. {anchor_at.date()} "
        "(anchor = max meas_hist timestamp)"
    )

    print("\n--- 2. monitor runs (meas_hist -> MinIO) ---")
    found = recent_runs(
        "cd-sem", fab_arg, ids, window_start, anchor_at,
        recipe=monitor_recipe_pattern(), per_tool=runs_per_tool(weeks_arg),
    )
    print(f"  {len(found.runs)} runs across {len(found.by_tool())} tools")
    if found.truncated:
        print(f"  capped at {runs_per_tool(weeks_arg)}/tool for: {list(found.truncated)}")
    if not found.runs:
        print(
            "  EMPTY — the recipe filter is the likely cause. Recipe names this "
            "fab actually ran, unfiltered:"
        )
        every = recent_runs("cd-sem", fab_arg, ids, window_start, anchor_at, per_tool=3)
        print(f"    {sorted({run.recipe_key for run in every.runs})[:20]}")
        print(f"  Set {MONITOR_RECIPE_ENV_VAR} to the monitor recipe above.")
        sys.exit(1)

    print("\n--- 3. CD values + axis split (the pickles) ---")
    # Every run in the window, not one sample: the direction is in the
    # parameter NAME and the naming varies per recipe and per fab, so the map
    # can only be written once the whole vocabulary is on screen.
    # Keyed by (recipe, parameter): the axis belongs to that PAIR, since one
    # recipe's Para_13 is not another's. Same scoping routes.py enforces on the
    # tttm `parameter` query arg.
    vocabulary: dict[tuple[str, str], int] = {}
    beams: set[str] = set()
    for run in found.runs:
        for point in load_points(run.pkl):
            beams.add(beam_label(point.vac))
            if point.parameter:
                key = (run.recipe_key, point.parameter)
                vocabulary[key] = vocabulary.get(key, 0) + 1
    resolved = {
        key: resolve_axis(key[1], key[0]) for key in sorted(vocabulary)
    }
    print(
        f"  {len(found.runs)} runs, {len(vocabulary)} distinct "
        "(recipe, parameter) pairs"
    )
    for key in sorted(vocabulary):
        recipe_key, name = key
        print(
            f"    {recipe_key:<30} {name:<24} "
            f"n={vocabulary[key]:<6} axis={resolved[key]}"
        )
    print(f"  beams seen: {sorted(beams)}")

    unresolved = [key for key, axis in resolved.items() if axis is None]
    if unresolved:
        print(
            f"\n  ★ {len(unresolved)} pair(s) have no resolvable direction, "
            "so their rows are DROPPED from `cells` (never defaulted to X)."
        )
        print("    Paste this into back_dev_home/.env, correcting each axis:")
        print(
            f"    {AXIS_ENV_VAR}="
            + ",".join(f"{recipe_key}:{name}=X" for recipe_key, name in unresolved)
        )
        print("    Globs work on both halves — e.g. ADI/*:*_HOR=X,*_VER=Y —")
        print("    and drop the 'recipe:' prefix for a rule that is fab-wide.")

    print("\n--- 4. BSM / PM / MDC ---")
    readings = _bsm_by_tool(fab_arg, ids, window_start, anchor_at)
    print(
        f"  BSM: {sum(len(v) for v in readings.values())} docs across "
        f"{len(readings)} tools; bands={_bsm_bands(readings)}"
    )
    maint = maintenance_events(
        fab_arg, ids, anchor_at - timedelta(days=PM_LOOKBACK_DAYS), anchor_at
    )
    print(
        f"  PM : {sum(len(v) for v in maint.values())} maintenance jobs, "
        f"{len(latest_pm_by_tool(maint))} tools with a completed PM in the last "
        f"{PM_LOOKBACK_DAYS}d"
    )
    print(
        f"  MDC: {len(mdc_changes(fab_arg, anchor_at - timedelta(days=EPOCH_LOOKBACK_DAYS), anchor_at))} "
        f"changes in the last {EPOCH_LOOKBACK_DAYS}d"
    )

    print("\n--- 5. payload ---")
    payload = get_pm_planning_fleet(fab_arg)
    print(f"  tools={len(payload['tools'])} consensus={payload['consensus']}")
    first = payload["tools"][0]
    print(
        f"  sample {first['eqp_id']}: verdict={first['gate']['verdict']} "
        f"cd={first['gate']['cd_monitoring_value']} "
        f"in[{first['gate']['cd_spec_lower']},{first['gate']['cd_spec_upper']}] "
        f"cells={len(first['cells'])}"
    )
