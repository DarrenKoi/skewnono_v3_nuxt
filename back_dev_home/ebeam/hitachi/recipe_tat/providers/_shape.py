"""mock·office 공용 payload 조립.

provider 는 자기 소스에서 격자(grid)만 만들고 여기로 넘깁니다. 지수·중앙값·
분위수를 두 provider 가 각자 계산하면 언젠가 어긋나고, 그때 어느 쪽이 맞는지
판정할 방법이 없습니다.
"""

from __future__ import annotations

import statistics
from datetime import timedelta
from typing import NamedTuple, Sequence

from back_dev_home.ebeam.hitachi._analytics import parse_iso_date, percentile_summary
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    EquipmentComparePayload,
    EquipmentRecipeRow,
    EquipmentRow,
    EquipmentsPayload,
    TAT_INDEX_MIN_SAMPLE,
    ToolType,
)


class EquipmentGridRow(NamedTuple):
    """One (장비, 레시피) cell on its way into ``build_equipments_payload``.

    Named rather than a bare 6-tuple because the row is threaded mock → shape →
    office and four of its six fields are strings. Swapping fab_name and
    eqp_model_cd — the office adapter's own comment warns this is the kind of
    mistake home tests cannot catch — type-checks fine as a tuple and produces
    a plausible-looking table. As a NamedTuple the fields are named at every
    hand-off and the swap has to be written out loud to happen.
    """

    eqp_id: str
    fab_name: str
    eqp_model_cd: str
    full_name: str
    meas_counts: int
    total_meastime: int


def window_seconds(start_date: str | None, end_date: str | None) -> int:
    """조회 기간의 총 초. 양 끝 날짜를 모두 포함합니다(필터와 같은 규칙)."""
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if start is None or end is None or end < start:
        return 0
    return ((end - start).days + 1) * 86400


def days_in_range(start_date: str | None, end_date: str | None) -> list[str]:
    """요청 기간의 모든 날짜. 트렌드 x축이 조용한 날을 건너뛰지 않게 합니다."""
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if start is None or end is None or end < start:
        return []
    days: list[str] = []
    cursor = start
    while cursor <= end:
        days.append(cursor.date().isoformat())
        cursor += timedelta(days=1)
    return days


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

    **지수는 fab 하나 안에서만 비교 가능합니다.** `base(r)`은 조회 범위
    전체의 레시피별 평균이라, 여러 fab을 함께 조회하면 base가 fab들을 섞은
    값이 됩니다. 그러면 fab 단위의 속도 차이가 그 fab 장비 *전부*의 지수로
    나타납니다 — mock의 cd-sem 전 fab 조회에서 fab별 지수 중앙값은
    `mock.FAB_MEASTIME_MULTIPLIER`의 배수 순서를 그대로 따라 줄서고, 가장
    느린 fab과 가장 빠른 fab 사이의 격차가 배지 대역(TAT_FLOOR 0.92 ~
    TAT_CEIL 1.10)의 폭보다 넓습니다. 여기에 실측 중앙값을 적어두지 않는
    이유는 mock 의 앵커가 프로세스 시작 시각이라 조회 창이 매일 움직이고
    그때마다 중앙값도 함께 움직이기 때문입니다 — 고정해 적으면 반드시
    낡습니다. 장비 상태가 아니라 fab을 잰 것이므로 배지 임계값은 단일 fab
    조회 기준으로 잡아야 합니다. 사무실에서도 같은 상관이 나타나는지는
    OFFICE-VERIFY 이며(MIGRATION.md), 나타난다면 `base(r)`을
    `(fab_name, recipe)`별로 계산해야 합니다. 지금 바꾸지 않는 이유는 근거가
    mock 의 지어낸 fab 배수뿐이기 때문입니다.

    **`usage_ratio`와 `occupancy`에는 fab 정규화가 아예 없습니다.** 지수는
    적어도 레시피 구성으로 표준화되지만, 이 둘은 원 `total_meastime`을 각각
    플릿 중앙값과 조회 기간으로 나눈 값일 뿐이라 정규화 항이 하나도 없습니다.
    레시피가 짧은 fab의 장비는 같은 개수의 측정을 돌아도 두 값이 함께 낮게
    나옵니다 — 여러 fab을 섞어 조회하면 `저사용` 배지가 방치된 장비가 아니라
    **레시피가 짧은 fab**을 가리킵니다(mock에서 실제로 그렇습니다). 그래서
    프론트엔드는 조회 범위에 fab이 2개 이상이면 배지를 아예 달지 않습니다
    (`front-dev-home/app/utils/equipmentSignals.ts`의
    `isPeerGroupComparable`). 사무실 실 분포에서도 이 편향이 나타나는지는
    지수와 마찬가지로 OFFICE-VERIFY 입니다(MIGRATION.md).
    """
    per_tool: dict[str, dict] = {}
    per_recipe: dict[str, dict] = {}
    for row in grid:
        tool = per_tool.setdefault(row.eqp_id, {
            "eqp_id": row.eqp_id,
            "fab_name": row.fab_name,
            "eqp_model_cd": row.eqp_model_cd,
            "exec_count": 0,
            "total_meastime": 0,
            "recipes": {}
        })
        tool["exec_count"] += row.meas_counts
        tool["total_meastime"] += row.total_meastime
        cell = tool["recipes"].setdefault(row.full_name, {"count": 0, "tat": 0})
        cell["count"] += row.meas_counts
        cell["tat"] += row.total_meastime

        recipe = per_recipe.setdefault(row.full_name, {"count": 0, "tat": 0})
        recipe["count"] += row.meas_counts
        recipe["tat"] += row.total_meastime

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

        # 2차 키로 full_name 을 명시합니다. tat 만으로 비교하면 동률에서
        # dict 삽입 순서가 승자를 정하는데, 그 순서는 mock(행 스캔 순서)과
        # office(composite 버킷 순서)가 서로 다릅니다 — 같은 장비의
        # `top_recipe`(표시값이자 `편중` 배지의 입력)가 provider 에 따라
        # 달라집니다. max 이므로 동률이면 full_name 이 사전순으로 뒤인 쪽이
        # 이깁니다. 어느 쪽을 고르든 상관없고, 정해져 있다는 것만 중요합니다.
        top_name, top_cell = max(
            cells.items(), key=lambda item: (item[1]["tat"], item[0]),
            default=(None, None)
        )
        # `if name in base` — count 가 0 인 레시피는 base 에 없습니다. mock 은
        # 행마다 count 1 을 더하므로 도달할 수 없지만, office 의 composite 는
        # doc_count 0 인 버킷을 낼 수 있습니다. 0.0 으로 채우지 않고 건너뛰는
        # 이유: 기여할 실행이 없는 항은 분모에서 빠져야 하고, 0.0 을 더하면
        # 분모만 작아져 지수가 조용히 부풀어 오릅니다.
        expected = sum(
            cell["count"] * base[name]
            for name, cell in cells.items() if name in base
        )

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


# (eqp_id, date, total_meastime, exec_count)
TrendGridRow = tuple[str, str, int, int]
# (eqp_id, full_name, meas_counts, total_meastime)
RecipeGridRow = tuple[str, str, int, int]


def build_equipment_compare_payload(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: Sequence[str],
    trend_rows: Sequence[TrendGridRow],
    recipe_rows: Sequence[RecipeGridRow],
) -> EquipmentComparePayload:
    """선택된 장비들의 일별 트렌드와 레시피 구성을 한 응답에 담습니다.

    레시피 행은 선택 장비들의 **합집합**이고, 돌지 않은 장비 칸은 0으로
    채웁니다. 클라이언트가 장비별 응답 여러 개를 조인하면 이 합집합과
    0채움을 매번 다시 만들어야 하고, 한 번 어긋나면 열이 밀려 다른 장비의
    숫자를 보여주게 됩니다.
    """
    selected = list(dict.fromkeys(eqp_ids))     # 순서 보존 dedupe
    if not selected:
        return {
            "tool_type": tool_type,
            "fab_names": list(fab_names or []),
            "start_date": start_date,
            "end_date": end_date,
            "eqp_ids": [],
            "trends": [],
            "recipes": []
        }

    days = days_in_range(start_date, end_date)
    trend: dict[str, dict[str, dict]] = {
        eqp_id: {day: {"total_meastime": 0, "exec_count": 0} for day in days}
        for eqp_id in selected
    }
    for eqp_id, day, tat, counts in trend_rows:
        bucket = trend.get(eqp_id, {}).get(day)
        if bucket is not None:
            bucket["total_meastime"] += tat
            bucket["exec_count"] += counts

    grid: dict[str, dict] = {}
    for eqp_id, full_name, counts, tat in recipe_rows:
        if eqp_id not in trend:
            continue
        # office 문서에는 class_name/recipe_name 이 따로 있지만 격자 키는
        # full_name 하나입니다. full_name = f"{class_name}/{recipe_name}" 이
        # 계약이므로 첫 '/' 로 되살립니다.
        class_name, _, recipe_name = full_name.partition("/")
        recipe = grid.setdefault(full_name, {
            "class_name": class_name,
            "recipe_name": recipe_name,
            "full_name": full_name,
            "total_meastime": 0,
            "cells": {picked: {"count": 0, "tat": 0} for picked in selected}
        })
        recipe["total_meastime"] += tat
        cell = recipe["cells"][eqp_id]
        cell["count"] += counts
        cell["tat"] += tat

    recipes: list[EquipmentRecipeRow] = [
        {
            "class_name": entry["class_name"],
            "recipe_name": entry["recipe_name"],
            "full_name": entry["full_name"],
            "total_meastime": entry["total_meastime"],
            "cells": [
                {
                    "eqp_id": eqp_id,
                    "meas_counts": entry["cells"][eqp_id]["count"],
                    "total_meastime": entry["cells"][eqp_id]["tat"],
                    "avg_meastime": round(
                        entry["cells"][eqp_id]["tat"] / entry["cells"][eqp_id]["count"], 2
                    ) if entry["cells"][eqp_id]["count"] else 0.0
                }
                for eqp_id in selected
            ]
        }
        for entry in sorted(
            grid.values(), key=lambda e: e["total_meastime"], reverse=True
        )
    ]

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "eqp_ids": selected,
        "trends": [
            {
                "eqp_id": eqp_id,
                "points": [
                    {
                        "date": day,
                        "total_meastime": trend[eqp_id][day]["total_meastime"],
                        "exec_count": trend[eqp_id][day]["exec_count"]
                    }
                    for day in days
                ]
            }
            for eqp_id in selected
        ],
        "recipes": recipes
    }
