# TEMPLATE — copy to office.py at the office, then implement/verify the body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 measurement-history adapter backed by the office OpenSearch cluster.

Unlike recipe_tat/fail_issue (pure aggregations), this feature returns RAW
rows: the skewvoir search stack and RecipeMeasHistView list individual
measurement executions. Connection plumbing, the lot_id<->lot_cd bridge, and
the shared anchor come from ``back_dev_home/ebeam/_office_meas_hist.py``
(see its docstring for the data layout and the KST-as-UTC timezone contract).

tool_type=None is the DEFAULT skewvoir request, not an edge case: the 검색 UI
sends ``tool_type`` only when the user picks exactly one 카테고리 (CD-SEM /
HV-SEM). Every other search hits BOTH aliases in one request
(``meas_hist_cdsem,meas_hist_hvsem``), so office verification must cover the
no-tool_type path — including that ``_hit_tool_type`` correctly recovers the
family from each hit's ``_index`` name on the real cluster. The dropdown
cascade (FAB → 카테고리 → 장비 모델 → EQ) is frontend-only via sem_list;
facets stay a single un-cascaded aggregation per scope.

Contract-gap derivations — the office documents lack four MeasHistRow fields
(docs/datatables/meas_hist.txt office section):

* ``id``        — the datatable pins ``id = msr``; reuse the msr value.
* ``tool_type`` — from the alias searched; when searching both (tool_type
                  None) it is derived from each hit's ``_index`` name, which
                  is assumed to contain the family token (``cdsem``/``hvsem``).
* ``lot_cd``    — per-row map through the 60-day lot-history bridge; the
                  retention window is also 60 days, so coverage lines up.
                  Unmapped lot_ids surface as ``""``, never dropped — this is
                  a row listing, not a device roll-up.
* ``vendor_nm`` — NOT stored office-side; derived from the eqp_model_cd
                  prefix. AMAT is exactly VeritySEM + Provision; everything
                  else is HITACHI, including BOTH in-scope families —
                  CD-SEM CG/GT and HV-SEM TP are all Hitachi.

Retention: the mock pins RETENTION_ANCHOR at import; office anchors the same
60-day window at the shared ``get_anchor_time()`` (latest real data date,
TTL-cached) so the window follows ingestion in a long-lived process. The
window-resolution semantics are copied from the mock verbatim: a present-but-
unparseable date or a fully-out-of-window range reports ``out_of_retention``
with zero rows; it never silently widens.

q free-text search: the ``q`` fallback is a case-insensitive substring
(``*term*`` wildcard) OR'd across the real source ``.keyword`` fields
(``_Q_FIELDS`` below), the same shape ``_recipe_clause`` already uses. An
earlier design routed ``q`` to a denormalized ``search_all`` wildcard field
(``build_q_fallback_clause`` in ``meas_hist/opensearch_query.py``), but that
field is NOT ingested on the office cluster, so every ``q`` term matched
nothing — a recipe name, an unusually-shaped lot id, or any free text typed in
the search bar returned honest-looking zero rows, and only an exact ``eqp_id``
facet value (which takes the ``eq`` term path) ever worked. Searching the
source fields directly needs no ingestion step this repo can't run. Leading
wildcards are the same ``search.allow_expensive_queries`` cost the recipe
clause already pays; if that ever bites, re-introduce ``search_all`` in the
loader and swap ``_wildcard_or`` back for ``build_q_fallback_clause``.

At the office: fill in OPENSEARCH_* / REDIS_* in ``back_dev_home/.env``,
then ``cp office_example.py office.py`` — that file's existence is the
switch, no env var needed — and run the Verify command in MIGRATION.md.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from back_dev_home.ebeam._office_meas_hist import (
    ALL_INDICES as _ALL_INDICES,
    EQP_ID_KW as _EQP_KW,
    FAB_NAME_KW as _FAB_KW,
    FULL_NAME_KW as _FULL_KW,
    INDEX as _INDEX,
    LOT_ID_KW as _LOT_ID_KW,
    TIME_FIELD as _TIME_F,
    aggregate as _aggregate,
    composite_buckets as _composite_buckets,
    get_anchor_time,
    search as _os_search,
    text as _text,
    try_bridge as _try_bridge,
)
from back_dev_home.meas_hist.contracts import (
    MeasHistFacetsResponse,
    MeasHistFacetValue,
    MeasHistRecipeName,
    MeasHistResponse,
    MeasHistRow,
)
from back_dev_home.meas_hist.contracts import MeasHistSearchResponse
from back_dev_home.meas_hist.opensearch_query import _escape_wildcard_literal
# Single source for the cross-phase constants — importing them (instead of
# redefining) makes Phase 1/2 disagreement impossible.
from back_dev_home.meas_hist.providers._shared import normalize_fail_ratio
from back_dev_home.meas_hist.providers.mock import (
    DEFAULT_LIMIT,
    MAX_RESULT_WINDOW,
    RECIPE_HISTORY_DAYS,
    RETENTION_DAYS,
    ToolType,
)


__all__ = [
    "get_meas_hist",
    "find_meas_hist_by_msr",
    "search_meas_hist",
    "get_meas_hist_facets",
]


_MODEL_KW = "eqp_model_cd.keyword"
_MSR_KW = "msr.keyword"
_RECIPE_KW = "recipe_name.keyword"

# Generous terms-agg cap for the facet dropdowns. A terms agg silently drops
# buckets beyond `size`; the fleet has at most a few hundred eqp_ids and a
# handful of fabs/models, so this is a ceiling, not a tuning knob.
_FACET_SIZE = 1000

# Cap for the per-recipe `fabs` terms sub-agg in the recipe_names snapshot —
# comfortably above the fab count (about a dozen), same ceiling-not-knob idea.
_RECIPE_FABS_SIZE = 16


def _indices(tool_type: ToolType | None) -> str:
    return _INDEX[tool_type] if tool_type else _ALL_INDICES


def _hit_tool_type(hit: dict[str, Any], tool_type: ToolType | None) -> ToolType:
    if tool_type:
        return tool_type
    # Backing index names carry the family token (alias == index, or rollover
    # names like meas_hist_hvsem-000001). "cd-sem" is the fallback family.
    return "hv-sem" if "hvsem" in str(hit.get("_index", "")) else "cd-sem"


_AMAT_MODEL_PREFIXES = ("VERITY", "PROVISION")


def _vendor(eqp_model_cd: str) -> str:
    # vendor_nm is not stored office-side. AMAT is exactly VeritySEM and
    # Provision; every other family here — CD-SEM CG/GT and HV-SEM TP — is
    # HITACHI, as is anything unrecognized on these Hitachi-only aliases.
    # (Neither AMAT family should reach meas_hist_cdsem/hvsem at all, since
    # they are separate tool types; the check is defensive.)
    return (
        "AMAT"
        if eqp_model_cd.upper().startswith(_AMAT_MODEL_PREFIXES)
        else "HITACHI"
    )


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _row(
    hit: dict[str, Any],
    tool_type: ToolType | None,
    bridge: dict[str, str],
) -> MeasHistRow:
    src = hit.get("_source", {})
    msr = _text(src.get("msr"))
    lot_id = _text(src.get("lot_id"))
    eqp_model_cd = _text(src.get("eqp_model_cd"))
    msr_check = "Yes" if _text(src.get("msr_check")).lower() == "yes" else "No"
    align_raw = _text(src.get("align_fail")).lower()
    align_fail = {"pass": "Pass", "fail": "Fail"}.get(align_raw, "NA")
    # All three image fields are computed upstream at ingestion and stored on
    # the document, so they are read, not recalculated. fail_ratio is already
    # a percentage (4.57 = 4.57%), which is the contract's scale — see
    # providers/_shared.py. Deriving it from the counts here would only let
    # this app disagree with every other consumer of the same index.
    total_images = _int(src.get("total_images"))
    fail_images = _int(src.get("fail_images"))

    return MeasHistRow(
        id=msr,  # datatable rule: mock row id = msr; office reuses the same key
        fac_id=_text(src.get("fac_id")),
        fab_name=_text(src.get("fab_name")),
        vendor_nm=_vendor(eqp_model_cd),  # type: ignore[typeddict-item]
        eqp_id=_text(src.get("eqp_id")),
        eqp_ip=_text(src.get("eqp_ip")),
        eqp_model_cd=eqp_model_cd,
        tool_type=_hit_tool_type(hit, tool_type),
        lot_cd=bridge.get(lot_id, ""),
        lot_id=lot_id,
        class_name=_text(src.get("class_name")),
        recipe_name=_text(src.get("recipe_name")),
        full_name=_text(src.get("full_name")),
        timestamp=_text(src.get("timestamp")),
        start_time=_text(src.get("start_time")),
        end_time=_text(src.get("end_time")),
        meastime=_int(src.get("meastime")),
        msr=msr,
        msr_check=msr_check,  # type: ignore[typeddict-item]
        align_fail=align_fail,  # type: ignore[typeddict-item]
        total_images=total_images,
        fail_images=fail_images,
        fail_ratio=normalize_fail_ratio(src.get("fail_ratio")),
        idp_name=_text(src.get("idp_name")),
        idw_name=_text(src.get("idw_name")),
    )


def _rows(result: dict[str, Any], tool_type: ToolType | None) -> list[MeasHistRow]:
    hits = result.get("hits", {}).get("hits", [])
    # Nice-to-have: a lot-history hiccup degrades lot_cd to "" per row rather
    # than failing the listing.
    bridge = _try_bridge() if hits else {}
    return [_row(hit, tool_type, bridge) for hit in hits]


def _total(result: dict[str, Any]) -> int:
    total = result.get("hits", {}).get("total", {})
    if isinstance(total, dict):  # ES7+/OpenSearch shape
        return int(total.get("value") or 0)
    return int(total or 0)  # legacy plain-int shape


# --- Retention window (semantics copied from the mock verbatim) --------------


def _retention_window() -> tuple[datetime, datetime]:
    end = get_anchor_time()
    return end - timedelta(days=RETENTION_DAYS), end


def _parse_date(value: str | None) -> tuple[datetime | None, bool]:
    """(parsed, invalid) — invalid means PRESENT but unparseable (caller error),
    distinct from absent (no bound). See the mock's docstring for why the two
    must not be conflated (an unparseable date must not widen the scan)."""
    if not value or not value.strip():
        return None, False
    try:
        return (
            datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc),
            False,
        )
    except ValueError:
        return None, True


def _resolve_window(
    date_from: str | None,
    date_to: str | None,
) -> tuple[datetime, datetime, bool, datetime]:
    """Intersect the caller's range with retention — mirror of the mock.

    Returns (start, end, out_of_retention, reported_end). ``end`` is the
    FILTERING bound (date_to shifted +1 day so the whole end day matches);
    ``reported_end`` stays the caller-facing INCLUSIVE date for the response's
    ``range.to``.
    """
    floor, ceiling = _retention_window()

    requested_start, start_invalid = _parse_date(date_from)
    requested_end, end_invalid = _parse_date(date_to)

    if start_invalid or end_invalid:
        return floor, ceiling, True, ceiling
    if requested_start and requested_start > ceiling:
        return floor, ceiling, True, ceiling
    if requested_end and requested_end < floor:
        return floor, ceiling, True, ceiling

    start = max(requested_start, floor) if requested_start else floor
    end = min(requested_end + timedelta(days=1), ceiling) if requested_end else ceiling
    reported_end = min(requested_end, ceiling) if requested_end else ceiling

    if start > end:
        return floor, ceiling, True, ceiling

    return start, end, False, reported_end


def _ts(dt: datetime) -> str:
    # KST-as-UTC convention: the indices store offset-less wall-clock values,
    # so bounds are sent offset-less too (an explicit offset would shift them).
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _time_range_clause(start: datetime, end: datetime) -> dict[str, Any]:
    # lte (not lt): the mock keeps ts <= end, where end is already the
    # +1-day-shifted filtering bound resolved by _resolve_window.
    return {"range": {_TIME_F: {"gte": _ts(start), "lte": _ts(end)}}}


# Fields the free-text `q` fallback searches — the office-available subset of
# opensearch_query.SEARCHABLE_SOURCE_FIELDS (no vendor_nm/lot_cd/id: those are
# not stored office-side, they are derived per-row). recipe_name/full_name/
# lot_id/eqp_id/msr cover every token the search-bar parser routes to `q`.
_Q_FIELDS = (
    _RECIPE_KW,
    _FULL_KW,
    _LOT_ID_KW,
    _EQP_KW,
    _MODEL_KW,
    _MSR_KW,
    "class_name.keyword",
    _FAB_KW,
    "fac_id.keyword",
)


def _wildcard_or(terms: list[str], fields: tuple[str, ...]) -> dict[str, Any] | None:
    """case_insensitive substring (``*term*``) match, OR'd across
    (term x field). The .keyword subfields dodge tokenization; constant_score
    skips scoring on what is a pure filter. Mirrors the mock's
    any()-of-substrings."""
    patterns = [
        f"*{_escape_wildcard_literal(term.strip())}*" for term in terms if term.strip()
    ]
    if not patterns:
        return None
    return {
        "bool": {
            "should": [
                {
                    "wildcard": {
                        field: {
                            "value": pattern,
                            "case_insensitive": True,
                            "rewrite": "constant_score",
                        }
                    }
                }
                for pattern in patterns
                for field in fields
            ],
            "minimum_should_match": 1,
        }
    }


def _recipe_clause(terms: list[str]) -> dict[str, Any] | None:
    """Substring match on recipe_name/full_name — the search bar accepts
    fragments."""
    return _wildcard_or(terms, (_RECIPE_KW, _FULL_KW))


# --- Endpoints ----------------------------------------------------------------


def get_meas_hist(
    tool_type: ToolType | None = None,
    fab_name: str | None = None,
    recipe_name: str | None = None,
) -> MeasHistResponse:
    fab_normalized = (fab_name or "").upper() or None

    # Default window, mirroring the mock's RECIPE_HISTORY_DAYS. Anchored on the
    # latest ingested data (not wall-clock) for the same reason retention is:
    # an ingestion pause must not silently empty the view. Applied as a filter
    # clause, so it also bounds the `total` count, not just the returned page.
    floor = get_anchor_time() - timedelta(days=RECIPE_HISTORY_DAYS)
    clauses: list[dict[str, Any]] = [
        {"range": {_TIME_F: {"gte": floor.strftime("%Y-%m-%dT%H:%M:%S")}}}
    ]
    if fab_normalized:
        clauses.append({"term": {_FAB_KW: fab_normalized}})
    if recipe_name:
        # Exact match on either the bare recipe_name or the class/recipe
        # full_name (mock's _matches_recipe). NO synthesis office-side —
        # a genuinely empty result set is correct (MIGRATION.md).
        clauses.append(
            {
                "bool": {
                    "should": [
                        {"term": {_FULL_KW: recipe_name}},
                        {"term": {_RECIPE_KW: recipe_name}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    body: dict[str, Any] = {
        "query": {"bool": {"filter": clauses}},
        "sort": [{_TIME_F: "desc"}],
        "size": MAX_RESULT_WINDOW,
        "track_total_hits": True,
    }
    result = _os_search(_indices(tool_type)).search_raw(body)

    return MeasHistResponse(
        tool_type=tool_type,
        fab_name=fab_normalized,
        recipe_name=recipe_name,
        # True match count — may exceed the returned rows when a filterless
        # call hits the retrieval ceiling (the mock's total == len(rows) only
        # because its universe is small).
        total=_total(result),
        rows=_rows(result, tool_type),
    )


def find_meas_hist_by_msr(msr: str) -> MeasHistRow | None:
    # msr_check == "No" rows carry no msr identity (OFFICE-VERIFY 2026-08-19,
    # docs/datatables/meas_hist.txt). A term query for "" would match any doc
    # that stores the field as an explicit empty string, handing back an
    # arbitrary "No" row -- an identity-less lookup must resolve to nothing,
    # exactly as the mock's _rows_by_msr guard does.
    if not msr:
        return None
    body = {
        "query": {"bool": {"filter": [{"term": {_MSR_KW: msr}}]}},
        "size": 1,
    }
    result = _os_search(_ALL_INDICES).search_raw(body)
    rows = _rows(result, None)
    return rows[0] if rows else None  # None (not raise) keeps 404 handling


def search_meas_hist(
    tool_type: ToolType | None = None,
    fab: list[str] | None = None,
    model: list[str] | None = None,
    eq: list[str] | None = None,
    recipe: list[str] | None = None,
    lot: list[str] | None = None,
    msr: list[str] | None = None,
    q: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
) -> MeasHistSearchResponse:
    start, end, out_of_retention, reported_end = _resolve_window(date_from, date_to)
    _, ceiling = _retention_window()

    offset = max(offset, 0)
    limit = max(1, min(limit, DEFAULT_LIMIT * 10))

    total = 0
    rows: list[MeasHistRow] = []
    recipe_names: list[MeasHistRecipeName] = []
    recipe_terms = [value for value in (recipe or []) if value.strip()]
    recipe_names_complete = False
    if not out_of_retention:
        # Values within a field OR together (terms); fields AND together
        # (filter context). List values are uppercased to match the stored
        # uppercase codes — EXCEPT msr, which is case-sensitive by contract.
        clauses: list[dict[str, Any]] = [_time_range_clause(start, end)]
        if fab:
            clauses.append({"terms": {_FAB_KW: [v.upper() for v in fab]}})
        if model:
            clauses.append({"terms": {_MODEL_KW: [v.upper() for v in model]}})
        if eq:
            clauses.append({"terms": {_EQP_KW: [v.upper() for v in eq]}})
        if lot:
            clauses.append({"terms": {_LOT_ID_KW: [v.upper() for v in lot]}})
        if msr:
            clauses.append({"terms": {_MSR_KW: list(msr)}})
        recipe_clause = _recipe_clause(recipe_terms)
        if recipe_clause:
            clauses.append(recipe_clause)
        # q fallback: substring wildcard across the real source fields — see
        # the module docstring's "q free-text search" note.
        q_clause = _wildcard_or(q or [], _Q_FIELDS)
        if q_clause:
            clauses.append(q_clause)

        # from+size must stay inside index.max_result_window (the same 10000
        # the mock truncates to); a page starting past it is legally empty.
        from_ = min(offset, MAX_RESULT_WINDOW)
        size = max(min(limit, MAX_RESULT_WINDOW - from_), 0)
        query = {"bool": {"filter": clauses}}
        body: dict[str, Any] = {
            "query": query,
            "sort": [{_TIME_F: "desc"}],
            "from": from_,
            "size": size,
            "track_total_hits": True,
        }
        result = _os_search(_indices(tool_type)).search_raw(body)
        total = _total(result)
        rows = _rows(result, tool_type) if size > 0 else []
        if recipe_terms:
            # A `fabs` terms sub-agg per full_name bucket — same pattern the
            # recipe_tat/fail_issue office rankings use. The outer query
            # already carries any fab filter, so the sub-agg only ever sees
            # in-scope fabs.
            buckets = _composite_buckets(
                _indices(tool_type),
                _FULL_KW,
                {"fabs": {"terms": {"field": _FAB_KW, "size": _RECIPE_FABS_SIZE}}},
                query,
            )
            pair_set: set[tuple[str, str]] = set()
            for bucket_position, bucket in enumerate(buckets, start=1):
                value = bucket["key"]["group"]
                if not isinstance(value, str) or not value.strip():
                    raise RuntimeError(
                        "OpenSearch full_name composite "
                        f"bucket {bucket_position} for {_indices(tool_type)!r} "
                        "'key.group' must be a nonblank string; "
                        f"got {type(value).__name__}."
                    )
                full_name = value.strip()
                fabs_agg = bucket.get("fabs")
                if not isinstance(fabs_agg, dict) or not isinstance(
                    fabs_agg.get("buckets"), list
                ):
                    raise RuntimeError(
                        "OpenSearch full_name composite "
                        f"bucket {bucket_position} for {_indices(tool_type)!r} "
                        "is missing the 'fabs' terms sub-aggregation."
                    )
                fab_values: list[str] = []
                for fab_position, fab_bucket in enumerate(
                    fabs_agg["buckets"], start=1
                ):
                    fab_value = (
                        fab_bucket.get("key")
                        if isinstance(fab_bucket, dict)
                        else None
                    )
                    if not isinstance(fab_value, str) or not fab_value.strip():
                        raise RuntimeError(
                            "OpenSearch full_name composite "
                            f"bucket {bucket_position} fab bucket "
                            f"{fab_position} for {_indices(tool_type)!r} "
                            "'key' must be a nonblank string; "
                            f"got {type(fab_value).__name__}."
                        )
                    fab_values.append(fab_value.strip())
                # Docs with no fab_name at all (dirty office data) must not
                # hide the recipe: keep the name discoverable with an empty
                # fab — "owner unknown" per the contract.
                for fab_value in fab_values or [""]:
                    pair_set.add((full_name, fab_value))
            recipe_names = [
                MeasHistRecipeName(full_name=name, fab_name=fab)
                for name, fab in sorted(pair_set)
            ]
            recipe_names_complete = True

    return MeasHistSearchResponse(
        total=total,
        capped=total > MAX_RESULT_WINDOW,
        recipe_names=recipe_names,
        recipe_names_complete=recipe_names_complete,
        offset=offset,
        limit=limit,
        range={
            "from": start.strftime("%Y-%m-%d"),
            # Caller-facing INCLUSIVE end date, not the shifted filter bound.
            "to": reported_end.strftime("%Y-%m-%d"),
            "anchor": ceiling.strftime("%Y-%m-%d"),
        },
        out_of_retention=out_of_retention,
        rows=rows,
    )


def get_meas_hist_facets(tool_type: ToolType | None = None) -> MeasHistFacetsResponse:
    """Dropdown options — only values that actually exist inside retention.

    Terms aggregations ordered by key (the mock sorts alphabetically).
    Recipe is deliberately NOT aggregated (hundreds of values) — recipe
    discovery goes through the search bar, same as the mock.
    """
    floor, ceiling = _retention_window()
    query = {"bool": {"filter": [_time_range_clause(floor, ceiling)]}}

    aggs = {
        "fab": {"terms": {"field": _FAB_KW, "size": _FACET_SIZE, "order": {"_key": "asc"}}},
        "model": {"terms": {"field": _MODEL_KW, "size": _FACET_SIZE, "order": {"_key": "asc"}}},
        "eq": {"terms": {"field": _EQP_KW, "size": _FACET_SIZE, "order": {"_key": "asc"}}},
    }
    result = _aggregate(_indices(tool_type), aggs, query)

    def facet(name: str) -> list[MeasHistFacetValue]:
        return [
            MeasHistFacetValue(value=str(b["key"]), count=int(b["doc_count"]))
            for b in result.get(name, {}).get("buckets", [])
        ]

    return MeasHistFacetsResponse(
        tool_type=tool_type,
        anchor=ceiling.strftime("%Y-%m-%d"),
        retention_days=RETENTION_DAYS,
        fab=facet("fab"),
        model=facet("model"),
        eq=facet("eq"),
    )


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.meas_hist.providers.office
    # (`python path/to/office.py` will NOT work: package imports need -m.)
    # The shared client loads back_dev_home/.env itself if the env isn't set.
    facets = get_meas_hist_facets("cd-sem")
    print(f"anchor={facets['anchor']}  retention={facets['retention_days']}d")
    print(f"fabs:   {[(f['value'], f['count']) for f in facets['fab']]}")
    print(f"models: {[(f['value'], f['count']) for f in facets['model']][:8]}")
    print(f"eqs:    {len(facets['eq'])} distinct")

    # The skewvoir default: no 카테고리 picked -> tool_type=None -> one request
    # across BOTH aliases. Rows must come back with a per-hit tool_type.
    both = search_meas_hist(limit=5)
    families = {row["tool_type"] for row in both["rows"]}
    print(
        f"\nsearch BOTH indices: total={both['total']} families_seen={families} "
        "(hvsem rows only appear if that alias has recent data)"
    )

    page = search_meas_hist(tool_type="cd-sem", limit=5)
    print(
        f"\nsearch (cd-sem only): total={page['total']} capped={page['capped']} "
        f"range={page['range']}"
    )
    for row in page["rows"]:
        # Raw timestamps printed alongside parsed fields — a trailing Z or
        # +09:00 here means the KST-as-UTC assumption is broken (see
        # _office_meas_hist docstring).
        print(
            f"  {row['timestamp']!r}  {row['eqp_id']:<10} {row['full_name']:<30} "
            f"lot_cd={row['lot_cd'] or '(unmapped)'} vendor={row['vendor_nm']} "
            f"align={row['align_fail']} msr_check={row['msr_check']}"
        )

    if page["rows"]:
        probe = page["rows"][0]["msr"]
        found = find_meas_hist_by_msr(probe)
        print(f"\nfind_by_msr({probe!r}): {'OK' if found else 'MISSING'}")
        missing = find_meas_hist_by_msr("__no_such_msr__")
        print(f"find_by_msr(unknown): {missing!r} (must be None)")
