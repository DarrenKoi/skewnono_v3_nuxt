"""측정 이력(meas_hist) — shared mock data for recipe-search 측정 이력 view and 스큐보아.

Spec: docs/datatables/meas_hist.txt
Each row = "장비가 특정 lot에 특정 recipe를 실행한 1회 측정 이력".

Office counterpart: OpenSearch, one alias per tool family — `meas_hist_cdsem`
and `meas_hist_hvsem`, one document per measurement execution. This is the most
widely read office source in the project (`meas_hist`, `recipe_tat`,
`fail_issue`, `msr_file`, `lateral_recipe`), so the mock↔office gaps below
matter well beyond this module.

FOUR CONTRACT FIELDS DO NOT EXIST IN THE OFFICE DOCUMENTS and are derived at
query time. A row here carries them natively, which is exactly why they are easy
to forget:

    id         = msr
    tool_type  = which alias the hit came from (its `_index`), not a field
    lot_cd     = resolved through `ebeam_tas_lot_hist` (the only lot_id -> lot_cd
                 bridge); unmapped becomes "", the row is never dropped
    vendor_nm  = derived from the eqp_model_cd prefix (VERITY* -> AMAT,
                 otherwise HITACHI)

Other office properties this mock cannot demonstrate:

* `fail_ratio` is a PERCENT (0..100) already computed at ingest. Office adapters
  read it as stored and never re-derive it from the image counts.
* text fields are analyzed, so exact match and aggregation go through `.keyword`
  (class_name/recipe_name/full_name/fab_name/eqp_id/lot_id).
* timestamps are offset-less KST wall clock, treated as UTC consistently
  throughout — range filters, day histograms (no `time_zone`), and the max-
  timestamp anchor all operate on the same values.
* the date-picker ceiling is the anchor = max(timestamp) across BOTH aliases —
  the latest data date, not wall clock — and recipe_tat and fail_issue share one
  cached anchor so the recipe-status tabs always agree on 데이터 기준 날짜.
* pagination is from/size with from+size <= 10000 (index.max_result_window).
* every mock row carries a nonblank `fab_name`, so the office dirty-data path
  where documents LACK the field — surfacing in the `recipe_names` snapshot as
  `fab_name: ""` ("owner unknown", OFFICE-VERIFY) — never exercises at home.

★ INGESTION PREREQUISITE for `q` free-text search: it queries the `search_all`
wildcard field (`meas_hist/opensearch_query.py`). If the loader has not indexed
that field, a `q` condition matches NOTHING and raises no error — an empty
result indistinguishable from "no such measurement".
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal

from back_dev_home.ebeam.hitachi._tool_specs import ToolType, model_to_tool_type
from back_dev_home.meas_hist.contracts import (
    MeasHistFacetsResponse,
    MeasHistFacetValue,
    MeasHistRecipeName,
    MeasHistResponse,
    MeasHistRow,
    MeasHistSearchResponse,
)
from back_dev_home.meas_hist.opensearch_query import SEARCHABLE_SOURCE_FIELDS
from back_dev_home.meas_hist.providers._shared import fail_ratio_percent
from back_dev_home.sem_list.contracts import SemListRow
from back_dev_home.sem_list.providers.mock import get_sem_list


__all__ = [
    "MeasHistRow",
    "MeasHistResponse",
    "MeasHistSearchResponse",
    "MeasHistFacetsResponse",
    "ToolType",
    "get_meas_hist",
    "find_meas_hist_by_msr",
    "search_meas_hist",
    "get_meas_hist_facets",
    "RETENTION_DAYS",
    "MAX_RESULT_WINDOW",
    "DEFAULT_LIMIT",
    "MOCK_SEARCH_FIXTURES",
]


RECIPE_CATALOG: dict[str, tuple[str, ...]] = {
    "ADI": ("ADI_CD_BIAS_001", "ADI_PITCH_002", "ADI_CD_BIAS_ABC123_STD_00001", "ADI_CD_BIAS_ABC123_PROD_00006"),
    "AEI": ("AEI_OVERLAY_001", "AEI_CD_002", "AEI_OVERLAY_ABC123_MON_00002"),
    "OVL": ("OVL_BOX_001", "OVL_AIM_002"),
    "GATE": ("GATE_PITCH_001", "GATE_HEIGHT_002", "GATE_PITCH_MON_ABC123_ENG_00009"),
    "CNT": ("CNT_HOLE_001", "CNT_DEPTH_002", "CNT_CONTACT_CHECK_ABC123_QUAL_00008"),
    "QC": ("QC_DAILY_MATCH_001", "QC_DAILY_MATCH_007", "QC_DAILY_MATCH_ABC123_PROD_00007"),
    "DEF": ("DEF_REVIEW_001",),
    "EDGE": ("EDGE_PROFILE_001", "EDGE_PROFILE_SCAN_ABC123_STD_00010")
}

NOW = datetime(2026, 5, 10, tzinfo=timezone.utc)
HISTORY_DAYS = 60
MOCK_ROW_COUNT = 600
SYNTH_ROW_COUNT_RANGE = (8, 20)

# Stable rows for home development and contract tests. Randomly generated rows
# remain useful for realistic volume, but UI examples must never depend on a
# random sequence or on sem_list seed changes elsewhere in the repository.
MOCK_SEARCH_FIXTURES: tuple[MeasHistRow, ...] = (
    MeasHistRow(
        id="msr_search_cdsem",
        fac_id="M11",
        fab_name="M11A",
        vendor_nm="HITACHI",
        eqp_id="ECXDX925",
        eqp_ip="10.41.12.87",
        eqp_model_cd="CG6300",
        tool_type="cd-sem",
        lot_cd="6LD",
        lot_id="6LD257421",
        class_name="ADI",
        recipe_name="ADI_CD_BIAS_001",
        full_name="ADI/ADI_CD_BIAS_001",
        timestamp="2026-05-09T12:00:00Z",
        start_time="2026-05-09T11:58:00Z",
        end_time="2026-05-09T12:00:00Z",
        meastime=120,
        msr="20260509_ADI_CD_BIAS_001_6LD257421_ECXDX925",
        msr_check="Yes",
        align_fail="Pass",
        total_images=120,
        fail_images=0,
        fail_ratio=0.0,
        idp_name="/Recipe/ADI/ADI_CD_BIAS_001.idp",
        idw_name="/Recipe/ADI/ADI_CD_BIAS_001.idw"
    ),
    MeasHistRow(
        id="msr_search_hvsem",
        fac_id="M14",
        fab_name="M14B",
        vendor_nm="AMAT",
        eqp_id="MCD018",
        eqp_ip="10.44.9.153",
        eqp_model_cd="TP3000",
        tool_type="hv-sem",
        lot_cd="RKPB",
        lot_id="RKPB240012",
        class_name="CNT",
        recipe_name="CNT_CONTACT_CHECK_001",
        full_name="CNT/CNT_CONTACT_CHECK_001",
        timestamp="2026-05-09T11:00:00Z",
        start_time="2026-05-09T10:57:00Z",
        end_time="2026-05-09T11:00:00Z",
        meastime=180,
        msr="20260509_CNT_CONTACT_CHECK_001_RKPB240012_MCD018",
        msr_check="Yes",
        align_fail="Pass",
        total_images=180,
        fail_images=1,
        fail_ratio=0.5556,  # 1/180 images, as a percent
        idp_name="/Recipe/CNT/CNT_CONTACT_CHECK_001.idp",
        idw_name="/Recipe/CNT/CNT_CONTACT_CHECK_001.idw"
    )
)


def _seed(*values: str | None) -> int:
    digest = hashlib.sha256(":".join(value or "" for value in values).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _r_lot_cd(rng: random.Random) -> str:
    letters = "".join(rng.choice("ABCDEFGHJKLMNPRSTVWXY") for _ in range(3))
    return f"R{letters}"


def _m_lot_cd(rng: random.Random) -> str:
    return rng.choice(("4MJ", "5KP", "6LD", "7HA", "MJD", "KPB"))


def _make_lot_id(lot_cd: str, rng: random.Random) -> str:
    suffix = f"{rng.randint(2400, 2699):04d}{rng.randint(10, 99):02d}"
    return f"{lot_cd}{suffix}"


def _make_msr(date_str: str, recipe_name: str, lot_id: str, eqp_id: str) -> str:
    return f"{date_str}_{recipe_name}_{lot_id}_{eqp_id}"


def _build_row(
    eqp: SemListRow,
    rng: random.Random,
    index: int,
    max_age_days: int = HISTORY_DAYS
) -> MeasHistRow | None:
    """One measurement row aged 0..``max_age_days`` before ``NOW``.

    ``max_age_days`` exists so recipe synthesis can land inside the narrower
    측정 이력 window; the default keeps the 600-row universe spread across
    full retention, and consumes the same one rng draw either way, so the
    seeded universe is byte-identical.
    """
    tool_type = model_to_tool_type(eqp["eqp_model_cd"])
    if tool_type is None:
        return None

    lot_cd = _r_lot_cd(rng) if eqp["fac_id"] == "R3" else _m_lot_cd(rng)
    lot_id = _make_lot_id(lot_cd, rng)

    class_name = rng.choice(tuple(RECIPE_CATALOG.keys()))
    recipe_name = rng.choice(RECIPE_CATALOG[class_name])
    full_name = f"{class_name}/{recipe_name}"

    end_time = NOW - timedelta(
        days=rng.randint(0, max_age_days),
        hours=rng.randint(0, 23),
        minutes=rng.randint(0, 59)
    )
    meastime = rng.randint(60, 1800)
    start_time = end_time - timedelta(seconds=meastime)
    timestamp = end_time

    msr_check: Literal["Yes", "No"] = "No" if rng.random() < 0.08 else "Yes"
    align_fail: Literal["Pass", "Fail", "NA"] = rng.choices(
        ("Pass", "Fail", "NA"),
        weights=(0.82, 0.12, 0.06),
        k=1
    )[0]

    # Percent, 0..100 — the office scale (see providers/_shared.py). The
    # bands come from docs/datatables/meas_hist.txt rule #9.
    if msr_check == "No" or align_fail == "Fail":
        fail_ratio = round(rng.uniform(15.0, 80.0), 4)
    else:
        fail_ratio = round(rng.uniform(0.0, 15.0), 4)

    total_images = rng.randint(40, 400)
    fail_images = int(total_images * fail_ratio / 100)
    fail_ratio = fail_ratio_percent(fail_images, total_images)

    date_str = end_time.strftime("%Y%m%d")
    msr = _make_msr(date_str, recipe_name, lot_id, eqp["eqp_id"])

    return MeasHistRow(
        id=f"msr_{index:06d}",
        fac_id=eqp["fac_id"],
        fab_name=eqp["fab_name"],
        vendor_nm=eqp["vendor_nm"],
        eqp_id=eqp["eqp_id"],
        eqp_ip=eqp["eqp_ip"],
        eqp_model_cd=eqp["eqp_model_cd"],
        tool_type=tool_type,
        lot_cd=lot_cd,
        lot_id=lot_id,
        class_name=class_name,
        recipe_name=recipe_name,
        full_name=full_name,
        timestamp=timestamp.isoformat().replace("+00:00", "Z"),
        start_time=start_time.isoformat().replace("+00:00", "Z"),
        end_time=end_time.isoformat().replace("+00:00", "Z"),
        meastime=meastime,
        msr=msr,
        msr_check=msr_check,
        align_fail=align_fail,
        total_images=total_images,
        fail_images=fail_images,
        fail_ratio=fail_ratio,
        idp_name=f"/Recipe/{class_name}/{recipe_name}.idp",
        idw_name=f"/Recipe/{class_name}/{recipe_name}.idw"
    )


@lru_cache(maxsize=1)
def _eligible_sem_rows() -> tuple[SemListRow, ...]:
    return tuple(row for row in get_sem_list() if model_to_tool_type(row["eqp_model_cd"]) is not None)


@lru_cache(maxsize=1)
def _all_rows() -> tuple[MeasHistRow, ...]:
    rng = random.Random(_seed("meas_hist", "v1"))
    sem_rows = _eligible_sem_rows()

    rows: list[MeasHistRow] = list(MOCK_SEARCH_FIXTURES)
    for index in range(len(rows), MOCK_ROW_COUNT):
        eqp = rng.choice(sem_rows)
        row = _build_row(eqp, rng, index)
        if row is not None:
            rows.append(row)

    return tuple(rows)


@lru_cache(maxsize=1)
def _rows_by_msr() -> dict[str, MeasHistRow]:
    return {row["msr"]: row for row in _all_rows()}


def find_meas_hist_by_msr(msr: str) -> MeasHistRow | None:
    """Look up the parent measurement-history row for an msr.

    스큐보아(skewvoir) opens an MSR's raw detail (msr_file) and needs the
    parent row's class_name / total_images. Only the pre-built mock rows are
    indexed; recipe-search synthesized rows are not, since the UI selects from
    real meas_hist rows before opening detail.
    """
    return _rows_by_msr().get(msr)


def _split_recipe(recipe_name: str) -> tuple[str, str]:
    if "/" in recipe_name:
        class_part, recipe_part = recipe_name.split("/", 1)
        return class_part, recipe_part
    return "ADI", recipe_name


def _synthesize_for_recipe(
    recipe_name: str,
    tool_type: ToolType | None,
    fab_name: str | None
) -> list[MeasHistRow]:
    rng = random.Random(_seed("synth", recipe_name, fab_name, tool_type))

    sem_rows: list[SemListRow] = list(_eligible_sem_rows())
    if tool_type:
        sem_rows = [row for row in sem_rows if model_to_tool_type(row["eqp_model_cd"]) == tool_type]
    if fab_name:
        sem_rows = [row for row in sem_rows if row["fab_name"].upper() == fab_name.upper()]

    if not sem_rows:
        return []

    class_part, recipe_part = _split_recipe(recipe_name)
    full_name = f"{class_part}/{recipe_part}"

    count = rng.randint(*SYNTH_ROW_COUNT_RANGE)
    rows: list[MeasHistRow] = []

    for index in range(count):
        eqp = rng.choice(sem_rows)
        # Aged within the 측정 이력 window: synthesis exists so that view is
        # never empty for an unknown recipe, and rows older than the window
        # would be filtered straight back out by the caller.
        base = _build_row(eqp, rng, 900_000 + index, max_age_days=RECIPE_HISTORY_DAYS)
        if base is None:
            continue

        date_str = base["end_time"][:10].replace("-", "")
        rows.append({
            **base,
            "class_name": class_part,
            "recipe_name": recipe_part,
            "full_name": full_name,
            "idp_name": f"/Recipe/{class_part}/{recipe_part}.idp",
            "idw_name": f"/Recipe/{class_part}/{recipe_part}.idw",
            "msr": _make_msr(date_str, recipe_part, base["lot_id"], base["eqp_id"])
        })

    return rows


def _matches_recipe(row: MeasHistRow, recipe_name: str) -> bool:
    return row["full_name"] == recipe_name or row["recipe_name"] == recipe_name


def get_meas_hist(
    tool_type: ToolType | None = None,
    fab_name: str | None = None,
    recipe_name: str | None = None
) -> MeasHistResponse:
    fab_normalized = (fab_name or "").upper() or None

    matched: list[MeasHistRow] = [
        row for row in _all_rows()
        if (not tool_type or row["tool_type"] == tool_type)
        and (not fab_normalized or row["fab_name"].upper() == fab_normalized)
        and (not recipe_name or _matches_recipe(row, recipe_name))
    ]

    # Synthesis is decided BEFORE the window, not after: it exists to cover a
    # recipe the mock universe has never heard of. Deciding after would make a
    # recipe whose real rows are merely old (31-60 days) look unknown, and
    # fabricate fresh history on top of history that actually exists.
    if recipe_name and not matched:
        matched = _synthesize_for_recipe(recipe_name, tool_type, fab_normalized)

    cutoff = RETENTION_ANCHOR - timedelta(days=RECIPE_HISTORY_DAYS)
    rows = [row for row in matched if _row_time(row) >= cutoff]
    rows.sort(key=lambda r: r["timestamp"], reverse=True)

    return MeasHistResponse(
        tool_type=tool_type,
        fab_name=fab_normalized,
        recipe_name=recipe_name,
        total=len(rows),
        rows=rows
    )


# --- Search -----------------------------------------------------------------
#
# Phase 1 filters the seeded rows in memory. Phase 2/3 replaces the bodies of
# search_meas_hist / get_meas_hist_facets with OpenSearch queries (a
# bool{must:[terms...]} + a terms aggregation). Routes and frontend do not change.

RETENTION_DAYS = 60
# The 측정 이력 tab's window. Narrower than retention on purpose: that view
# answers "how has this recipe been running lately", and a recipe measured
# every few minutes produces far more rows over 60 days than anyone reads.
# The wider retention window still governs /meas-hist/search, where the user
# has explicit date controls. Shared with the office adapter so the two
# phases cannot disagree about how much history "default" means.
RECIPE_HISTORY_DAYS = 30
# OpenSearch index.max_result_window default. A retrieval ceiling, not a promise
# to the browser: `total` may exceed it, in which case `capped` is True.
MAX_RESULT_WINDOW = 10000
DEFAULT_LIMIT = 50

# The clock the retention window is measured from. Phase 1 pins it to the mock's
# frozen NOW so the 60-day window actually contains the seeded rows; Phase 2/3
# swaps this one line for datetime.now(timezone.utc).
RETENTION_ANCHOR = NOW


def _parse_date(value: str | None) -> tuple[datetime | None, bool]:
    """Parse a caller-supplied `from`/`to` bound.

    Returns (parsed, invalid). `invalid` is True only when `value` was
    PRESENT (non-empty) but failed to parse as `%Y-%m-%d` — a caller error
    (e.g. `2026-13-45`), distinct from the value being genuinely ABSENT
    (None/empty), which legitimately means "no bound" and defaults to the
    retention window. Conflating the two (as returning bare `None` for both
    used to do) let an unparseable date silently widen the query to the full
    60-day window instead of the honest zero rows a bad date deserves.
    """
    if not value or not value.strip():
        return None, False
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc), False
    except ValueError:
        return None, True


def _retention_window() -> tuple[datetime, datetime]:
    end = RETENTION_ANCHOR
    return end - timedelta(days=RETENTION_DAYS), end


def _resolve_window(
    date_from: str | None,
    date_to: str | None
) -> tuple[datetime, datetime, bool, datetime]:
    """Intersect the caller's range with the retention window.

    The window is a guarantee, not a default: a stale bookmark or a hand-edited
    URL must never widen the scan past retention. Returns (start, end,
    out_of_retention, reported_end) — the flag says the caller's range fell
    entirely outside (or, see below, was unparseable).

    `end` is the FILTERING bound: `date_to` shifted one day forward so the
    comparison `ts <= end` includes the whole of `date_to`. That shift is an
    internal implementation detail — callers reporting the applied range back
    to the caller (e.g. the `range` field in the search response) must use
    `reported_end` instead, which stays the caller-facing INCLUSIVE end date
    (clamped to the retention ceiling, never pushed a day past it).

    A PRESENT-but-unparseable `from`/`to` (e.g. `2026-13-45`) is a caller
    error, not an absent bound — it must not fall back to "no bound", which
    would silently widen the scan to the full retention window and answer a
    single-date query with everything (Fix 1). It is treated the same as a
    range that falls entirely outside retention: zero rows, `out_of_retention`
    True. A genuinely ABSENT (empty/omitted) `from`/`to` is unaffected and
    still defaults to the retention window, exactly as before.
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
    # `to` is inclusive of the whole day for FILTERING purposes only.
    end = min(requested_end + timedelta(days=1), ceiling) if requested_end else ceiling
    reported_end = min(requested_end, ceiling) if requested_end else ceiling

    if start > end:
        return floor, ceiling, True, ceiling

    return start, end, False, reported_end


def _row_time(row: MeasHistRow) -> datetime:
    return datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))


def _matches_recipe_term(row: MeasHistRow, term: str) -> bool:
    """Recipe terms are substrings — the search bar accepts fragments."""
    needle = term.lower()
    return needle in row["full_name"].lower() or needle in row["recipe_name"].lower()


def _matches_any_term(row: MeasHistRow, terms: list[str]) -> bool:
    """OR fallback terms across an explicit field allowlist."""
    needles = [term.casefold() for term in terms if term]
    if not needles:
        return True
    haystacks = [str(row[field]).casefold() for field in SEARCHABLE_SOURCE_FIELDS]
    return any(needle in value for needle in needles for value in haystacks)


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
    limit: int = DEFAULT_LIMIT
) -> MeasHistSearchResponse:
    start, end, out_of_retention, reported_end = _resolve_window(date_from, date_to)

    fab_set = {v.upper() for v in (fab or [])}
    model_set = {v.upper() for v in (model or [])}
    eq_set = {v.upper() for v in (eq or [])}
    lot_set = {v.upper() for v in (lot or [])}
    msr_set = set(msr or [])
    recipe_terms = [v for v in (recipe or []) if v]
    q_terms = [v for v in (q or []) if v]

    rows: list[MeasHistRow] = []
    if not out_of_retention:
        for row in _all_rows():
            if tool_type and row["tool_type"] != tool_type:
                continue

            ts = _row_time(row)
            if ts < start or ts > end:
                continue

            # Values within a field OR together; fields AND together.
            if fab_set and row["fab_name"].upper() not in fab_set:
                continue
            if model_set and row["eqp_model_cd"].upper() not in model_set:
                continue
            if eq_set and row["eqp_id"].upper() not in eq_set:
                continue
            if lot_set and row["lot_id"].upper() not in lot_set:
                continue
            if msr_set and row["msr"] not in msr_set:
                continue
            if recipe_terms and not any(_matches_recipe_term(row, t) for t in recipe_terms):
                continue
            if q_terms and not _matches_any_term(row, q_terms):
                continue

            rows.append(row)

    # (full_name, fab_name) pairs, not bare names — the recipe-search
    # fallback badges and owner-routes each discovered name by fab, and every
    # matching row already carries its fab.
    recipe_names: list[MeasHistRecipeName] = (
        [
            MeasHistRecipeName(full_name=name, fab_name=fab)
            for name, fab in sorted({(row["full_name"], row["fab_name"]) for row in rows})
        ]
        if recipe_terms
        else []
    )

    rows.sort(key=lambda r: r["timestamp"], reverse=True)

    total = len(rows)
    capped = total > MAX_RESULT_WINDOW
    retrievable = rows[:MAX_RESULT_WINDOW]

    offset = max(offset, 0)
    limit = max(1, min(limit, DEFAULT_LIMIT * 10))
    page = retrievable[offset:offset + limit]

    return MeasHistSearchResponse(
        total=total,
        capped=capped,
        recipe_names=recipe_names,
        recipe_names_complete=bool(recipe_terms) and not out_of_retention,
        offset=offset,
        limit=limit,
        range={
            "from": start.strftime("%Y-%m-%d"),
            # Inclusive end date as the caller understands it — NOT `end`,
            # which is shifted one day forward internally so the filtering
            # comparison covers the whole of the last day (Fix 4).
            "to": reported_end.strftime("%Y-%m-%d"),
            "anchor": RETENTION_ANCHOR.strftime("%Y-%m-%d")
        },
        out_of_retention=out_of_retention,
        rows=page
    )


def _facet_counts(rows: tuple[MeasHistRow, ...], key: str) -> list[MeasHistFacetValue]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[key]] = counts.get(row[key], 0) + 1
    return [
        MeasHistFacetValue(value=value, count=count)
        for value, count in sorted(counts.items())
    ]


def get_meas_hist_facets(tool_type: ToolType | None = None) -> MeasHistFacetsResponse:
    """Dropdown options — only values that actually exist inside retention.

    Recipe is intentionally NOT aggregated here: the office index carries
    hundreds of recipes, and loading them all into a dropdown just to let the
    user pick one (or throw the rest away) is the exact cost this endpoint
    must avoid. Recipes are found via the search bar's free-text `recipe`
    parameter instead (substring match against full_name/recipe_name in
    search_meas_hist), never via a facet list.

    Phase 2/3: a terms aggregation over the same bool filter.
    """
    start, end = _retention_window()

    rows = tuple(
        row for row in _all_rows()
        if (not tool_type or row["tool_type"] == tool_type)
        and start <= _row_time(row) <= end
    )

    return MeasHistFacetsResponse(
        tool_type=tool_type,
        anchor=RETENTION_ANCHOR.strftime("%Y-%m-%d"),
        retention_days=RETENTION_DAYS,
        fab=_facet_counts(rows, "fab_name"),
        model=_facet_counts(rows, "eqp_model_cd"),
        eq=_facet_counts(rows, "eqp_id")
    )
