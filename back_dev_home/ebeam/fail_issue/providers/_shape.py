"""mock·office 공용 payload 조립.

provider 는 자기 소스에서 격자(grid)만 만들고 여기로 넘깁니다. 지수·구간·
분위수를 두 provider 가 각자 계산하면 언젠가 어긋나고, 그때 어느 쪽이 맞는지
판정할 방법이 없습니다 — 집에서는 office 를 실행할 수 없으므로 그 판정자가
아예 존재하지 않습니다. recipe_tat/providers/_shape.py 와 같은 규약입니다.
"""

from __future__ import annotations

import statistics
from math import sqrt
from typing import NamedTuple, Sequence

from back_dev_home.ebeam._analytics import percentile_summary
from back_dev_home.ebeam.fail_issue.contracts import (
    CONFIDENCE_Z,
    EquipmentComparePayload,
    EquipmentRecipeRow,
    EquipmentRow,
    EquipmentsPayload,
    FAIL_INDEX_MIN_EXPECTED,
    ToolType,
)
# 날짜 채움 규칙은 recipe_tat 이 이미 갖고 있습니다. 복제하면 두 화면의 x축이
# 서로 다른 날 개수를 그리게 되고, 그 어긋남은 조용합니다.
from back_dev_home.ebeam.recipe_tat.providers._shape import days_in_range


def byar_interval(
    observed: int,
    expected: float,
    z: float = CONFIDENCE_Z,
) -> tuple[float, float]:
    """관측/기대 건수비의 신뢰구간 (Byar 근사).

    이 지수는 역학의 간접표준화 비(SMR)와 같은 양이고, Byar 근사는 그쪽의
    표준 처방입니다. 정확한 Garwood 구간(카이제곱 분위수)을 쓰지 않는 이유는
    scipy 의존을 들이지 않기 위해서이며, 근사 오차는 observed >= 1 에서
    소수 셋째 자리 수준이라 배지 판정에 영향을 주지 않습니다.

    observed == 0 은 sqrt(0) 로 0 나눗셈이 나는 자리라 분기가 필요합니다.
    하한은 그 경우 정확히 0 입니다 — 실패가 0건이면 참값이 0일 수도 있습니다.
    """
    if expected <= 0:
        return (0.0, 0.0)

    if observed <= 0:
        low = 0.0
    else:
        low = observed * (1 - 1 / (9 * observed) - z / (3 * sqrt(observed))) ** 3 / expected
        low = max(0.0, low)

    upper_n = observed + 1
    high = upper_n * (1 - 1 / (9 * upper_n) + z / (3 * sqrt(upper_n))) ** 3 / expected

    return (round(low, 4), round(high, 4))


def standardised(
    observed: int,
    expected: float,
) -> tuple[float | None, float | None, float | None]:
    """(index, low, high). 기대가 표시 하한 미만이면 셋 다 None.

    None 은 "실패하지 않았다"가 아니라 **"모른다"** 입니다. 호출자는 어느
    쪽으로도 판정하면 안 되며, 특히 0 으로 채우면 안 됩니다.
    """
    if expected < FAIL_INDEX_MIN_EXPECTED:
        return (None, None, None)
    low, high = byar_interval(observed, expected)
    return (round(observed / expected, 4), low, high)


class EquipmentGridRow(NamedTuple):
    """One (장비, 레시피) cell on its way into ``build_equipments_payload``.

    Named for the same reason as recipe_tat's twin, only more so: this one has
    SEVEN fields, three of them ints that all count different things. A bare
    tuple lets align_fails and meas_fails trade places without a murmur, and
    the resulting table is wrong in a way no shape check can see.
    """

    eqp_id: str
    fab_name: str
    eqp_model_cd: str
    full_name: str
    exec_count: int
    align_fails: int
    meas_fails: int


def build_equipments_payload(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    grid: Sequence[EquipmentGridRow],
) -> EquipmentsPayload:
    """장비별 집계 + 배지 판정을 위한 구간과 분포.

    `align_index`/`meas_index`는 간접표준화입니다: 실제 실패 건수를, 이 장비의
    레시피 구성이면 나왔어야 할 건수(레시피별 플릿 실패율 × 이 장비의 실행 수)
    로 나눕니다. 원 실패율로 장비를 줄세우면 정렬이 까다로운 레이어를 맡은
    장비가 저절로 불량 장비가 됩니다 — 장비 상태가 아니라 일감의 난이도를
    잰 것입니다.

    어떤 레시피를 장비 한 대만 돌았다면 그 레시피의 플릿 실패율이 곧 그
    장비의 실패율이라 해당 항이 정확히 1.0 을 기여합니다. 비교 정보가 없는
    일감은 지수를 1.0 쪽으로 희석시킬 뿐 없는 경보를 만들지 않습니다.

    **지수는 fab 하나 안에서만 비교 가능합니다.** `base(r)`이 조회 범위 전체의
    레시피별 평균이라, 여러 fab 을 함께 조회하면 fab 단위의 실패율 차이가 그
    fab 장비 *전부*의 지수가 됩니다. mock 의 FAB_ALIGN_FAIL_RATE 는 fab 별로
    0.05~0.15 로 3배 차이가 나므로 이 편향은 집에서 즉시 재현됩니다. 그래서
    프론트엔드는 조회 범위에 fab 이 2개 이상이면 배지를 아예 달지 않습니다
    (front-dev-home/app/utils/equipmentSignals.ts 의 isPeerGroupComparable).
    사무실에서도 같은 상관이 나타나는지는 OFFICE-VERIFY 입니다(MIGRATION.md).
    """
    per_tool: dict[str, dict] = {}
    per_recipe: dict[str, dict] = {}

    for row in grid:
        tool = per_tool.setdefault(row.eqp_id, {
            "eqp_id": row.eqp_id,
            "fab_name": row.fab_name,
            "eqp_model_cd": row.eqp_model_cd,
            "exec_count": 0,
            "align_fail_count": 0,
            "meas_fail_count": 0,
            "recipes": {},
        })
        tool["exec_count"] += row.exec_count
        tool["align_fail_count"] += row.align_fails
        tool["meas_fail_count"] += row.meas_fails

        cell = tool["recipes"].setdefault(row.full_name, {"execs": 0, "align": 0, "meas": 0})
        cell["execs"] += row.exec_count
        cell["align"] += row.align_fails
        cell["meas"] += row.meas_fails

        recipe = per_recipe.setdefault(row.full_name, {"execs": 0, "align": 0, "meas": 0})
        recipe["execs"] += row.exec_count
        recipe["align"] += row.align_fails
        recipe["meas"] += row.meas_fails

    # base(r) = 레시피 r 의 플릿 실패율
    base_align = {
        name: agg["align"] / agg["execs"]
        for name, agg in per_recipe.items() if agg["execs"]
    }
    base_meas = {
        name: agg["meas"] / agg["execs"]
        for name, agg in per_recipe.items() if agg["execs"]
    }

    equipments: list[EquipmentRow] = []
    for tool in per_tool.values():
        execs = tool["exec_count"]
        cells = tool["recipes"]

        # `if name in base` — execs 가 0 인 레시피는 base 에 없습니다. mock 은
        # 행마다 1 을 더하므로 도달할 수 없지만, office 의 composite 는
        # doc_count 0 인 버킷을 낼 수 있습니다. 0.0 으로 채우지 않고 건너뛰는
        # 이유: 기여할 실행이 없는 항은 분모에서 빠져야 하고, 0.0 을 더하면
        # 분모만 작아져 지수가 조용히 부풀어 오릅니다.
        expected_align = sum(
            cell["execs"] * base_align[name]
            for name, cell in cells.items() if name in base_align
        )
        expected_meas = sum(
            cell["execs"] * base_meas[name]
            for name, cell in cells.items() if name in base_meas
        )

        align_index, align_low, align_high = standardised(
            tool["align_fail_count"], expected_align
        )
        meas_index, meas_low, meas_high = standardised(
            tool["meas_fail_count"], expected_meas
        )

        # 2차 키로 full_name 을 명시합니다. execs 만으로 비교하면 동률에서 dict
        # 삽입 순서가 승자를 정하는데, 그 순서는 mock(행 스캔 순서)과
        # office(composite 버킷 순서)가 서로 다릅니다 — 같은 장비의 top_recipe
        # (표시값이자 `편중` 배지의 입력)가 provider 에 따라 달라집니다. max
        # 이므로 동률이면 full_name 이 사전순으로 뒤인 쪽이 이깁니다. 어느
        # 쪽을 고르든 상관없고, 정해져 있다는 것만 중요합니다.
        top_name, top_cell = max(
            cells.items(), key=lambda item: (item[1]["execs"], item[0]),
            default=(None, None)
        )

        equipments.append({
            "eqp_id": tool["eqp_id"],
            "fab_name": tool["fab_name"],
            "eqp_model_cd": tool["eqp_model_cd"],
            "exec_count": execs,
            "align_fail_count": tool["align_fail_count"],
            "align_fail_rate": round(tool["align_fail_count"] / execs, 4) if execs else 0.0,
            "align_expected": round(expected_align, 4),
            "align_index": align_index,
            "align_index_low": align_low,
            "align_index_high": align_high,
            "meas_fail_count": tool["meas_fail_count"],
            "meas_fail_rate": round(tool["meas_fail_count"] / execs, 4) if execs else 0.0,
            "meas_expected": round(expected_meas, 4),
            "meas_index": meas_index,
            "meas_index_low": meas_low,
            "meas_index_high": meas_high,
            "recipe_count": len(cells),
            "top_recipe": top_name,
            "top_recipe_share": (
                round(top_cell["execs"] / execs, 4) if execs and top_cell else 0.0
            ),
        })

    # 방향이 서로 달라 한 번에 정렬할 수 없습니다. 파이썬 정렬은 안정적이므로
    # 2차 키를 먼저 오름차순으로 깔고 1차 키를 내림차순으로 덮습니다.
    equipments.sort(key=lambda row: row["eqp_id"])
    equipments.sort(key=lambda row: row["exec_count"], reverse=True)

    total_execs = sum(row["exec_count"] for row in equipments)
    total_align = sum(row["align_fail_count"] for row in equipments)
    total_meas = sum(row["meas_fail_count"] for row in equipments)

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "fleet": {
            "tool_count": len(equipments),
            "total_executions": total_execs,
            "align_fail_count": total_align,
            "meas_fail_count": total_meas,
            "align_fail_rate": round(total_align / total_execs, 4) if total_execs else 0.0,
            "meas_fail_rate": round(total_meas / total_execs, 4) if total_execs else 0.0,
            "median_exec_count": float(
                statistics.median([row["exec_count"] for row in equipments])
            ) if equipments else 0.0,
            "median_recipe_count": float(
                statistics.median([row["recipe_count"] for row in equipments])
            ) if equipments else 0.0,
            "percentiles": {
                "exec_count": percentile_summary(r["exec_count"] for r in equipments),
                "recipe_count": percentile_summary(r["recipe_count"] for r in equipments),
                "align_fail_rate": percentile_summary(
                    r["align_fail_rate"] for r in equipments
                ),
                "meas_fail_rate": percentile_summary(
                    r["meas_fail_rate"] for r in equipments
                ),
                # None 장비는 제외 — 표본 미달은 "실패하지 않았다"가 아니라
                # "모른다"이고, 0 으로 채우면 p10 이 통째로 무너집니다.
                "align_index": percentile_summary(
                    r["align_index"] for r in equipments if r["align_index"] is not None
                ),
                "meas_index": percentile_summary(
                    r["meas_index"] for r in equipments if r["meas_index"] is not None
                ),
            },
        },
        "equipments": equipments,
    }


# (eqp_id, date, exec_count, align_fails, meas_fails)
TrendGridRow = tuple[str, str, int, int, int]
# (eqp_id, full_name, exec_count, align_fails, meas_fails)
RecipeGridRow = tuple[str, str, int, int, int]


def build_equipment_compare_payload(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: Sequence[str],
    trend_rows: Sequence[TrendGridRow],
    recipe_rows: Sequence[RecipeGridRow],
) -> EquipmentComparePayload:
    """선택된 장비들의 일별 추이와 레시피별 실패 구성을 한 응답에 담습니다.

    레시피 행은 선택 장비들의 **합집합**이고, 돌지 않은 장비 칸은 0 으로
    채웁니다. 클라이언트가 장비별 응답 여러 개를 조인하면 이 합집합과 0채움을
    매번 다시 만들어야 하고, 한 번 어긋나면 열이 밀려 다른 장비의 숫자를
    보여주게 됩니다.
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
            "recipes": [],
        }

    days = days_in_range(start_date, end_date)
    trend: dict[str, dict[str, dict]] = {
        eqp_id: {
            day: {"exec_count": 0, "align_fail_count": 0, "meas_fail_count": 0}
            for day in days
        }
        for eqp_id in selected
    }
    for eqp_id, day, execs, align_f, meas_f in trend_rows:
        bucket = trend.get(eqp_id, {}).get(day)
        if bucket is not None:
            bucket["exec_count"] += execs
            bucket["align_fail_count"] += align_f
            bucket["meas_fail_count"] += meas_f

    grid: dict[str, dict] = {}
    for eqp_id, full_name, execs, align_f, meas_f in recipe_rows:
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
            "total_exec_count": 0,
            "total_align_fail_count": 0,
            "total_meas_fail_count": 0,
            "cells": {
                picked: {"execs": 0, "align": 0, "meas": 0} for picked in selected
            },
        })
        recipe["total_exec_count"] += execs
        recipe["total_align_fail_count"] += align_f
        recipe["total_meas_fail_count"] += meas_f
        cell = recipe["cells"][eqp_id]
        cell["execs"] += execs
        cell["align"] += align_f
        cell["meas"] += meas_f

    # 활성 탭을 백엔드가 모르므로 두 지표의 합으로 정렬하고, 동률은 full_name
    # 으로 파훼합니다. 프론트엔드가 활성 aspect 로 다시 정렬하지만, 이 순서가
    # 결정적이지 않으면 페이지네이션이 흔들립니다.
    ordered = sorted(
        grid.values(),
        key=lambda e: (
            -(e["total_align_fail_count"] + e["total_meas_fail_count"]),
            e["full_name"],
        ),
    )

    recipes: list[EquipmentRecipeRow] = [
        {
            "class_name": entry["class_name"],
            "recipe_name": entry["recipe_name"],
            "full_name": entry["full_name"],
            "total_exec_count": entry["total_exec_count"],
            "total_align_fail_count": entry["total_align_fail_count"],
            "total_meas_fail_count": entry["total_meas_fail_count"],
            "cells": [
                {
                    "eqp_id": eqp_id,
                    "exec_count": entry["cells"][eqp_id]["execs"],
                    "align_fail_count": entry["cells"][eqp_id]["align"],
                    "meas_fail_count": entry["cells"][eqp_id]["meas"],
                }
                for eqp_id in selected
            ],
        }
        for entry in ordered
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
                        "exec_count": trend[eqp_id][day]["exec_count"],
                        "align_fail_count": trend[eqp_id][day]["align_fail_count"],
                        "meas_fail_count": trend[eqp_id][day]["meas_fail_count"],
                    }
                    for day in days
                ],
            }
            for eqp_id in selected
        ],
        "recipes": recipes,
    }
