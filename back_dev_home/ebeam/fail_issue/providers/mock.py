"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본 테이블:  docs/datatables/hitachi/meas_hist.txt
계약:        docs/api-contracts/fail-issue.yaml

Fail-issue mock data — measurement-history rows enriched with two failure
aspects derived from the meas_hist schema:

* `align_fail` (Pass/Fail/NA): wafer-alignment outcome at measurement start.
  Surfaced as a per-recipe ranking for the fail-issue table.
* `fail_ratio` > MEAS_FAIL_THRESHOLD: image-level failure during the run.
  A recipe-side problem — surfaced as a per-recipe ranking.

Phase 1 implementation reuses recipe_tat's 55,000-row meas_hist universe as
the source of (eqp, recipe, lot, timestamp) tuples and enriches each row
with deterministic fail metadata. Sharing the row universe keeps the two
dashboards consistent (a recipe with heavy TAT can also show high fails)
and avoids generating a parallel 55,000-row dataset. The equipment identity
in those rows comes from the sem_list roster, so this feature's per-tool
samples name real fleet tools too.

장비별 뷰(get_equipments / get_equipment_compare)가 흉내내는 것:

이 mock 의 실패는 FAB_ALIGN_FAIL_RATE · FAB_MEAS_FAIL_RATE 라는 **fab 단위
고정 스칼라**에서 나옵니다. 즉 mock 에는 "장비 개체차"가 존재하지 않으며,
같은 fab 안의 장비 지수는 순수하게 표본 변동만으로 흩어집니다. 그래서
집에서는 배지가 켜지는 것을 안정적으로 재현할 수 없습니다 — 지수 산식과
0채움·정렬 같은 **모양**은 여기서 검증되지만, 임계값이 실제로 맞는지는
사무실에서만 알 수 있습니다(OFFICE-VERIFY, MIGRATION.md).

fab 간에는 반대로 3배 차이(0.05~0.15)가 있어서, 여러 fab 을 함께 조회하면
지수가 장비가 아니라 fab 을 가리키는 편향이 즉시 재현됩니다. 프론트엔드가
다중 fab 조회에서 배지를 끄는 이유가 이것입니다.

장비별 편차를 여기에 지어내지 마십시오. 사무실 데이터에 대해 거짓을
가르치게 됩니다.

사무실 주의사항: 사무실 구현은 recipe_tat 결과에 join 하지 말고 OpenSearch
의 meas_hist 인덱스에서 align_fail/fail_ratio/msr_check 컬럼을 그대로
읽어와 동일한 집계 (count, rate, daily series) 를 수행해야 합니다.
MEAS_FAIL_THRESHOLD 의 값은 YAML 계약에 명시되어 있으므로 임의로
변경하지 마세요 — Phase 1/2 간 수치가 어긋날 수 있습니다.

Multi-fab filtering (`fab_names`) is a case-insensitive set union — a row
passes if its `fab_name` matches ANY entry; an empty tuple or `None` means
no fab filter at all.
"""

import random
from collections import Counter
from datetime import timedelta
from functools import lru_cache

from back_dev_home.ebeam._analytics import (
    MeasurementScope,
    fab_base,
    filter_measurements,
    lot_metadata,
    parse_iso_date,
)
from back_dev_home.ebeam.fail_issue.contracts import (
    AlignOutcome,
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    EquipmentComparePayload,
    EquipmentsPayload,
    FailRow,
    MeasRankingRow,
    MsrCheck,
    SummaryPayload,
)
from back_dev_home.ebeam.fail_issue.providers._shape import (
    EquipmentGridRow,
    build_equipment_compare_payload,
    build_equipments_payload,
)
from back_dev_home.ebeam.recipe_tat.providers.mock import (
    ANCHOR_TIME,
    MeasHistRow,
    ToolType,
    _generate_meas_hist,
)
# fail_ratio's scale (percent, 0..100) is defined once, by meas_hist — this
# feature reads the same column off the same index.
from back_dev_home.meas_hist.providers._shared import fail_ratio_percent


__all__ = [
    "ANCHOR_TIME",
    "MEAS_FAIL_THRESHOLD",
    "ToolType",
    "FailRow",
    "get_summary",
    "get_daily_trend",
    "get_align_ranking",
    "get_meas_ranking",
    "get_devices",
    "get_equipments",
    "get_equipment_compare"
]


# Threshold that promotes a meas_hist row to a "meas fail". Pinned to the
# datatable spec (docs/datatables/hitachi/meas_hist.txt rule #9 — "정상 row는 보통
# 0 ~ 15%"). The YAML contract repeats this constant; office must keep
# it in sync.
#
# Same scale as fail_ratio itself: PERCENT, 0..100. 15 means 15%.
MEAS_FAIL_THRESHOLD = 15.0


# Per-fab fail-rate personalities. Without this, switching fab in the
# sidebar would only change row counts — both KPIs and rankings would look
# identical across fabs. Keyed by `_fab_base` so M15A/B/C share the M15
# profile, mirroring recipe_tat's FAB_CLASS_MIX convention.
DEFAULT_ALIGN_FAIL_RATE = 0.10
FAB_ALIGN_FAIL_RATE: dict[str, float] = {
    "R3":  0.11,
    "R4":  0.06,
    "M11": 0.08,
    "M10": 0.05,
    "M14": 0.15,
    "M15": 0.09,
    "M16": 0.12
}

DEFAULT_MEAS_FAIL_RATE = 0.13
FAB_MEAS_FAIL_RATE: dict[str, float] = {
    "R3":  0.14,
    "R4":  0.08,
    "M11": 0.07,
    "M10": 0.12,
    "M14": 0.19,
    "M15": 0.10,
    "M16": 0.16
}

# Background rate of "NA" align — neither pass nor fail (skipped/aborted).
# Held constant across fabs because it correlates with tool state, not the
# fab itself.
ALIGN_NA_RATE = 0.05

# Background rate of msr_check == "No" (raw data missing). Same reasoning.
MSR_MISSING_RATE = 0.06


def _row_rng(row_id: str) -> random.Random:
    """Per-row deterministic RNG.

    Seeding off `row_id` (e.g. "MEAS-000123") makes the same row always
    enrich to the same fail fields regardless of call order. Without this
    each request would draw fresh outcomes and the dashboard would shimmer.
    """
    return random.Random(f"fail-issue::{row_id}")


def _enrich(row: MeasHistRow) -> FailRow:
    rng = _row_rng(row["id"])
    base_fab = fab_base(row["fab_name"])

    align_fail_rate = FAB_ALIGN_FAIL_RATE.get(base_fab, DEFAULT_ALIGN_FAIL_RATE)
    meas_fail_rate = FAB_MEAS_FAIL_RATE.get(base_fab, DEFAULT_MEAS_FAIL_RATE)

    # Align outcome: roll Fail then NA against fab-specific rate. Ordering
    # matters so Fail wins ties with NA, matching the datatable's
    # (Pass 0.82, Fail 0.12, NA 0.06) baseline weights.
    align_roll = rng.random()
    if align_roll < align_fail_rate:
        align_fail: AlignOutcome = "Fail"
    elif align_roll < align_fail_rate + ALIGN_NA_RATE:
        align_fail = "NA"
    else:
        align_fail = "Pass"

    msr_check: MsrCheck = "No" if rng.random() < MSR_MISSING_RATE else "Yes"

    # Per datatable rule #9: rows with align Fail or missing MSR get an
    # elevated fail_ratio band; otherwise stay below 15%. We use the
    # MEAS_FAIL_THRESHOLD anchor instead of hard-coding 15 so the band
    # logic and the threshold can't drift out of sync.
    is_problem = align_fail == "Fail" or msr_check == "No"
    # Also independently roll a fab-specific meas-fail event so the meas
    # ranking has signal even on align-Pass rows.
    if not is_problem and rng.random() < meas_fail_rate:
        is_problem = True

    if is_problem:
        fail_ratio = round(rng.uniform(MEAS_FAIL_THRESHOLD, 80.0), 4)
    else:
        fail_ratio = round(rng.uniform(0.0, MEAS_FAIL_THRESHOLD), 4)

    total_images = rng.randint(40, 400)
    fail_images = int(total_images * fail_ratio / 100)
    fail_ratio = fail_ratio_percent(fail_images, total_images)

    return FailRow(
        id=row["id"],
        fac_id=row["fac_id"],
        fab_name=row["fab_name"],
        vendor_nm=row["vendor_nm"],
        eqp_id=row["eqp_id"],
        eqp_model_cd=row["eqp_model_cd"],
        tool_type=row["tool_type"],
        lot_cd=row["lot_cd"],
        lot_id=row["lot_id"],
        class_name=row["class_name"],
        recipe_name=row["recipe_name"],
        full_name=row["full_name"],
        timestamp=row["timestamp"],
        align_fail=align_fail,
        msr_check=msr_check,
        total_images=total_images,
        fail_images=fail_images,
        fail_ratio=fail_ratio
    )


@lru_cache(maxsize=1)
def _all_fail_rows() -> tuple[FailRow, ...]:
    return tuple(_enrich(row) for row in _generate_meas_hist())


@lru_cache(maxsize=256)
def _filter_rows(
    tool_type: ToolType | None,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> tuple[FailRow, ...]:
    # Each page load hits summary + daily-trend + align-ranking +
    # meas-ranking with the same filter args. Memoizing here means the
    # 55,000-row scan runs once per unique window instead of four times.
    # `fab_names` must be a tuple (hashable), never a list — lru_cache
    # requires hashable arguments.
    return filter_measurements(
        _all_fail_rows(),
        MeasurementScope(tool_type, fab_names, start_date, end_date, lot_cd),
    )


# Aggregation helpers --------------------------------------------------------

def _is_align_fail(row: FailRow) -> bool:
    return row["align_fail"] == "Fail"


def _is_meas_fail(row: FailRow) -> bool:
    # NB: msr_check == "No" guarantees fail_ratio >= MEAS_FAIL_THRESHOLD by
    # construction, so the threshold check alone covers the "raw data
    # missing" case the datatable describes. Keeping a single criterion
    # also keeps the contract simple.
    return row["fail_ratio"] > MEAS_FAIL_THRESHOLD


def get_summary(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> SummaryPayload:
    rows = _filter_rows(tool_type, fab_names, start_date, end_date, lot_cd)

    total = len(rows)
    align_fails = sum(1 for r in rows if _is_align_fail(r))
    align_na = sum(1 for r in rows if r["align_fail"] == "NA")
    meas_fails = sum(1 for r in rows if _is_meas_fail(r))

    align_rate = round(align_fails / total, 4) if total else 0.0
    meas_rate = round(meas_fails / total, 4) if total else 0.0

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "anchor_date": ANCHOR_TIME.date().isoformat(),
        "total_executions": total,
        "align_fail_count": align_fails,
        "align_fail_rate": align_rate,
        "align_na_count": align_na,
        "meas_fail_count": meas_fails,
        "meas_fail_rate": meas_rate,
        "meas_fail_threshold": MEAS_FAIL_THRESHOLD,
        "distinct_equipment": len({r["eqp_id"] for r in rows}),
        "distinct_recipes": len({(r["class_name"], r["recipe_name"]) for r in rows}),
        "distinct_lots": len({r["lot_cd"] for r in rows})
    }


def get_daily_trend(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> list[DailyTrendPoint]:
    rows = _filter_rows(tool_type, fab_names, start_date, end_date, lot_cd)

    bucket: dict[str, dict[str, int]] = {}
    for row in rows:
        date_key = row["timestamp"][:10]
        entry = bucket.setdefault(date_key, {
            "exec_count": 0,
            "align_fail_count": 0,
            "meas_fail_count": 0
        })
        entry["exec_count"] += 1
        if _is_align_fail(row):
            entry["align_fail_count"] += 1
        if _is_meas_fail(row):
            entry["meas_fail_count"] += 1

    # Backfill the requested window so the chart renders a continuous axis
    # rather than skipping silent days.
    start_dt = parse_iso_date(start_date)
    end_dt = parse_iso_date(end_date)
    if start_dt is not None and end_dt is not None and start_dt <= end_dt:
        cursor = start_dt
        while cursor <= end_dt:
            key = cursor.date().isoformat()
            bucket.setdefault(key, {
                "exec_count": 0,
                "align_fail_count": 0,
                "meas_fail_count": 0
            })
            cursor += timedelta(days=1)

    return [
        {
            "date": date_key,
            "exec_count": entry["exec_count"],
            "align_fail_count": entry["align_fail_count"],
            "meas_fail_count": entry["meas_fail_count"]
        }
        for date_key, entry in sorted(bucket.items())
    ]


def _top_sample(counts: "Counter[str]") -> list[str]:
    """빈도 상위 5개를 고른 뒤 표시용으로 사전순 정렬.

    office 의 ``terms(field=eqp_id, size=5)`` + ``sorted`` 와 같은 규칙입니다 —
    전체를 사전순 정렬해 앞 5개를 자르면 후보 집합부터 달라집니다. 동률은
    이름으로 갈라 결정론을 유지합니다.
    """
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return sorted(name for name, _ in top)


def get_align_ranking(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None
) -> list[AlignRankingRow]:
    rows = _filter_rows(tool_type, fab_names, start_date, end_date, lot_cd)

    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["class_name"], row["recipe_name"])
        bucket = grouped.setdefault(key, {
            "class_name": row["class_name"],
            "recipe_name": row["recipe_name"],
            "full_name": row["full_name"],
            "exec_count": 0,
            "align_fail_count": 0,
            "eqp_ids": Counter(),
            "fabs": set()
        })
        bucket["exec_count"] += 1
        bucket["fabs"].add(str(row["fab_name"]).upper())
        if _is_align_fail(row):
            bucket["align_fail_count"] += 1
            bucket["eqp_ids"][row["eqp_id"]] += 1

    ranked = sorted(
        # Filter out recipes with zero fails so this stays a triage table.
        (b for b in grouped.values() if b["align_fail_count"] > 0),
        key=lambda b: (b["align_fail_count"], b["align_fail_count"] / b["exec_count"]),
        reverse=True
    )
    if limit > 0:
        ranked = ranked[:limit]

    out: list[AlignRankingRow] = []
    for index, bucket in enumerate(ranked):
        exec_count = bucket["exec_count"]
        fail_count = bucket["align_fail_count"]
        rate = round(fail_count / exec_count, 4) if exec_count else 0.0

        out.append({
            "rank": index + 1,
            "class_name": bucket["class_name"],
            "recipe_name": bucket["recipe_name"],
            "full_name": bucket["full_name"],
            "exec_count": exec_count,
            "align_fail_count": fail_count,
            "align_fail_rate": rate,
            "sample_eqp_ids": _top_sample(bucket["eqp_ids"]),
            "fab_names": sorted(bucket["fabs"])
        })

    return out


def get_meas_ranking(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None
) -> list[MeasRankingRow]:
    rows = _filter_rows(tool_type, fab_names, start_date, end_date, lot_cd)

    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["class_name"], row["recipe_name"])
        bucket = grouped.setdefault(key, {
            "class_name": row["class_name"],
            "recipe_name": row["recipe_name"],
            "full_name": row["full_name"],
            "exec_count": 0,
            "meas_fail_count": 0,
            "fail_ratio_sum": 0.0,
            "eqp_ids": Counter(),
            "fabs": set()
        })
        bucket["exec_count"] += 1
        bucket["fail_ratio_sum"] += row["fail_ratio"]
        bucket["fabs"].add(str(row["fab_name"]).upper())
        if _is_meas_fail(row):
            bucket["meas_fail_count"] += 1
            bucket["eqp_ids"][row["eqp_id"]] += 1

    ranked = sorted(
        (b for b in grouped.values() if b["meas_fail_count"] > 0),
        key=lambda b: (b["meas_fail_count"], b["meas_fail_count"] / b["exec_count"]),
        reverse=True
    )
    if limit > 0:
        ranked = ranked[:limit]

    out: list[MeasRankingRow] = []
    for index, bucket in enumerate(ranked):
        exec_count = bucket["exec_count"]
        fail_count = bucket["meas_fail_count"]
        rate = round(fail_count / exec_count, 4) if exec_count else 0.0
        avg_ratio = round(bucket["fail_ratio_sum"] / exec_count, 4) if exec_count else 0.0

        out.append({
            "rank": index + 1,
            "class_name": bucket["class_name"],
            "recipe_name": bucket["recipe_name"],
            "full_name": bucket["full_name"],
            "exec_count": exec_count,
            "meas_fail_count": fail_count,
            "meas_fail_rate": rate,
            "avg_fail_ratio": avg_ratio,
            "sample_eqp_ids": _top_sample(bucket["eqp_ids"]),
            "fab_names": sorted(bucket["fabs"])
        })

    return out


def get_devices(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None
) -> list[DeviceRow]:
    """Distinct lot_cds with measurements in scope.

    Sorted by combined fail count (align + meas) descending so the chip
    strip surfaces the most-problematic devices first — matches the
    intent of the 디바이스별 view ("which device should I look at?").
    """
    rows = _filter_rows(tool_type, fab_names, start_date, end_date)
    metadata = lot_metadata()

    bucket: dict[str, dict] = {}
    for row in rows:
        entry = bucket.setdefault(row["lot_cd"], {
            "exec_count": 0,
            "align_fail_count": 0,
            "meas_fail_count": 0
        })
        entry["exec_count"] += 1
        if _is_align_fail(row):
            entry["align_fail_count"] += 1
        if _is_meas_fail(row):
            entry["meas_fail_count"] += 1

    return [
        {
            "lot_cd": lot_cd,
            "exec_count": entry["exec_count"],
            "align_fail_count": entry["align_fail_count"],
            "meas_fail_count": entry["meas_fail_count"],
            "prod_catg_cd": metadata.get(lot_cd, {}).get("prod_catg_cd"),
            "tech_nm": metadata.get(lot_cd, {}).get("tech_nm")
        }
        for lot_cd, entry in sorted(
            bucket.items(),
            key=lambda kv: kv[1]["align_fail_count"] + kv[1]["meas_fail_count"],
            reverse=True
        )
    ]


def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None
) -> EquipmentsPayload:
    """범위 안의 행을 (장비, 레시피) 격자로 접어 공용 조립기에 넘깁니다.

    office 어댑터는 같은 격자를 OpenSearch composite 집계로 만들어 같은
    조립기를 부릅니다 — 두 provider 의 숫자가 정의상 일치합니다.
    """
    cells: dict[tuple[str, str], EquipmentGridRow] = {}
    for row in _filter_rows(tool_type, fab_names, start_date, end_date):
        key = (row["eqp_id"], row["full_name"])
        cell = cells.get(key)
        if cell is None:
            cell = EquipmentGridRow(
                eqp_id=row["eqp_id"],
                fab_name=row["fab_name"],
                eqp_model_cd=row["eqp_model_cd"],
                full_name=row["full_name"],
                exec_count=0,
                align_fails=0,
                meas_fails=0,
            )
        # `cell[5] += 1` / `cell[6] += 1` until 2026-08-09 — align and meas were
        # two adjacent indexes, and swapping them is invisible to a shape check.
        cells[key] = cell._replace(
            exec_count=cell.exec_count + 1,
            align_fails=cell.align_fails + (1 if _is_align_fail(row) else 0),
            meas_fails=cell.meas_fails + (1 if _is_meas_fail(row) else 0),
        )

    return build_equipments_payload(
        tool_type, fab_names, start_date, end_date, list(cells.values())
    )


def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...]
) -> EquipmentComparePayload:
    """선택된 장비들의 (장비, 날짜) · (장비, 레시피) 두 격자를 만듭니다.

    합집합·0채움·정렬은 전부 공용 조립기가 합니다 — office 어댑터는 같은 두
    격자를 composite 집계로 만들어 같은 조립기를 부릅니다.
    """
    selected = list(dict.fromkeys(eqp_ids))
    if not selected:
        return build_equipment_compare_payload(
            tool_type, fab_names, start_date, end_date, [], [], []
        )

    wanted = set(selected)
    rows = [
        row for row in _filter_rows(tool_type, fab_names, start_date, end_date)
        if row["eqp_id"] in wanted
    ]

    trend_cells: dict[tuple[str, str], list] = {}
    recipe_cells: dict[tuple[str, str], list] = {}
    for row in rows:
        is_align = _is_align_fail(row)
        is_meas = _is_meas_fail(row)
        day = row["timestamp"][:10]

        day_key = (row["eqp_id"], day)
        day_cell = trend_cells.get(day_key)
        if day_cell is None:
            trend_cells[day_key] = [row["eqp_id"], day, 0, 0, 0]
            day_cell = trend_cells[day_key]
        day_cell[2] += 1
        day_cell[3] += int(is_align)
        day_cell[4] += int(is_meas)

        recipe_key = (row["eqp_id"], row["full_name"])
        recipe_cell = recipe_cells.get(recipe_key)
        if recipe_cell is None:
            recipe_cells[recipe_key] = [row["eqp_id"], row["full_name"], 0, 0, 0]
            recipe_cell = recipe_cells[recipe_key]
        recipe_cell[2] += 1
        recipe_cell[3] += int(is_align)
        recipe_cell[4] += int(is_meas)

    return build_equipment_compare_payload(
        tool_type, fab_names, start_date, end_date, selected,
        [tuple(cell) for cell in trend_cells.values()],
        [tuple(cell) for cell in recipe_cells.values()]
    )


if __name__ == "__main__":
    # Standalone preview:
    #   python -m back_dev_home.ebeam.fail_issue.data
    import pprint

    end = ANCHOR_TIME.date().isoformat()
    start = (ANCHOR_TIME - timedelta(days=30)).date().isoformat()

    print("=" * 72)
    print(f"FAIL-ISSUE SUMMARY (cd-sem, {start} -> {end})")
    print("=" * 72)
    pprint.pprint(get_summary("cd-sem", None, start, end))

    print("\n" + "=" * 72)
    print("TOP 5 ALIGN-FAIL RECIPES")
    print("=" * 72)
    for entry in get_align_ranking("cd-sem", None, start, end, limit=5):
        print(
            f"#{entry['rank']:>2}  {entry['full_name']:<28}  "
            f"fails={entry['align_fail_count']:>3}/{entry['exec_count']:>4}  "
            f"rate={entry['align_fail_rate'] * 100:>5.2f}%"
        )

    print("\nTOP 5 MEAS-FAIL RECIPES")
    print("=" * 72)
    for entry in get_meas_ranking("cd-sem", None, start, end, limit=5):
        print(
            f"#{entry['rank']:>2}  {entry['full_name']:<28}  "
            f"fails={entry['meas_fail_count']:>3}/{entry['exec_count']:>4}  "
            f"rate={entry['meas_fail_rate'] * 100:>5.2f}%"
        )
