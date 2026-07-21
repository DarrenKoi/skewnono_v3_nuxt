"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본 테이블:  docs/datatables/meas_hist.txt
계약:        docs/api-contracts/recipe-tat.yaml
픽스처:      back_dev_home/ebeam/hitachi/recipe_tat/__fixtures__/

Recipe TAT mock data — measurement-history rows aggregated per recipe.

One row in `_generate_meas_hist()` represents a single measurement execution
on one lot, by one tool, of one recipe. The TAT dashboard groups these rows
by (tool_type, recipe_name, class_name) over a date range to surface which
recipes consume the most measurement time.

Schema follows `docs/datatables/meas_hist.txt`. We intentionally drop the
wider columns (msr / align / image counts / idp paths) — TAT only needs
timing, so adding them would bloat payloads without changing the dashboard.

사무실 주의사항: ANCHOR_TIME 은 모듈 로드 시점의 wall-clock 입니다. 사무실
구현은 wall-clock 대신 실 인덱스의 max(timestamp) 를 anchor 로 사용해야
합니다. (routes.py 의 _resolve_dates 가 ANCHOR_TIME.date() 를 기본 윈도
끝점으로 사용함을 인지)

NOTE: `_lot_index` is currently sourced from `cdsem.device_statistics`.
HV-SEM responses derived from this data layer reuse the CD-SEM mock lot
index until an HV-SEM-specific lot pool is introduced — acceptable for
mock-only Phase 1 since no HV-SEM frontend currently calls these endpoints.
"""

import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from back_dev_home.ebeam.cdsem.device_statistics.providers.mock import _lot_index
from back_dev_home.ebeam.hitachi._analytics import (
    MeasurementScope,
    fab_base,
    filter_measurements,
    lot_metadata,
    parse_iso_date,
)
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    DailyTrendPoint,
    DeviceRow,
    MeasHistRow,
    RankingRow,
    SummaryPayload,
    ToolType,
)


__all__ = [
    "ANCHOR_TIME",
    "ToolType",
    "MeasHistRow",
    "get_meas_hist",
    "get_ranking",
    "get_summary",
    "get_daily_trend",
    "get_devices",
]


# Anchor the mock-data window on wall-clock now (captured once per process)
# instead of device_statistics' BASE_TIME. The TAT dashboard defaults to
# "today minus 30 days" in any deployment phase per CLAUDE.md's cross-phase
# principle — anchoring on a fixed mock date would force the frontend to
# special-case Phase 1 vs 2/3.
#
# KST, not UTC: every deployment phase serves Korean fabs, and a UTC anchor
# makes anchor_date (the 데이터 기준 badge and the default window's end) read
# yesterday's date between 00:00 and 09:00 KST. Korea has no DST, so a fixed
# +09:00 offset is exact and avoids zoneinfo/tzdata availability concerns on
# Windows office hosts.
KST = timezone(timedelta(hours=9), "KST")
ANCHOR_TIME = datetime.now(KST).replace(microsecond=0)


# Tool model -> tool type mapping. CG family is CD-SEM; TP / VERITYSEM /
# PROVISION are HV-SEM. Mirrors the meas_hist.txt rule "CG -> cd-sem,
# TP / PROVISION / VERITYSEM -> hv-sem".
TOOL_MODELS: dict[ToolType, tuple[tuple[str, str], ...]] = {
    # (eqp_model_cd, vendor_nm)
    "cd-sem": (
        ("CG6300", "HITACHI"),
        ("CG6380", "HITACHI"),
        ("CG5000", "HITACHI")
    ),
    "hv-sem": (
        ("TP4000", "HITACHI"),
        ("VERITYSEM_5", "AMAT"),
        ("PROVISION_3", "AMAT")
    )
}

# fab_name choices per fac_id. Must match SemList's vocabulary so the
# FAB sidebar's selections actually filter rows here — every M-fab carries
# A/B/C sub-fabs in SemList, R3 lots can land on R3 or R4.
FAB_NAMES_BY_FAC: dict[str, tuple[str, ...]] = {
    "R3": ("R3", "R4"),
    "M11": ("M11A", "M11B", "M11C"),
    "M12": ("M12A", "M12B", "M12C"),
    "M14": ("M14A", "M14B", "M14C"),
    "M15": ("M15A", "M15B", "M15C"),
    "M16": ("M16A", "M16B", "M16C")
}


# Recipe class -> baseline meastime range (seconds). QC is fast, ADI/AEI
# are heaviest. This shapes the TAT ranking — without per-class spread the
# dashboard would be uniform noise.
CLASS_MEASTIME_BANDS: dict[str, tuple[int, int]] = {
    "ADI":  (320, 900),
    "AEI":  (280, 820),
    "OVL":  (200, 540),
    "GATE": (240, 700),
    "CNT":  (180, 480),
    "QC":   (60, 200),
    "DEF":  (140, 360),
    "EDGE": (220, 560)
}

# Each fab has a recognizable workload personality so switching fab_name in
# the UI changes both ranking composition and KPI scale, not only row counts.
DEFAULT_CLASS_MIX = tuple(CLASS_MEASTIME_BANDS.keys())
# Keyed by `_fab_base` (e.g. M15A/M15B/M15C all share "M15"); `R3`/`R4`
# stay full names since they have no sub-fab variants.
FAB_CLASS_MIX: dict[str, tuple[str, ...]] = {
    "R3": ("ADI", "ADI", "AEI", "GATE", "OVL", "QC"),
    "R4": ("QC", "QC", "OVL", "CNT", "EDGE", "DEF"),
    "M11": ("DEF", "DEF", "EDGE", "QC", "CNT", "OVL"),
    "M12": ("GATE", "GATE", "CNT", "OVL", "QC", "ADI"),
    "M14": ("ADI", "GATE", "GATE", "EDGE", "AEI", "OVL"),
    "M15": ("AEI", "AEI", "OVL", "QC", "CNT", "DEF"),
    "M16": ("ADI", "ADI", "DEF", "CNT", "GATE", "QC")
}

FAB_MEASTIME_MULTIPLIER: dict[str, float] = {
    "R3": 1.12,
    "R4": 0.82,
    "M11": 0.74,
    "M12": 0.95,
    "M14": 1.25,
    "M15": 1.03,
    "M16": 1.18
}

# Per-class recipe-name templates. {n} is filled with a 3-digit running
# number per recipe instance.
CLASS_RECIPE_TEMPLATES: dict[str, tuple[str, ...]] = {
    "ADI":  ("ADI_CD_BIAS_{n}", "ADI_LINEWIDTH_{n}", "ADI_PROFILE_{n}"),
    "AEI":  ("AEI_CD_BIAS_{n}", "AEI_OVERLAY_{n}"),
    "OVL":  ("OVL_M2M_{n}", "OVL_M2P_{n}"),
    "GATE": ("GATE_CD_{n}", "GATE_PITCH_{n}"),
    "CNT":  ("CNT_DIAM_{n}", "CNT_MATCH_{n}"),
    "QC":   ("QC_DAILY_MATCH_{n}", "QC_PM_{n}"),
    "DEF":  ("DEF_REVIEW_{n}",),
    "EDGE": ("EDGE_PROFILE_{n}",)
}

RECIPE_DEFINITIONS_PER_TOOL = 60      # distinct recipes per tool_type
TOTAL_MEAS_ROWS = 6000                 # split evenly across both tool types
HISTORY_WINDOW_DAYS = 120              # extends past 30-day default range


@lru_cache(maxsize=1)
def _lot_pool() -> tuple[tuple[str, str], ...]:
    return tuple(_lot_index().items())


@lru_cache(maxsize=1)
def _recipe_definitions() -> tuple[dict, ...]:
    """Stable per-recipe metadata generated once.

    Each entry pins a tool_type, class, recipe_name, eqp_model and a baseline
    meastime — every measurement row for that recipe samples meastime around
    the baseline so a single recipe has a recognizable "size" on the chart.
    """
    rng = random.Random(20260508)
    classes = tuple(CLASS_MEASTIME_BANDS.keys())
    recipes: list[dict] = []

    for tool_type in ("cd-sem", "hv-sem"):
        models = TOOL_MODELS[tool_type]
        for index in range(RECIPE_DEFINITIONS_PER_TOOL):
            class_name = rng.choice(classes)
            template = rng.choice(CLASS_RECIPE_TEMPLATES[class_name])
            recipe_name = template.format(n=f"{index + 1:03d}")
            full_name = f"{class_name}/{recipe_name}"

            min_t, max_t = CLASS_MEASTIME_BANDS[class_name]
            baseline = rng.randint(min_t, max_t)

            eqp_model_cd, vendor_nm = rng.choice(models)

            recipes.append({
                "tool_type": tool_type,
                "class_name": class_name,
                "recipe_name": recipe_name,
                "full_name": full_name,
                "baseline_meastime": baseline,
                "eqp_model_cd": eqp_model_cd,
                "vendor_nm": vendor_nm
            })

    return tuple(recipes)


def _format_iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _build_lot_id(rng: random.Random, lot_cd: str) -> str:
    suffix = f"{rng.randint(1, 999999):06d}"
    return f"{lot_cd}{suffix}"


def _build_eqp_id(rng: random.Random, eqp_model_cd: str) -> str:
    family = eqp_model_cd[:4].upper()
    return f"{family}-{rng.randint(1, 24):02d}"


def _recipe_indexes(
    recipes: tuple[dict, ...]
) -> tuple[dict[tuple[ToolType, str], tuple[dict, ...]], dict[ToolType, tuple[dict, ...]]]:
    by_tool_class: dict[tuple[ToolType, str], list[dict]] = {}
    by_tool: dict[ToolType, list[dict]] = {"cd-sem": [], "hv-sem": []}

    for recipe in recipes:
        tool_type = recipe["tool_type"]
        class_name = recipe["class_name"]
        by_tool[tool_type].append(recipe)
        by_tool_class.setdefault((tool_type, class_name), []).append(recipe)

    return (
        {key: tuple(value) for key, value in by_tool_class.items()},
        {key: tuple(value) for key, value in by_tool.items()}
    )


def _pick_recipe_for_fab(
    rng: random.Random,
    by_tool_class: dict[tuple[ToolType, str], tuple[dict, ...]],
    by_tool: dict[ToolType, tuple[dict, ...]],
    tool_type: ToolType,
    fab_name: str
) -> dict:
    class_name = rng.choice(FAB_CLASS_MIX.get(fab_base(fab_name), DEFAULT_CLASS_MIX))
    candidates = by_tool_class.get((tool_type, class_name)) or by_tool[tool_type]
    return candidates[rng.randrange(len(candidates))]


@lru_cache(maxsize=1)
def _generate_meas_hist() -> tuple[MeasHistRow, ...]:
    """Generate the full meas_hist mock universe.

    Determinism is the contract: the same (tool_type, date_range) query
    must always return byte-identical aggregates so the dashboard does
    not shimmer between renders.
    """
    rng = random.Random(20260508)
    recipes = _recipe_definitions()
    by_tool_class, by_tool = _recipe_indexes(recipes)
    lots = _lot_pool()

    if not lots or not recipes:
        return ()

    rows: list[MeasHistRow] = []
    history_start = ANCHOR_TIME - timedelta(days=HISTORY_WINDOW_DAYS)
    window_seconds = HISTORY_WINDOW_DAYS * 24 * 3600

    for index in range(TOTAL_MEAS_ROWS):
        tool_type: ToolType = "cd-sem" if index % 2 == 0 else "hv-sem"
        lot_cd, fac_id = lots[rng.randrange(len(lots))]
        fab_name = rng.choice(FAB_NAMES_BY_FAC.get(fac_id, (fac_id,)))
        recipe = _pick_recipe_for_fab(rng, by_tool_class, by_tool, tool_type, fab_name)

        offset = rng.randint(0, window_seconds - 1)
        end_dt = history_start + timedelta(seconds=offset)

        baseline = recipe["baseline_meastime"]
        # ±25 % jitter around baseline, clamped to a sensible floor.
        jitter = rng.uniform(-0.25, 0.25)
        fab_multiplier = FAB_MEASTIME_MULTIPLIER.get(fab_base(fab_name), 1.0)
        meastime = max(30, int(baseline * fab_multiplier * (1 + jitter)))

        start_dt = end_dt - timedelta(seconds=meastime)
        eqp_id = _build_eqp_id(rng, recipe["eqp_model_cd"])
        lot_id = _build_lot_id(rng, lot_cd)

        rows.append({
            "id": f"MEAS-{index + 1:06d}",
            "fac_id": fac_id,
            "fab_name": fab_name,
            "vendor_nm": recipe["vendor_nm"],
            "eqp_id": eqp_id,
            "eqp_model_cd": recipe["eqp_model_cd"],
            "tool_type": recipe["tool_type"],
            "lot_cd": lot_cd,
            "lot_id": lot_id,
            "class_name": recipe["class_name"],
            "recipe_name": recipe["recipe_name"],
            "full_name": recipe["full_name"],
            "timestamp": _format_iso(end_dt),
            "start_time": _format_iso(start_dt),
            "end_time": _format_iso(end_dt),
            "meastime": meastime
        })

    return tuple(rows)


def get_meas_hist() -> list[MeasHistRow]:
    """Public accessor — callers may filter with the helpers below."""
    return list(_generate_meas_hist())


@lru_cache(maxsize=256)
def _filter_rows(
    tool_type: ToolType | None,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> tuple[MeasHistRow, ...]:
    # Each page load hits ranking + summary + daily-trend with the same
    # filter args. Memoizing here cuts the 6000-row scan from 3× to 1× per
    # unique window. Sized for ~tool_type × fab × preset_window × lot_cd —
    # keeps the unfiltered (lot_cd=None) entry warm even when the user
    # cycles through many devices.
    return filter_measurements(
        _generate_meas_hist(),
        MeasurementScope(tool_type, fab_name, start_date, end_date, lot_cd),
    )


def get_ranking(
    tool_type: ToolType,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None
) -> list[RankingRow]:
    rows = _filter_rows(tool_type, fab_name, start_date, end_date, lot_cd)

    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row["class_name"], row["recipe_name"])
        bucket = grouped.setdefault(key, {
            "class_name": row["class_name"],
            "recipe_name": row["recipe_name"],
            "full_name": row["full_name"],
            "meas_counts": 0,
            "total_meastime": 0,
            "lot_cds": set(),
            "eqp_ids": set()
        })
        bucket["meas_counts"] += 1
        bucket["total_meastime"] += row["meastime"]
        bucket["lot_cds"].add(row["lot_cd"])
        bucket["eqp_ids"].add(row["eqp_id"])

    ranked = sorted(
        grouped.values(),
        key=lambda b: b["total_meastime"],
        reverse=True
    )
    if limit > 0:
        ranked = ranked[:limit]

    out: list[RankingRow] = []
    for index, bucket in enumerate(ranked):
        meas_counts = bucket["meas_counts"]
        total = bucket["total_meastime"]
        avg = round(total / meas_counts, 2) if meas_counts else 0.0
        # Cap the example lists so the JSON response stays compact even when
        # a recipe ran on many lots.
        sample_lots = sorted(bucket["lot_cds"])[:5]
        sample_eqps = sorted(bucket["eqp_ids"])[:5]

        out.append({
            "rank": index + 1,
            "class_name": bucket["class_name"],
            "recipe_name": bucket["recipe_name"],
            "full_name": bucket["full_name"],
            "meas_counts": meas_counts,
            "total_meastime": total,
            "avg_meastime": avg,
            "sample_lot_cds": sample_lots,
            "sample_eqp_ids": sample_eqps
        })

    return out


def get_summary(
    tool_type: ToolType,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> SummaryPayload:
    rows = _filter_rows(tool_type, fab_name, start_date, end_date, lot_cd)

    total_executions = len(rows)
    total_tat_seconds = sum(row["meastime"] for row in rows)
    avg_meastime = round(total_tat_seconds / total_executions, 2) if total_executions else 0.0
    total_recipes = len({(row["class_name"], row["recipe_name"]) for row in rows})

    return {
        "tool_type": tool_type,
        "fab_name": fab_name,
        "start_date": start_date,
        "end_date": end_date,
        "anchor_date": ANCHOR_TIME.date().isoformat(),
        "total_tat_seconds": total_tat_seconds,
        "total_recipes": total_recipes,
        "total_executions": total_executions,
        "avg_meastime": avg_meastime
    }


def get_daily_trend(
    tool_type: ToolType,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None
) -> list[DailyTrendPoint]:
    rows = _filter_rows(tool_type, fab_name, start_date, end_date, lot_cd)

    bucket: dict[str, dict] = {}
    for row in rows:
        date_key = row["timestamp"][:10]   # YYYY-MM-DD slice from ISO string
        entry = bucket.setdefault(date_key, {"total_meastime": 0, "exec_count": 0})
        entry["total_meastime"] += row["meastime"]
        entry["exec_count"] += 1

    # Backfill empty days inside the requested range so the trend chart
    # renders a continuous x-axis instead of skipping silent days.
    start_dt = parse_iso_date(start_date)
    end_dt = parse_iso_date(end_date)
    if start_dt is not None and end_dt is not None and start_dt <= end_dt:
        cursor = start_dt
        while cursor <= end_dt:
            key = cursor.date().isoformat()
            bucket.setdefault(key, {"total_meastime": 0, "exec_count": 0})
            cursor += timedelta(days=1)

    return [
        {
            "date": date_key,
            "total_meastime": entry["total_meastime"],
            "exec_count": entry["exec_count"]
        }
        for date_key, entry in sorted(bucket.items())
    ]


def get_devices(
    tool_type: ToolType,
    fab_name: str | None,
    start_date: str | None,
    end_date: str | None
) -> list[DeviceRow]:
    """Distinct lot_cds with measurements in scope, sorted by total TAT desc.

    Drives the `디바이스별` view's quick-filter chip strip — only surfacing
    devices that actually have data in the window keeps the picker honest
    (no zero-result chips).
    """
    rows = _filter_rows(tool_type, fab_name, start_date, end_date)
    metadata = lot_metadata()

    bucket: dict[str, dict] = {}
    for row in rows:
        entry = bucket.setdefault(row["lot_cd"], {"exec_count": 0, "total_meastime": 0})
        entry["exec_count"] += 1
        entry["total_meastime"] += row["meastime"]

    return [
        {
            "lot_cd": lot_cd,
            "exec_count": entry["exec_count"],
            "total_meastime": entry["total_meastime"],
            "prod_catg_cd": metadata.get(lot_cd, {}).get("prod_catg_cd"),
            "tech_nm": metadata.get(lot_cd, {}).get("tech_nm")
        }
        for lot_cd, entry in sorted(
            bucket.items(),
            key=lambda kv: kv[1]["total_meastime"],
            reverse=True
        )
    ]


if __name__ == "__main__":
    # Standalone preview:
    #   python -m back_dev_home.ebeam.hitachi.recipe_tat.data
    import pprint

    print("=" * 72)
    print("MEAS_HIST SCALE")
    print("=" * 72)
    rows = _generate_meas_hist()
    print(f"Total rows: {len(rows)}")
    by_tool: dict[str, int] = {}
    for row in rows:
        by_tool[row["tool_type"]] = by_tool.get(row["tool_type"], 0) + 1
    print(f"By tool_type: {by_tool}")

    print("\n" + "=" * 72)
    print("SAMPLE ROW")
    print("=" * 72)
    pprint.pprint(rows[0])

    print("\n" + "=" * 72)
    print("CD-SEM RANKING (last 30 days from ANCHOR_TIME), top 5")
    print("=" * 72)
    end = ANCHOR_TIME.date().isoformat()
    start = (ANCHOR_TIME - timedelta(days=30)).date().isoformat()
    ranking = get_ranking("cd-sem", None, start, end, limit=5)
    for entry in ranking:
        print(
            f"#{entry['rank']:>2}  {entry['full_name']:<28}  "
            f"counts={entry['meas_counts']:>4}  "
            f"total={entry['total_meastime']:>7}s  "
            f"avg={entry['avg_meastime']:>6.1f}s"
        )

    print("\nSUMMARY")
    pprint.pprint(get_summary("cd-sem", None, start, end))

    trend = get_daily_trend("cd-sem", None, start, end)
    print(f"\nDAILY TREND points: {len(trend)} (range {trend[0]['date']} -> {trend[-1]['date']})")
