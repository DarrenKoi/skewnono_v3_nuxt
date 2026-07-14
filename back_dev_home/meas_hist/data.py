"""측정 이력(meas_hist) — shared mock data for recipe-search 측정 이력 view and 스큐보아.

Spec: docs/datatables/meas_hist.txt
Each row = "장비가 특정 lot에 특정 recipe를 실행한 1회 측정 이력".
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi._tool_specs import ToolType, model_to_tool_type
from back_dev_home.sem_list.data import SemListRow, get_sem_list


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
]


class MeasHistRow(TypedDict):
    id: str
    fac_id: str
    fab_name: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    eqp_id: str
    eqp_model_cd: str
    tool_type: ToolType
    lot_cd: str
    lot_id: str
    class_name: str
    recipe_name: str
    full_name: str
    timestamp: str
    start_time: str
    end_time: str
    meastime: int
    msr: str
    msr_check: Literal["Yes", "No"]
    align_fail: Literal["Pass", "Fail", "NA"]
    total_images: int
    fail_images: int
    fail_ratio: float
    idp_name: str
    idw_name: str


class MeasHistResponse(TypedDict):
    tool_type: ToolType | None
    fab_name: str | None
    recipe_name: str | None
    total: int
    rows: list[MeasHistRow]


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


def _build_row(eqp: SemListRow, rng: random.Random, index: int) -> MeasHistRow | None:
    tool_type = model_to_tool_type(eqp["eqp_model_cd"])
    if tool_type is None:
        return None

    lot_cd = _r_lot_cd(rng) if eqp["fac_id"] == "R3" else _m_lot_cd(rng)
    lot_id = _make_lot_id(lot_cd, rng)

    class_name = rng.choice(tuple(RECIPE_CATALOG.keys()))
    recipe_name = rng.choice(RECIPE_CATALOG[class_name])
    full_name = f"{class_name}/{recipe_name}"

    end_time = NOW - timedelta(
        days=rng.randint(0, HISTORY_DAYS),
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

    if msr_check == "No" or align_fail == "Fail":
        fail_ratio = round(rng.uniform(0.15, 0.8), 4)
    else:
        fail_ratio = round(rng.uniform(0.0, 0.15), 4)

    total_images = rng.randint(40, 400)
    fail_images = int(total_images * fail_ratio)
    fail_ratio = round(fail_images / total_images, 4) if total_images else 0.0

    date_str = end_time.strftime("%Y%m%d")
    msr = _make_msr(date_str, recipe_name, lot_id, eqp["eqp_id"])

    return MeasHistRow(
        id=f"msr_{index:06d}",
        fac_id=eqp["fac_id"],
        fab_name=eqp["fab_name"],
        vendor_nm=eqp["vendor_nm"],
        eqp_id=eqp["eqp_id"],
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

    rows: list[MeasHistRow] = []
    for index in range(MOCK_ROW_COUNT):
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
        base = _build_row(eqp, rng, 900_000 + index)
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

    rows: list[MeasHistRow] = [
        row for row in _all_rows()
        if (not tool_type or row["tool_type"] == tool_type)
        and (not fab_normalized or row["fab_name"].upper() == fab_normalized)
        and (not recipe_name or _matches_recipe(row, recipe_name))
    ]

    if recipe_name and not rows:
        rows = _synthesize_for_recipe(recipe_name, tool_type, fab_normalized)

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
# OpenSearch index.max_result_window default. A retrieval ceiling, not a promise
# to the browser: `total` may exceed it, in which case `capped` is True.
MAX_RESULT_WINDOW = 10000
DEFAULT_LIMIT = 50

# The clock the retention window is measured from. Phase 1 pins it to the mock's
# frozen NOW so the 60-day window actually contains the seeded rows; Phase 2/3
# swaps this one line for datetime.now(timezone.utc).
RETENTION_ANCHOR = NOW


class MeasHistSearchResponse(TypedDict):
    total: int
    capped: bool
    offset: int
    limit: int
    range: dict[str, str]
    out_of_retention: bool
    rows: list[MeasHistRow]


class MeasHistFacetValue(TypedDict):
    value: str
    count: int


class MeasHistFacetsResponse(TypedDict):
    tool_type: ToolType | None
    anchor: str
    retention_days: int
    fab: list[MeasHistFacetValue]
    model: list[MeasHistFacetValue]
    eq: list[MeasHistFacetValue]
    recipe: list[MeasHistFacetValue]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _retention_window() -> tuple[datetime, datetime]:
    end = RETENTION_ANCHOR
    return end - timedelta(days=RETENTION_DAYS), end


def _resolve_window(
    date_from: str | None,
    date_to: str | None
) -> tuple[datetime, datetime, bool]:
    """Intersect the caller's range with the retention window.

    The window is a guarantee, not a default: a stale bookmark or a hand-edited
    URL must never widen the scan past retention. Returns (start, end,
    out_of_retention) — the flag says the caller's range fell entirely outside.
    """
    floor, ceiling = _retention_window()

    requested_start = _parse_date(date_from)
    requested_end = _parse_date(date_to)

    if requested_start and requested_start > ceiling:
        return floor, ceiling, True
    if requested_end and requested_end < floor:
        return floor, ceiling, True

    start = max(requested_start, floor) if requested_start else floor
    # `to` is inclusive of the whole day.
    end = min(requested_end + timedelta(days=1), ceiling) if requested_end else ceiling

    if start > end:
        return floor, ceiling, True

    return start, end, False


def _row_time(row: MeasHistRow) -> datetime:
    return datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))


def _matches_recipe_term(row: MeasHistRow, term: str) -> bool:
    """Recipe terms are substrings — the search bar accepts fragments."""
    needle = term.lower()
    return needle in row["full_name"].lower() or needle in row["recipe_name"].lower()


def search_meas_hist(
    tool_type: ToolType | None = None,
    fab: list[str] | None = None,
    model: list[str] | None = None,
    eq: list[str] | None = None,
    recipe: list[str] | None = None,
    lot: list[str] | None = None,
    msr: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT
) -> MeasHistSearchResponse:
    start, end, out_of_retention = _resolve_window(date_from, date_to)

    fab_set = {v.upper() for v in (fab or [])}
    model_set = {v.upper() for v in (model or [])}
    eq_set = {v.upper() for v in (eq or [])}
    lot_set = {v.upper() for v in (lot or [])}
    msr_set = set(msr or [])
    recipe_terms = [v for v in (recipe or []) if v]

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

            rows.append(row)

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
        offset=offset,
        limit=limit,
        range={
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
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
        eq=_facet_counts(rows, "eqp_id"),
        recipe=_facet_counts(rows, "full_name")
    )
