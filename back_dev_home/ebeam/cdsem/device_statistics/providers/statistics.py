"""Recipe statistics mock data for device_statistics.

The lot_cd column on r3_device_grp / device_desc (see providers/mock.py) is
the join key. When the frontend selects one or more lot_cds, this module
returns matching recipe-info and summary rows for each weekly date in
a trend window — keyed by ISO date so the frontend can plot the
trend directly without re-shaping.

Internal module: callers outside this feature must import the public surface
from `device_statistics.data` (the provider switch); `recipe_tat`'s mock
provider is the one sanctioned exception and imports `_lot_index` straight
from `device_statistics.providers.mock` (mock-to-mock, never through the
switch — see that module's own docstring). Imports of `.mock` are deferred
to function bodies — eager module-top imports would form a circular load
with `mock.py` (which itself re-exports the symbols below), so the import
order is fragile when this module is entered first (e.g. `python -m ...
providers.statistics` running the __main__ block, or any future test that
imports this module directly).
"""

import random
from datetime import timedelta
from functools import lru_cache

from back_dev_home.ebeam.cdsem.device_statistics.contracts import (
    RecipeInfoRow,
    SummaryRow,
)


RCP_BUCKETS = ("all", "only_normal", "mother_normal", "only_sample")
DEFAULT_TREND_POINTS = 8
DEFAULT_INTERVAL_DAYS = 7

OPER_DESCS = (
    "Initial Material Prep", "Primary Etching", "Deposition Layer 1",
    "Photolithography", "Ion Implantation", "Chemical Cleaning",
    "Annealing Process", "Final Inspection", "Wafer Testing"
)

OPER_PREFIXES = (
    "ETCH", "DEPO", "LITH", "IMPL", "CLEAN", "ANNL", "INSP", "MEAS",
    "CMP", "STRIP", "OXID", "DIFF"
)

EQP_FAMILIES = ("CDSEM", "CDS2", "MET", "VS", "INSP")

# Per-bucket recipe-count range. "all" is widest; "only_sample" narrowest —
# the summary chart aggregates from these counts, so this also governs the
# relative visual hierarchy of the bucket bars on the comparison page.
RECIPE_COUNT_RANGES = {
    "all": (130, 200),
    "only_normal": (80, 150),
    "mother_normal": (50, 110),
    "only_sample": (25, 70),
}

# Per-recipe parameter ranges. Sums across ~150 recipes land in the legacy
# summary range of ~5k–10k for `all`, which keeps existing chart axes
# meaningful.
PARA_RANGES = {
    "para_16": (10, 50),
    "para_13": (6, 32),
    "para_9": (3, 16),
    "para_5": (1, 9),
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
    from .mock import BASE_TIME  # deferred import — avoid circular load
    base_monday = (BASE_TIME - timedelta(days=BASE_TIME.weekday())).date()
    dates = [
        (base_monday - timedelta(days=interval_days * offset)).isoformat()
        for offset in range(points - 1, -1, -1)
    ]
    return tuple(dates)


@lru_cache(maxsize=1)
def _lot_index() -> dict[str, str]:
    """lot_cd -> fac_id, sourced from both R3 and per-fab generators."""
    from .mock import get_device_desc, get_r3_device_grp  # deferred import
    index: dict[str, str] = {}

    for row in get_r3_device_grp():
        index[row["lot_cd"]] = row["fac_id"]

    for row in get_device_desc():
        index[row["lot_cd"]] = row["fac_id"]

    return index


@lru_cache(maxsize=1)
def _lot_ctn_desc() -> dict[str, str]:
    """lot_cd -> device-level ctn_desc, joined from both lot sources.

    The frontend uses this on chart tooltips and the slideover summary
    card so analysts can identify devices without memorizing lot codes.
    Later sources win on conflict, matching `_lot_index`.
    """
    from .mock import get_device_desc, get_r3_device_grp  # deferred import
    descs: dict[str, str] = {}

    for row in get_r3_device_grp():
        descs[row["lot_cd"]] = row["ctn_desc"]

    for row in get_device_desc():
        descs[row["lot_cd"]] = row["ctn_desc"]

    return descs


def _build_recipe_row(
    rng: random.Random,
    lot_cd: str,
    fac_id: str,
    bucket: str,
    idx: int
) -> RecipeInfoRow:
    para_16 = rng.randint(*PARA_RANGES["para_16"])
    para_13 = rng.randint(*PARA_RANGES["para_13"])
    para_9 = rng.randint(*PARA_RANGES["para_9"])
    para_5 = rng.randint(*PARA_RANGES["para_5"])
    para_all = para_16 + para_13 + para_9 + para_5

    oper_prefix = rng.choice(OPER_PREFIXES)
    oper_id = f"{oper_prefix}-{rng.randint(100, 999)}"
    eqp_id = f"{rng.choice(EQP_FAMILIES)}-{rng.randint(1, 24):02d}"
    recipe_id = f"RCP-{lot_cd}-{bucket[:3].upper()}-{idx:03d}"

    return {
        "lot_cd": lot_cd,
        "fac_id": fac_id,
        "oper_id": oper_id,
        "oper_desc": rng.choice(OPER_DESCS),
        "oper_seq": idx + 1,
        "samp_seq": rng.randint(1, 5),
        "eqp_id": eqp_id,
        "recipe_id": recipe_id,
        "skip_yn": "Yes" if rng.random() < 0.15 else "No",
        "chg_tm": f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}",
        "ctn_desc": f"{oper_prefix} {rng.choice(OPER_DESCS)} step",
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


def _build_recipes_for_bucket(
    rng: random.Random,
    lot_cd: str,
    fac_id: str,
    bucket: str
) -> list[RecipeInfoRow]:
    count_min, count_max = RECIPE_COUNT_RANGES[bucket]
    count = rng.randint(count_min, count_max)
    return [_build_recipe_row(rng, lot_cd, fac_id, bucket, i) for i in range(count)]


def _summarize(
    lot_cd: str,
    fac_id: str,
    ctn_desc: str,
    recipes: list[RecipeInfoRow]
) -> SummaryRow:
    para_16 = sum(r["para_16"] for r in recipes)
    para_13 = sum(r["para_13"] for r in recipes)
    para_9 = sum(r["para_9"] for r in recipes)
    para_5 = sum(r["para_5"] for r in recipes)
    para_all = para_16 + para_13 + para_9 + para_5

    total_recipe = len(recipes)
    avail_recipe = sum(1 for r in recipes if r["skip_yn"] == "No")

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
        "ctn_desc": ctn_desc,
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
    interval_days: int = DEFAULT_INTERVAL_DAYS,
    include_recipes: bool = True
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
    descs = _lot_ctn_desc()
    selected = _resolve_lots(lot_cds)
    dates = _trend_dates(points, interval_days)
    trend: dict[str, dict[str, list]] = {}

    for point_index, date_key in enumerate(dates):
        bucketed: dict[str, list] = {}
        for bucket in RCP_BUCKETS:
            if include_recipes:
                bucketed[f"{bucket}_rcp_info"] = []
            bucketed[f"{bucket}_summary"] = []

        for lot_cd in selected:
            fac_id = index[lot_cd]
            ctn_desc = descs.get(lot_cd, "")
            rng = random.Random(_seed_for(lot_cd, point_index))

            for bucket in RCP_BUCKETS:
                recipes = _build_recipes_for_bucket(rng, lot_cd, fac_id, bucket)
                if include_recipes:
                    bucketed[f"{bucket}_rcp_info"].extend(recipes)
                bucketed[f"{bucket}_summary"].append(
                    _summarize(lot_cd, fac_id, ctn_desc, recipes)
                )

        trend[date_key] = bucketed

    return trend


def get_lot_index() -> list[dict]:
    """Flat lot_cd -> fac_id listing, useful as a frontend lot picker."""
    return [{"lot_cd": lot_cd, "fac_id": fac_id} for lot_cd, fac_id in _lot_index().items()]


if __name__ == "__main__":
    # Standalone mock-data preview. Run from the project root with:
    #   python -m back_dev_home.ebeam.cdsem.device_statistics.providers.statistics
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
