"""Office-side plumbing: fleet measurement runs -> per-point CD values.

``_office_meas_hist.py`` answers "which runs happened" out of OpenSearch and
``_office_search.py`` owns the raw connection mechanics. Neither of them opens
a measurement: the CD numbers live in the post-processed pickle each meas_hist
document points at (``minio_pkl``), and until now only ``msr_file``'s adapter
read one — a single MSR at a time, for one screen.

pm_planning and tttm both need the step after that: the CD values of a whole
FLEET's recent runs, reduced to one robust number per (tool, beam, axis). They
would otherwise grow two copies of the same pickle reader, the same beam/axis
vocabulary, and the same cost guards — and the two copies would drift, which is
precisely the failure ``_office_meas_hist.py`` was extracted to prevent when
fail_issue became recipe_tat's second consumer.

This module is TRACKED (it is not an ``office_example.py`` template), so a
``git pull`` at the office updates it without a second ``cp``. It carries index
names, field names and pickle column names — all of which are already recorded
in ``docs/datatables/hitachi/{meas_hist,msr_file_pickle}.txt`` — but no query shaped to
one feature's question. Those stay in each feature's gitignored ``office.py``.

Three properties are load-bearing, and each has a way of failing silently:

* **The unit of evidence is a RUN, not a measurement point.** One MSR holds
  hundreds of points of the same wafer, correlated at rho ~ 0.8; counting them
  as independent samples shrinks a standard error by 10-25x and reports every
  tool pair as significantly skewed. ``run_median`` therefore collapses each
  run to ONE number before any tool-level statistic sees it. See section 2.4 of
  ``docs/research/2026-08-16-skew-tttm-feasibility.md``.
* **Median, never mean.** A single CD outlier inside a run moves that tool's
  action limit. The fab states its own rule against a median, and the mocks
  follow it.
* **Cost is bounded and the bound is announced.** One MinIO GET per run; a fab
  fleet over 60 days is thousands of them, which is why ``recent_runs`` takes a
  per-tool cap and ``load_points`` is LRU-cached. When the cap bites, the
  caller is told (``RunSet.truncated``) rather than shown a quietly partial
  answer — the same rule ``fetch_hits`` states for its own ``size``.

Connection settings come from ``OPENSEARCH_*`` in ``back_dev_home/.env``
(self-loaded by ``_office_search.client``) and from
``minio_handler/minio_config.py`` for the object store.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable, Sequence
from fnmatch import fnmatch
from datetime import datetime
from functools import lru_cache
from statistics import median
from typing import Any, NamedTuple

from back_dev_home.ebeam._office_meas_hist import (
    EQP_ID_KW,
    FAB_NAME_KW,
    FULL_NAME_KW,
    INDEX,
    TIME_FIELD,
    MAX_INNER_RESULT_WINDOW,
    aggregate,
    msr_of as _msr_of,
    parse_dt,
    query as _query,
    text as _text,
    top_hits as _top_hits,
)
from back_dev_home.ebeam._tool_specs import ToolType


__all__ = [
    "AXIS_ENV_VAR",
    "as_float",
    "CD_BANDS",
    "MONITOR_RECIPE_ENV_VAR",
    "Point",
    "RunRef",
    "RunSet",
    "beam_label",
    "cd_band",
    "has_pickle_clause",
    "load_points",
    "monitor_recipe_pattern",
    "recent_runs",
    "resolve_axis",
    "run_median",
]

_LOG = logging.getLogger(__name__)


# ── the run index ──────────────────────────────────────────────────────────

# Only a run whose MSR file landed has a pickle to open. A run without one is a
# real execution (recipe_tat counts it) but carries no CD values, so fetching it
# would be a guaranteed wasted GET.
#
# This asks for the pickle path directly. It used to ask `msr_check == "Yes"`
# as a proxy, which stopped meaning anything: msr_check is "Yes" on all
# 2,250,652 office documents (office 확인 2026-08-20), so the clause filtered
# nothing and every pickle-less run reached the fetch loop. Asking for the
# field the next step actually opens cannot drift out of agreement with it.
MINIO_PKL_FIELD = "minio_pkl"
RECIPE_NAME_KW = "recipe_name.keyword"
CLASS_NAME_KW = "class_name.keyword"


def has_pickle_clause() -> dict[str, Any]:
    """The filter for "this run has CD values to read".

    Every caller that fans out to MinIO must apply this, and tttm's recipe
    picker must apply it too: a picker scoped more loosely than the payload it
    drives offers recipes that come back empty. Returns a fresh dict so a
    caller assembling a clause list cannot mutate the shared one.

    `exists` also matches a field stored as "", which `_run_from_hit` drops on
    the `pkl` guard. Narrowing that here would need a `minio_pkl.keyword`
    subfield whose existence is unverified, and a composite source on a field
    that is not mapped returns zero buckets rather than an error -- an empty
    screen indistinguishable from "no data".
    """
    return {"exists": {"field": MINIO_PKL_FIELD}}

# The _source fields a run needs. Trimmed on purpose: meas_hist documents are
# wide and this adapter reads eight fields of them.
_RUN_SOURCE = [
    "msr",
    "eqp_id",
    "recipe_name",
    "full_name",
    "class_name",
    "lot_id",
    "timestamp",
    "start_time",
    "minio_pkl",
]

# Per tool, per request. 12 runs over the default window is enough to separate
# a reproducible tool offset from day-to-day scatter (the local-linear-trend
# filter in the feasibility note wants a series, not a single point), while
# keeping a 20-tool fab under ~240 MinIO GETs — slow but survivable for a lab
# page. Raise it only together with a rollup job; see MIGRATION.md.
DEFAULT_RUNS_PER_TOOL = 12

# Callers pick `per_tool`; this is the ceiling OpenSearch itself imposes on a
# top_hits sub-aggregation. `_top_hits` raises rather than letting the cluster
# answer 400, so a caller asking for more fails at home, in a test.
MAX_RUNS_PER_TOOL = MAX_INNER_RESULT_WINDOW

# Hard ceiling on the terms bucket count, so a mis-typed fleet cannot ask
# OpenSearch for an unbounded aggregation.
_MAX_TOOLS = 64


class RunRef(NamedTuple):
    """One measurement execution: the address of a pickle plus its identity."""

    msr: str
    eqp_id: str
    recipe_name: str
    full_name: str
    lot_id: str
    at: datetime
    pkl: str

    @property
    def recipe_key(self) -> str:
        """The recipe identity to CONTRAST tools within.

        ``full_name`` (``class/recipe``) when the document carries one, because
        two classes can hold the same recipe_name and they are not the same
        measurement program. Falls back to ``recipe_name`` so a document with
        an empty ``full_name`` still groups with its siblings instead of
        forming a nameless bucket of its own.
        """
        return self.full_name or self.recipe_name


class RunSet(NamedTuple):
    """The runs found, and whether the per-tool cap hid any of them."""

    runs: tuple[RunRef, ...]
    truncated: tuple[str, ...]  # eqp_ids whose run list hit the cap

    def by_tool(self) -> dict[str, list[RunRef]]:
        grouped: dict[str, list[RunRef]] = {}
        for run in self.runs:
            grouped.setdefault(run.eqp_id, []).append(run)
        return grouped


def _run_from_hit(hit: dict[str, Any]) -> RunRef | None:
    # The whole hit, not just _source: on documents with no ``msr`` field the
    # measurement id is the ``_id``, and dropping those runs would quietly
    # shrink every tool's history to the days that predate the change.
    source = hit.get("_source", {})
    pkl = _text(source.get("minio_pkl"))
    msr = _msr_of(hit)
    eqp_id = _text(source.get("eqp_id"))
    if not (pkl and msr and eqp_id):
        # No pickle path, no measurement to open. Dropping it here keeps every
        # downstream loop free of a None check that would otherwise be silently
        # skipped once someone "simplified" it away.
        return None
    stamp = _text(source.get("timestamp")) or _text(source.get("start_time"))
    try:
        at = parse_dt(stamp)
    except ValueError:
        return None
    return RunRef(
        msr=msr,
        eqp_id=eqp_id,
        recipe_name=_text(source.get("recipe_name")),
        full_name=_text(source.get("full_name")),
        lot_id=_text(source.get("lot_id")),
        at=at,
        pkl=pkl,
    )


def _recipe_clause(recipe: str) -> dict[str, Any]:
    """Match ``recipe`` against every recipe identity a caller might hold.

    Three names address the same runs and different callers hold different
    ones: the tttm picker passes whatever ``recipe-search`` listed (a bare
    ``recipe_name`` on one path, a ``class/recipe`` ``full_name`` on another),
    while pm_planning's monitor-recipe knob may reasonably be a ``class_name``
    such as ``QC``. Matching only one of them answers 200 with an empty fleet
    for the other callers, and nothing about that response looks wrong.

    A value containing ``*`` becomes a case-insensitive wildcard instead —
    ``*MONITOR*`` finds the monitor recipe without anyone having to type its
    exact name first. Wildcards run against the same ``.keyword`` sub-fields:
    the analyzed parents are tokenized, so ``VERITYSEM_5`` would already have
    been split into ``veritysem``/``5`` before the pattern ever saw it.
    """
    fields = (FULL_NAME_KW, RECIPE_NAME_KW, CLASS_NAME_KW)
    if "*" in recipe:
        should: list[dict[str, Any]] = [
            {"wildcard": {field: {"value": recipe, "case_insensitive": True}}}
            for field in fields
        ]
    else:
        should = [{"term": {field: recipe}} for field in fields]
    return {"bool": {"should": should, "minimum_should_match": 1}}


def recent_runs(
    tool_type: ToolType,
    fab_name: str,
    eqp_ids: Sequence[str],
    start: datetime,
    end: datetime,
    *,
    recipe: str | None = None,
    per_tool: int = DEFAULT_RUNS_PER_TOOL,
) -> RunSet:
    """The most recent ``per_tool`` runs of each tool, OLDEST first.

    The query sorts descending (that is how "most recent N" is selected); the
    result is then re-sorted ascending, because every caller reads it as a
    series — a before/after split around a PM, a daily trend. Callers that want
    the latest run take the last element.

    One aggregation, not one search per tool: a 20-tool fab would otherwise be
    20 round trips before the first pickle is even opened. ``terms`` over
    ``eqp_id.keyword`` with a ``top_hits`` sub-aggregation gives the same
    answer in a single request, and the bucket's ``doc_count`` is what tells us
    whether the cap hid anything.

    Tools absent from the result simply have no runs in the window — that is a
    fact about the fab, not an error, and callers must render it as "not
    measured" rather than as zero skew.
    """
    fleet = [eqp for eqp in dict.fromkeys(eqp_ids) if eqp]
    if not fleet:
        return RunSet((), ())
    if len(fleet) > _MAX_TOOLS:
        raise ValueError(
            f"recent_runs was asked for {len(fleet)} tools (cap {_MAX_TOOLS}). "
            "That is larger than any single fab's fleet — check the roster "
            "filter rather than raising the cap."
        )

    index = INDEX[tool_type]
    clauses: list[dict[str, Any]] = [
        {"term": {FAB_NAME_KW: fab_name.strip().upper()}},
        {"terms": {EQP_ID_KW: fleet}},
        has_pickle_clause(),
        {
            "range": {
                TIME_FIELD: {
                    "gte": start.strftime("%Y-%m-%dT%H:%M:%S"),
                    "lte": end.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            }
        },
    ]
    if recipe:
        clauses.append(_recipe_clause(recipe))

    aggs = {
        "per_tool": {
            "terms": {"field": EQP_ID_KW, "size": len(fleet)},
            "aggs": {
                "latest": _top_hits(
                    per_tool, sort=[{TIME_FIELD: "desc"}], source=_RUN_SOURCE
                )
            },
        }
    }
    result = aggregate(index, aggs, _query(clauses))

    runs: list[RunRef] = []
    truncated: list[str] = []
    for bucket in result.get("per_tool", {}).get("buckets", []):
        hits = bucket.get("latest", {}).get("hits", {}).get("hits", [])
        for hit in hits:
            run = _run_from_hit(hit)
            if run is not None:
                runs.append(run)
        if bucket.get("doc_count", 0) > len(hits):
            truncated.append(_text(bucket.get("key")))

    if truncated:
        _LOG.info(
            "recent_runs: %d of %d tools had more than %d runs in "
            "[%s .. %s]; older runs were not opened (%s)",
            len(truncated), len(fleet), per_tool,
            start.date(), end.date(), ", ".join(sorted(truncated)),
        )
    runs.sort(key=lambda run: (run.eqp_id, run.at), reverse=False)
    return RunSet(tuple(runs), tuple(sorted(truncated)))


# ── the pickle ─────────────────────────────────────────────────────────────

# Pickle column names, per docs/datatables/hitachi/msr_file_pickle.txt. The spaces in
# the meas_condition keys are in the source; msr_file's contract renames them
# to meas_condition_vac and friends, which is a CONTRACT name, not a source one.
_COL_PARAMETER = "parameter"
_COL_CD = "cd_value"
_COL_VAC = "meas_condition vac"
_COL_MAG = "meas_condition mag"
_COL_CHIP = "chip_number"
_COL_MP = "mp_number"
_COL_METHOD = "meas_method"
_COL_OBJECT = "object"


class Point(NamedTuple):
    """One measured site of one run."""

    parameter: str
    cd_value: float | None
    vac: int
    mag: int
    chip: str
    mp: int
    method: str
    object_type: str


def as_float(value: Any) -> float | None:
    """A source cell as a finite float, or None.

    Shared rather than re-derived per adapter: the office sources mix floats
    with numeric strings inside one array (``[6.069593, '6.118456', ...]``), and
    two copies of this coercion are two places for NaN handling to diverge.
    ``bool`` is excluded explicitly — it is an ``int`` subclass, so ``True``
    would otherwise coerce to a measurement of 1.0.
    """
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and abs(result) != float("inf") else None


_as_float = as_float


def _as_int(value: Any) -> int:
    result = as_float(value)
    return int(result) if result is not None else 0


def _records(frame: Any) -> list[dict[str, Any]]:
    """``df_result_data`` as plain dicts, whether it is a frame or records."""
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict(orient="records"))
    if isinstance(frame, list):
        return [row for row in frame if isinstance(row, dict)]
    return []


# One entry per MSR. A fab request opens a few hundred pickles and consecutive
# requests (the same fab, a different parameter) reuse almost all of them, so
# the cache is what makes the second request fast rather than merely repeatable.
#
# Sized for the WIDEST window of both lab adapters on one page, twice over:
# pm-tune loads the tttm check (3 weeks x 10 runs/week x ~18 tools = 540) and
# the pm_planning fleet (3 x 8 x 18 = 432) together, ~970 pickles, and a cache
# smaller than one page load evicts the first adapter's runs while the second
# is still opening its own — every later request then re-fetches everything.
# 768 was that size once the window became selectable (2026-08-25).
@lru_cache(maxsize=2048)
def load_points(pkl: str) -> tuple[Point, ...]:
    """Every measured site of one run, straight from its MinIO pickle.

    Rows with an unnamed ``parameter`` are KEPT: they are the stabilisation
    shots a recipe fires before its real measurements, they carry genuine
    cd_values, and dropping them here would silently change what "every point
    of this run" means for a caller that never asked about naming. Callers
    that want named features only filter on ``point.parameter``.

    Raises whatever the object store raises. A missing pickle is a real
    ingestion gap, and answering 200 with fewer tools would hide it.
    """
    from minio_handler import MinioObject

    payload = MinioObject().get_pickle(pkl.lstrip("/"))
    if not isinstance(payload, dict):
        return ()
    points: list[Point] = []
    for row in _records(payload.get("df_result_data")):
        points.append(
            Point(
                parameter=_text(row.get(_COL_PARAMETER)),
                cd_value=_as_float(row.get(_COL_CD)),
                vac=_as_int(row.get(_COL_VAC)),
                mag=_as_int(row.get(_COL_MAG)),
                chip=_text(row.get(_COL_CHIP)),
                mp=_as_int(row.get(_COL_MP)),
                method=_text(row.get(_COL_METHOD)),
                object_type=_text(row.get(_COL_OBJECT)),
            )
        )
    return tuple(points)


def run_median(points: Iterable[Point]) -> float | None:
    """The one number a run contributes, or None when it measured no CD.

    Collapsing here rather than at the call site is the whole point: a caller
    that pooled raw points across runs would be counting the same wafer many
    times over. See the module docstring's first load-bearing property.
    """
    values = [point.cd_value for point in points if point.cd_value is not None]
    return median(values) if values else None


# ── beam, axis and CD band vocabulary ──────────────────────────────────────


def beam_label(vac: int) -> str:
    """Accelerating voltage as the label the MDC keys use (``500`` -> 500V).

    ``meas_condition vac`` is the only beam attribute the pickle carries, so
    the label stops at the voltage. The office MDC keys carry an optics suffix
    too (``500V_HR_0Deg``); an adapter that can resolve the tool's optics may
    extend this label, but it must not GUESS one — two optics modes at the same
    voltage are different beams and folding them together averages away the
    difference the screen exists to show.
    """
    return f"{vac}V" if vac > 0 else ""


# Bands are the contract's own labels (tttm/contracts.py CellSkew.cd_band).
# Lower bound inclusive, upper exclusive — tttm/tests/test_contract.py parses
# these strings back and asserts `low <= median < high`, so the two must agree.
CD_BANDS: tuple[tuple[float, float, str], ...] = (
    (0.0, 25.0, "<25"),
    (25.0, 50.0, "25-50"),
    (50.0, 100.0, "50-100"),
    (100.0, 200.0, "100-200"),
    (200.0, float("inf"), ">=200"),
)


def cd_band(value: float) -> str:
    """The band ``value`` (nm) falls in. Derive BOTH from the same number.

    A cell whose band came from one frame and whose median came from another is
    the mistake ``test_median_cd_agrees_with_the_band_it_is_filed_under``
    exists to catch: it still renders, just against an action limit drawn for
    the wrong pattern size.
    """
    for low, high, label in CD_BANDS:
        if low <= value < high:
            return label
    return CD_BANDS[-1][2]


AXIS_ENV_VAR = "SKEWNONO_AXIS_PARAM_MAP"

# Direction tokens inside a parameter name. Deliberately anchored on separators
# so `PARA_X` resolves and `MAX_CD` does not — a substring test on "X" matches
# most of a fab's vocabulary and would file half the fleet under the wrong axis.
_AXIS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:^|[_\-\s])(?:X|CDX|XCD|H|HORIZ\w*)(?:[_\-\s]|$)", re.I), "X"),
    (re.compile(r"(?:^|[_\-\s])(?:Y|CDY|YCD|V|VERT\w*)(?:[_\-\s]|$)", re.I), "Y"),
)


class _AxisRule(NamedTuple):
    """One ``[recipe:]parameter=axis`` entry of the axis map."""

    recipe: str | None   # casefolded; None = applies to any recipe
    parameter: str       # casefolded
    axis: str
    recipe_is_glob: bool
    parameter_is_glob: bool

    @property
    def specificity(self) -> tuple[int, int]:
        """How narrowly this rule was written. Higher wins.

        A rule naming one recipe outranks one naming a family, which outranks
        an unscoped rule; within each, an exact parameter outranks a glob. So a
        fab can state a broad family rule and then correct the single feature
        that breaks it, without having to order the entries carefully.
        """
        recipe_rank = 0 if self.recipe is None else (1 if self.recipe_is_glob else 2)
        return (recipe_rank, 0 if self.parameter_is_glob else 1)


def _is_glob(text: str) -> bool:
    return any(char in text for char in "*?[")


def _matches(value: str, pattern: str, is_glob: bool) -> bool:
    return fnmatch(value, pattern) if is_glob else value == pattern


@lru_cache(maxsize=1)
def _axis_rules() -> tuple[_AxisRule, ...]:
    """``SKEWNONO_AXIS_PARAM_MAP`` parsed once.

    Grammar, comma-separated::

        [<recipe>:]<parameter>=<X|Y>

    Both halves accept globs::

        SKEWNONO_AXIS_PARAM_MAP="ADI/CD_MONITOR_001:Para_13=X,*:*_HOR=X,*_VER=Y"

    **The recipe scope is the point, not a convenience.** A parameter name is a
    row of ONE recipe's ``idp_image_info``, and the same name in another recipe
    measures a different feature — which is why ``tttm/routes.py`` refuses a
    ``parameter`` without a ``recipe_id`` rather than ignoring it. An axis map
    keyed on the bare name contradicts that rule: it would file ``Para_13`` of
    every recipe under one direction, and be wrong for all but the one it was
    written against, silently.

    Unscoped entries are still accepted and still useful — a fab whose
    ``*_HOR`` / ``*_VER`` convention really is fab-wide should say so once
    rather than repeat it per recipe. They simply lose to any scoped rule that
    also matches.
    """
    rules: list[_AxisRule] = []
    for item in os.environ.get(AXIS_ENV_VAR, "").split(","):
        left, sep, axis = item.rpartition("=")
        if not sep:
            continue
        axis = axis.strip().upper()
        if axis not in ("X", "Y"):
            continue
        recipe_part, scoped, parameter_part = left.strip().partition(":")
        recipe = recipe_part.strip() if scoped else None
        parameter = (parameter_part if scoped else recipe_part).strip()
        if not parameter or (scoped and not recipe):
            continue
        rules.append(
            _AxisRule(
                recipe=recipe.casefold() if recipe else None,
                parameter=parameter.casefold(),
                axis=axis,
                recipe_is_glob=bool(recipe) and _is_glob(recipe),
                parameter_is_glob=_is_glob(parameter),
            )
        )
    return tuple(rules)


def resolve_axis(parameter: str, recipe: str | None = None) -> str | None:
    """``"X"`` / ``"Y"`` for a measured feature of ``recipe``, or None.

    ``recipe`` is the recipe identity the parameter was measured under
    (``RunRef.recipe_key``). It is optional only so a caller that genuinely has
    no recipe in hand — a diagnostic listing a vocabulary, say — can still ask;
    every real reduction passes it, because without it no recipe-scoped rule
    can apply and the answer silently falls back to the fab-wide guess.

    Order: the most specific matching env rule, then the built-in token
    patterns. The env comes first because the built-in table is a guess about a
    vocabulary that varies per fab, and the fab's own answer must be able to
    overrule it rather than merely fill its gaps.

    None is a real answer and callers must honor it by DROPPING the rows, not
    by defaulting to ``"X"``. The contract's ``Axis`` is a two-value Literal
    with no room for "unknown", so a default would be indistinguishable from a
    measured fact: an X cell would silently hold both directions' rows, and the
    axis-specific drift that TTTM exists to find would average itself away.

    Empty ``occupied_cells`` says "we could not split by direction" loudly.
    A wrong axis says nothing at all.
    """
    name = parameter.strip()
    if not name:
        return None
    folded = name.casefold()
    recipe_folded = recipe.strip().casefold() if recipe else None

    best: _AxisRule | None = None
    for rule in _axis_rules():
        if rule.recipe is not None:
            if recipe_folded is None:
                continue  # a scoped rule cannot be judged without a recipe
            if not _matches(recipe_folded, rule.recipe, rule.recipe_is_glob):
                continue
        if not _matches(folded, rule.parameter, rule.parameter_is_glob):
            continue
        if best is None or rule.specificity > best.specificity:
            best = rule
    if best is not None:
        return best.axis

    for pattern, axis in _AXIS_PATTERNS:
        if pattern.search(name):
            return axis
    return None


MONITOR_RECIPE_ENV_VAR = "SKEWNONO_CD_MONITOR_RECIPE"

# CD monitoring is not one recipe. Each fab runs its own, under its own name,
# and the names differ per fab — but they all begin ``CD_MONITOR``
# (user-confirmed 2026-08-18). They run periodically on the same tool with the
# same recipe, so the runs are ordinary meas_hist documents and need no separate
# source: this prefix over ``meas_hist_{cdsem,hvsem}`` finds them.
#
# So the default is a DISCOVERY rule, not a guess to be replaced. The env var
# stays for the fab that names one differently, or to pin a single recipe when
# a fab runs several and they should not be pooled.
DEFAULT_MONITOR_RECIPE = "CD_MONITOR*"


def monitor_recipe_pattern() -> str:
    """The recipe name pattern that identifies a CD-monitoring run.

    Matched case-insensitively against ``recipe_name``, ``full_name`` and
    ``class_name`` (see ``_recipe_clause``); a value containing ``*`` is a
    wildcard, so the default matches ``CD_MONITOR_M14A_001`` and its
    per-fab siblings alike.

    Override with ``SKEWNONO_CD_MONITOR_RECIPE`` to pin one exact recipe — worth
    doing if a fab runs several monitor recipes at different pattern sizes,
    because pooling those would average two CDs into one gate reading.
    """
    return os.environ.get(MONITOR_RECIPE_ENV_VAR, "").strip() or DEFAULT_MONITOR_RECIPE
