"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본 테이블:  docs/datatables/meas_hist.txt
계약:        docs/api-contracts/fail-issue.yaml

Fail-issue mock data — measurement-history rows enriched with two failure
aspects derived from the meas_hist schema:

* `align_fail` (Pass/Fail/NA): wafer-alignment outcome at measurement start.
  Surfaced as a per-recipe ranking for the fail-issue table.
* `fail_ratio` > MEAS_FAIL_THRESHOLD: image-level failure during the run.
  A recipe-side problem — surfaced as a per-recipe ranking.

Phase 1 implementation reuses recipe_tat's 6000-row meas_hist universe as
the source of (eqp, recipe, lot, timestamp) tuples and enriches each row
with deterministic fail metadata. Sharing the row universe keeps the two
dashboards consistent (a recipe with heavy TAT can also show high fails)
and avoids generating a parallel 6000-row dataset.

사무실 주의사항: 사무실 구현은 recipe_tat 결과에 join 하지 말고 OpenSearch
의 meas_hist 인덱스에서 align_fail/fail_ratio/msr_check 컬럼을 그대로
읽어와 동일한 집계 (count, rate, daily series) 를 수행해야 합니다.
MEAS_FAIL_THRESHOLD 의 값은 YAML 계약에 명시되어 있으므로 임의로
변경하지 마세요 — Phase 1/2 간 수치가 어긋날 수 있습니다.
"""

import random
from datetime import timedelta
from functools import lru_cache

from back_dev_home.ebeam.hitachi._analytics import (
    MeasurementScope,
    fab_base,
    filter_measurements,
    lot_metadata,
    parse_iso_date,
)
from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    AlignOutcome,
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    FailRow,
    MeasRankingRow,
    MsrCheck,
    SummaryPayload,
)
from back_dev_home.ebeam.hitachi.recipe_tat.providers.mock import (
    ANCHOR_TIME,
    MeasHistRow,
    ToolType,
    get_meas_hist,
)


__all__ = [
    "ANCHOR_TIME",
    "MEAS_FAIL_THRESHOLD",
    "ToolType",
    "FailRow",
    "get_summary",
    "get_daily_trend",
    "get_align_ranking",
    "get_meas_ranking",
    "get_devices"
]


# Threshold that promotes a meas_hist row to a "meas fail". Pinned to the
# datatable spec (docs/datatables/meas_hist.txt rule #9 — "정상 row는 보통
# 0.0 ~ 0.15"). The YAML contract repeats this constant; office must keep
# it in sync.
MEAS_FAIL_THRESHOLD = 0.15


# Per-fab fail-rate personalities. Without this, switching fab in the
# sidebar would only change row counts — both KPIs and rankings would look
# identical across fabs. Keyed by `_fab_base` so M15A/B/C share the M15
# profile, mirroring recipe_tat's FAB_CLASS_MIX convention.
DEFAULT_ALIGN_FAIL_RATE = 0.10
FAB_ALIGN_FAIL_RATE: dict[str, float] = {
    "R3":  0.11,
    "R4":  0.06,
    "M11": 0.08,
    "M12": 0.05,
    "M14": 0.15,
    "M15": 0.09,
    "M16": 0.12
}

DEFAULT_MEAS_FAIL_RATE = 0.13
FAB_MEAS_FAIL_RATE: dict[str, float] = {
    "R3":  0.14,
    "R4":  0.08,
    "M11": 0.07,
    "M12": 0.12,
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
    # elevated fail_ratio band; otherwise stay below 0.15. We use the
    # MEAS_FAIL_THRESHOLD anchor instead of hard-coding 0.15 so the band
    # logic and the threshold can't drift out of sync.
    is_problem = align_fail == "Fail" or msr_check == "No"
    # Also independently roll a fab-specific meas-fail event so the meas
    # ranking has signal even on align-Pass rows.
    if not is_problem and rng.random() < meas_fail_rate:
        is_problem = True

    if is_problem:
        fail_ratio = round(rng.uniform(MEAS_FAIL_THRESHOLD, 0.8), 4)
    else:
        fail_ratio = round(rng.uniform(0.0, MEAS_FAIL_THRESHOLD), 4)

    total_images = rng.randint(40, 400)
    fail_images = int(total_images * fail_ratio)
    fail_ratio = round(fail_images / total_images, 4) if total_images else 0.0

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
    return tuple(_enrich(row) for row in get_meas_hist())


@lru_cache(maxsize=256)
def _filter_rows(
    tool_type: ToolType | None,
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> tuple[FailRow, ...]:
    # Each page load hits summary + daily-trend + align-ranking +
    # meas-ranking with the same filter args. Memoizing here means the
    # 6000-row scan runs once per unique window instead of four times.
    return filter_measurements(
        _all_fail_rows(),
        MeasurementScope(tool_type, fab_id, start_date, end_date, lot_cd),
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
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> SummaryPayload:
    rows = _filter_rows(tool_type, fab_id, start_date, end_date, lot_cd)

    total = len(rows)
    align_fails = sum(1 for r in rows if _is_align_fail(r))
    align_na = sum(1 for r in rows if r["align_fail"] == "NA")
    meas_fails = sum(1 for r in rows if _is_meas_fail(r))

    align_rate = round(align_fails / total, 4) if total else 0.0
    meas_rate = round(meas_fails / total, 4) if total else 0.0

    return {
        "tool_type": tool_type,
        "fab_id": fab_id,
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
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> list[DailyTrendPoint]:
    rows = _filter_rows(tool_type, fab_id, start_date, end_date, lot_cd)

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


def get_align_ranking(
    tool_type: ToolType,
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 1000,
    lot_cd: str | None = None
) -> list[AlignRankingRow]:
    rows = _filter_rows(tool_type, fab_id, start_date, end_date, lot_cd)

    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["class_name"], row["recipe_name"])
        bucket = grouped.setdefault(key, {
            "class_name": row["class_name"],
            "recipe_name": row["recipe_name"],
            "full_name": row["full_name"],
            "exec_count": 0,
            "align_fail_count": 0,
            "eqp_ids": set()
        })
        bucket["exec_count"] += 1
        if _is_align_fail(row):
            bucket["align_fail_count"] += 1
            bucket["eqp_ids"].add(row["eqp_id"])

    ranked = sorted(
        # Filter out recipes with zero fails so this stays a triage table.
        (b for b in grouped.values() if b["align_fail_count"] > 0),
        key=lambda b: (b["align_fail_count"], b["align_fail_count"] / b["exec_count"]),
        reverse=True
    )[:limit]

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
            "sample_eqp_ids": sorted(bucket["eqp_ids"])[:5]
        })

    return out


def get_meas_ranking(
    tool_type: ToolType,
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 1000,
    lot_cd: str | None = None
) -> list[MeasRankingRow]:
    rows = _filter_rows(tool_type, fab_id, start_date, end_date, lot_cd)

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
            "eqp_ids": set()
        })
        bucket["exec_count"] += 1
        bucket["fail_ratio_sum"] += row["fail_ratio"]
        if _is_meas_fail(row):
            bucket["meas_fail_count"] += 1
            bucket["eqp_ids"].add(row["eqp_id"])

    ranked = sorted(
        (b for b in grouped.values() if b["meas_fail_count"] > 0),
        key=lambda b: (b["meas_fail_count"], b["meas_fail_count"] / b["exec_count"]),
        reverse=True
    )[:limit]

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
            "sample_eqp_ids": sorted(bucket["eqp_ids"])[:5]
        })

    return out


def get_devices(
    tool_type: ToolType,
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None
) -> list[DeviceRow]:
    """Distinct lot_cds with measurements in scope.

    Sorted by combined fail count (align + meas) descending so the chip
    strip surfaces the most-problematic devices first — matches the
    intent of the 디바이스별 view ("which device should I look at?").
    """
    rows = _filter_rows(tool_type, fab_id, start_date, end_date)
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


if __name__ == "__main__":
    # Standalone preview:
    #   python -m back_dev_home.ebeam.hitachi.fail_issue.data
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
