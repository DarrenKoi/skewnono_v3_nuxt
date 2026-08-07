"""mock·office 공용 payload 조립.

provider 는 자기 소스에서 격자(grid)만 만들고 여기로 넘깁니다. 지수·중앙값·
분위수를 두 provider 가 각자 계산하면 언젠가 어긋나고, 그때 어느 쪽이 맞는지
판정할 방법이 없습니다.
"""

from __future__ import annotations

import statistics
from typing import Sequence

from back_dev_home.ebeam.hitachi._analytics import parse_iso_date, percentile_summary
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    EquipmentRow,
    EquipmentsPayload,
    TAT_INDEX_MIN_SAMPLE,
    ToolType,
)


# (eqp_id, fab_name, eqp_model_cd, full_name, meas_counts, total_meastime)
EquipmentGridRow = tuple[str, str, str, str, int, int]


def window_seconds(start_date: str | None, end_date: str | None) -> int:
    """조회 기간의 총 초. 양 끝 날짜를 모두 포함합니다(필터와 같은 규칙)."""
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if start is None or end is None or end < start:
        return 0
    return ((end - start).days + 1) * 86400


def build_equipments_payload(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    grid: Sequence[EquipmentGridRow],
) -> EquipmentsPayload:
    """장비별 집계 + 배지 판정을 위한 플릿 분포 요약.

    `tat_index`는 간접표준화입니다: 실제 총 TAT을, 이 장비의 레시피 구성이면
    걸렸어야 할 TAT(레시피별 플릿 평균 × 이 장비의 실행 수)으로 나눕니다.
    단순 평균 TAT으로 장비를 줄세우면 QC만 도는 장비가 저절로 빠른 장비가
    되고 ADI를 많이 도는 장비가 느린 장비가 됩니다 — 장비 상태가 아니라
    일감의 종류를 잰 것입니다.

    어떤 레시피를 장비 한 대만 돌았다면 그 레시피의 플릿 평균이 곧 그 장비의
    평균이라 해당 항이 정확히 1.0을 기여합니다. 비교 정보가 없는 일감은
    지수를 1.0 쪽으로 희석시킬 뿐 없는 경보를 만들지 않습니다 — 의도된
    성질입니다.
    """
    per_tool: dict[str, dict] = {}
    per_recipe: dict[str, dict] = {}
    for eqp_id, fab_name, eqp_model_cd, full_name, counts, tat in grid:
        tool = per_tool.setdefault(eqp_id, {
            "eqp_id": eqp_id,
            "fab_name": fab_name,
            "eqp_model_cd": eqp_model_cd,
            "exec_count": 0,
            "total_meastime": 0,
            "recipes": {}
        })
        tool["exec_count"] += counts
        tool["total_meastime"] += tat
        cell = tool["recipes"].setdefault(full_name, {"count": 0, "tat": 0})
        cell["count"] += counts
        cell["tat"] += tat

        recipe = per_recipe.setdefault(full_name, {"count": 0, "tat": 0})
        recipe["count"] += counts
        recipe["tat"] += tat

    # base(r) = 레시피 r의 플릿 평균 meastime
    base = {
        name: agg["tat"] / agg["count"]
        for name, agg in per_recipe.items() if agg["count"]
    }

    window = window_seconds(start_date, end_date)
    totals = sorted(tool["total_meastime"] for tool in per_tool.values())
    median_total = float(statistics.median(totals)) if totals else 0.0

    equipments: list[EquipmentRow] = []
    for tool in per_tool.values():
        exec_count = tool["exec_count"]
        total = tool["total_meastime"]
        cells = tool["recipes"]

        top_name, top_cell = max(
            cells.items(), key=lambda item: item[1]["tat"], default=(None, None)
        )
        expected = sum(cell["count"] * base[name] for name, cell in cells.items())

        equipments.append({
            "eqp_id": tool["eqp_id"],
            "fab_name": tool["fab_name"],
            "eqp_model_cd": tool["eqp_model_cd"],
            "exec_count": exec_count,
            "total_meastime": total,
            "avg_meastime": round(total / exec_count, 2) if exec_count else 0.0,
            "recipe_count": len(cells),
            "top_recipe": top_name,
            "top_recipe_share": round(top_cell["tat"] / total, 4) if total and top_cell else 0.0,
            "tat_index": (
                round(total / expected, 4)
                if exec_count >= TAT_INDEX_MIN_SAMPLE and expected else None
            ),
            "occupancy": round(total / window, 6) if window else 0.0,
            "usage_ratio": round(total / median_total, 4) if median_total else 0.0
        })

    equipments.sort(key=lambda row: (row["total_meastime"], row["exec_count"]), reverse=True)

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "fleet": {
            "tool_count": len(equipments),
            "total_executions": sum(row["exec_count"] for row in equipments),
            "total_meastime": sum(row["total_meastime"] for row in equipments),
            "window_seconds": window,
            "median_total_meastime": median_total,
            "median_recipe_count": float(
                statistics.median([row["recipe_count"] for row in equipments])
            ) if equipments else 0.0,
            "min_sample": TAT_INDEX_MIN_SAMPLE,
            "percentiles": {
                "usage_ratio": percentile_summary(r["usage_ratio"] for r in equipments),
                "occupancy": percentile_summary(r["occupancy"] for r in equipments),
                "recipe_count": percentile_summary(r["recipe_count"] for r in equipments),
                # None 장비는 제외 — 표본 미달은 "느리지 않다"가 아니라
                # "모른다"이고, 0으로 채우면 p10이 통째로 무너집니다.
                "tat_index": percentile_summary(
                    r["tat_index"] for r in equipments if r["tat_index"] is not None
                )
            }
        },
        "equipments": equipments
    }
