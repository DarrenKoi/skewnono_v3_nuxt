"""Recipe statistics mock data for device_statistics.

The lot_cd column on r3_device_grp / device_desc (see data.py) is the
join key. When the frontend selects one or more lot_cds, this module
returns matching recipe-info and summary rows for each weekly date in
a trend window — keyed by ISO date so the frontend can plot the
trend directly without re-shaping.
"""

import random
from datetime import timedelta
from functools import lru_cache
from typing import TypedDict

from back_dev_home.device_statistics.data import BASE_TIME, get_device_desc, get_r3_device_grp


class RecipeInfoRow(TypedDict):
    lot_cd: str
    fac_id: str
    oper_id: str
    oper_desc: str
    oper_seq: int
    samp_seq: int
    eqp_id: str
    recipe_id: str
    skip_yn: str
    chg_tm: str
    ctn_desc: str
    para_all: int
    para_16: int
    para_13: int
    para_9: int
    para_5: int
    para_16_percent: float
    para_13_percent: float
    para_9_percent: float
    para_5_percent: float


class SummaryRow(TypedDict):
    lot_cd: str
    fac_id: str
    para_all: int
    para_16: int
    para_13: int
    para_9: int
    para_5: int
    para_16_percent: float
    para_13_percent: float
    para_9_percent: float
    para_5_percent: float
    ctn_desc: str
    total_recipe: int
    avail_recipe: int
    avail_recipe_percent: float


RCP_BUCKETS = ("all", "only_normal", "mother_normal", "only_sample")
DEFAULT_TREND_POINTS = 8
DEFAULT_INTERVAL_DAYS = 7

OPER_DESCS = (
    "Initial Material Prep", "Primary Etching", "Deposition Layer 1",
    "Photolithography", "Ion Implantation", "Chemical Cleaning",
    "Annealing Process", "Final Inspection", "Wafer Testing"
)

# Per-bucket value ranges. "all" is the widest bucket; "only_sample" is
# the narrowest — matches the legacy dashboard's visual hierarchy where
# all_summary always dominates and only_sample is a small slice.
SUMMARY_RANGES = {
    "all": (5000, 10000),
    "only_normal": (3000, 7000),
    "mother_normal": (2000, 5000),
    "only_sample": (1000, 3000),
}


def _percent(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, 2)


def _seed_for(lot_cd: str, point_index: int) -> int:
    digest = 0
    for ch in lot_cd:
        digest = (digest * 131 + ord(ch)) & 0xFFFFFFFF
    return (digest * 1009 + point_index * 7919) & 0xFFFFFFFF


def _trend_dates(points: int, interval_days: int) -> tuple[str, ...]:
    base_monday = (BASE_TIME - timedelta(days=BASE_TIME.weekday())).date()
    dates = [
        (base_monday - timedelta(days=interval_days * offset)).isoformat()
        for offset in range(points - 1, -1, -1)
    ]
    return tuple(dates)


@lru_cache(maxsize=1)
def _lot_index() -> dict[str, str]:
    """lot_cd -> fac_id, sourced from both R3 and per-fab generators."""
    index: dict[str, str] = {}

    for row in get_r3_device_grp():
        index[row["lot_cd"]] = row["fac_id"]

    for row in get_device_desc():
        index[row["lot_cd"]] = row["fac_id"]

    return index


def _build_recipe_row(
    rng: random.Random,
    lot_cd: str,
    fac_id: str,
    bucket_index: int
) -> RecipeInfoRow:
    para_all = rng.randint(500, 1000)
    para_16 = rng.randint(100, para_all // 2)
    para_13 = rng.randint(50, para_all // 3)
    para_9 = rng.randint(20, para_all // 4)
    para_5 = rng.randint(10, para_all // 5)

    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        "oper_id": f"OPER-{lot_cd}-{bucket_index}",
        "oper_desc": rng.choice(OPER_DESCS),
        "oper_seq": rng.randint(1, 10),
        "samp_seq": rng.randint(1, 5),
        "eqp_id": f"EQP-{lot_cd}-{bucket_index:02d}",
        "recipe_id": f"RCP-{lot_cd}-{500 + bucket_index}",
        "skip_yn": rng.choice(("Yes", "No")),
        "chg_tm": f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}",
        "ctn_desc": f"Container for {lot_cd}",
        "para_all": para_all,
        "para_16": para_16,
        "para_13": para_13,
        "para_9": para_9,
        "para_5": para_5,
        "para_16_percent": _percent(para_16, para_all),
        "para_13_percent": _percent(para_13, para_all),
        "para_9_percent": _percent(para_9, para_all),
        "para_5_percent": _percent(para_5, para_all),
    }


def _build_summary_row(
    rng: random.Random,
    lot_cd: str,
    fac_id: str,
    bucket: str
) -> SummaryRow:
    base_min, base_max = SUMMARY_RANGES[bucket]
    para_all = rng.randint(base_min, base_max)
    para_16 = rng.randint(base_min // 5, para_all // 2)
    para_13 = rng.randint(base_min // 10, para_all // 3)
    para_9 = rng.randint(max(base_min // 20, 1), para_all // 4)
    para_5 = rng.randint(max(base_min // 50, 1), para_all // 5)

    total_recipe = rng.randint(20, 50)
    avail_recipe = rng.randint(10, total_recipe)

    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        "para_all": para_all,
        "para_16": para_16,
        "para_13": para_13,
        "para_9": para_9,
        "para_5": para_5,
        "para_16_percent": _percent(para_16, para_all),
        "para_13_percent": _percent(para_13, para_all),
        "para_9_percent": _percent(para_9, para_all),
        "para_5_percent": _percent(para_5, para_all),
        "ctn_desc": f"Summary Container for {lot_cd} ({bucket})",
        "total_recipe": total_recipe,
        "avail_recipe": avail_recipe,
        "avail_recipe_percent": _percent(avail_recipe, total_recipe),
    }


def _resolve_lots(lot_cds: list[str] | None) -> list[str]:
    index = _lot_index()

    if not lot_cds:
        return list(index.keys())

    requested = {lot.strip() for lot in lot_cds if lot.strip()}

    if not requested:
        return list(index.keys())

    return [lot for lot in index.keys() if lot in requested]


def get_weekly_trend_data(
    lot_cds: list[str] | None = None,
    points: int = DEFAULT_TREND_POINTS,
    interval_days: int = DEFAULT_INTERVAL_DAYS
) -> dict[str, dict[str, list]]:
    """Return trend data keyed by ISO date.

    Each date entry maps to a flat dict with eight keys — the four
    recipe buckets paired with their summaries:

      {
        "2026-02-09": {
          "all_rcp_info":           [RecipeInfoRow, ...],
          "all_summary":            [SummaryRow, ...],
          "only_normal_rcp_info":   [...],
          "only_normal_summary":    [...],
          "mother_normal_rcp_info": [...],
          "mother_normal_summary":  [...],
          "only_sample_rcp_info":   [...],
          "only_sample_summary":    [...],
        },
        ...
      }

    Dates are spaced `interval_days` apart (default 7 = weekly), with
    `points` total samples ending at the most recent Monday before
    BASE_TIME. Per-(lot, date) seeding keeps the output deterministic
    across calls.
    """
    index = _lot_index()
    selected = _resolve_lots(lot_cds)
    dates = _trend_dates(points, interval_days)
    trend: dict[str, dict[str, list]] = {}

    for point_index, date_key in enumerate(dates):
        bucketed: dict[str, list] = {}
        for bucket in RCP_BUCKETS:
            bucketed[f"{bucket}_rcp_info"] = []
            bucketed[f"{bucket}_summary"] = []

        for lot_cd in selected:
            fac_id = index[lot_cd]
            rng = random.Random(_seed_for(lot_cd, point_index))

            for bucket_index, bucket in enumerate(RCP_BUCKETS):
                bucketed[f"{bucket}_rcp_info"].append(
                    _build_recipe_row(rng, lot_cd, fac_id, bucket_index)
                )
                bucketed[f"{bucket}_summary"].append(
                    _build_summary_row(rng, lot_cd, fac_id, bucket)
                )

        trend[date_key] = bucketed

    return trend


def get_lot_index() -> list[dict]:
    """Flat lot_cd -> fac_id listing, useful as a frontend lot picker."""
    return [{"lot_cd": lot_cd, "fac_id": fac_id} for lot_cd, fac_id in _lot_index().items()]


if __name__ == "__main__":
    # Standalone mock-data preview. Run from the project root with:
    #   python -m back_dev_home.device_statistics.statistics
    import pprint

    print("=" * 72)
    print("LOT INDEX")
    print("=" * 72)
    index = _lot_index()
    fac_breakdown: dict[str, int] = {}
    for fac_id in index.values():
        fac_breakdown[fac_id] = fac_breakdown.get(fac_id, 0) + 1
    print(f"Total lots: {len(index)}")
    print(f"By fac_id:  {fac_breakdown}")

    print("\n" + "=" * 72)
    print("SHAPE SPOT-CHECK: single lot 'R007', latest date")
    print("=" * 72)
    trend = get_weekly_trend_data(["R007"])
    date_keys = list(trend.keys())
    print(f"Date keys (oldest -> newest): {date_keys}")

    latest = date_keys[-1]
    print(f"\nKeys at trend[{latest!r}]:")
    pprint.pprint(list(trend[latest].keys()))

    print(f"\n--- trend[{latest!r}]['all_rcp_info'][0] ---")
    pprint.pprint(trend[latest]["all_rcp_info"][0])

    print(f"\n--- trend[{latest!r}]['all_summary'][0] ---")
    pprint.pprint(trend[latest]["all_summary"][0])

    print(f"\n--- trend[{latest!r}]['only_sample_summary'][0] ---")
    pprint.pprint(trend[latest]["only_sample_summary"][0])

    print("\n" + "=" * 72)
    print("TREND VIEW: para_all per bucket across dates (single lot 'R007')")
    print("=" * 72)
    print(f"{'date':<12} | {'all':>6} | {'only_normal':>11} | "
          f"{'mother_normal':>13} | {'only_sample':>11}")
    print("-" * 72)
    for date_key, payload in trend.items():
        all_v = payload["all_summary"][0]["para_all"]
        norm_v = payload["only_normal_summary"][0]["para_all"]
        moth_v = payload["mother_normal_summary"][0]["para_all"]
        samp_v = payload["only_sample_summary"][0]["para_all"]
        print(f"{date_key:<12} | {all_v:>6} | {norm_v:>11} | "
              f"{moth_v:>13} | {samp_v:>11}")

    print("\n" + "=" * 72)
    print("MULTI-LOT FILTER: mix of R3 and M-fab lots")
    print("=" * 72)
    multi = get_weekly_trend_data(["R000", "R001", "100", "1001", "60B2"])
    latest_multi = list(multi.keys())[-1]
    print(f"Latest date: {latest_multi}")
    print(f"\nall_rcp_info rows (one per selected lot):")
    for row in multi[latest_multi]["all_rcp_info"]:
        print(f"  lot_cd={row['lot_cd']:<6} fac_id={row['fac_id']:<4} "
              f"recipe={row['recipe_id']:<14} para_all={row['para_all']}")

    print("\n" + "=" * 72)
    print("SCALE CHECK: full dataset (all lots, all dates)")
    print("=" * 72)
    full = get_weekly_trend_data()
    total_rows = 0
    for payload in full.values():
        for rows in payload.values():
            total_rows += len(rows)
    print(f"Lots:      {len(index)}")
    print(f"Dates:     {len(full)}")
    print(f"Buckets per date: 8 (4 rcp_info + 4 summary)")
    print(f"Total rows across the whole payload: {total_rows:,}")
