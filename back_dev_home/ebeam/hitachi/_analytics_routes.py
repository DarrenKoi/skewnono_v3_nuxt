"""Shared Flask request parsing for Recipe TAT and Fail Issue routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from flask import jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import (
    ToolType,
    resolve_tool_type_from_slug,
)


DEFAULT_DAYS = 14
# limit bounds the number of ranking rows (distinct recipes), not raw
# measurements. 0 means "no cap": every recipe in the date range is returned,
# so fleet-wide ranges never silently drop the tail of the ranking.
DEFAULT_LIMIT = 0
# equipment-compare 가 한 번에 받는 장비 수 상한.
#
# 정의가 여기 있는 이유: 요청 형태에 관한 값이지 응답 계약이 아니고, 이 파서를
# recipe_tat 과 fail_issue 가 함께 씁니다. recipe-tat spec §4.2 는 홈을
# `recipe_tat/contracts.py` 로 적었지만 — 소비자가 recipe_tat 하나뿐이던
# 때입니다 — 그대로 하면 공유 plumbing 이 기능 하나의 계약을 임포트하고
# fail_issue 까지 끌려옵니다. 이 이탈은 구현 계획에 근거와 함께 기록돼
# 있고(docs/superpowers/plans/2026-08-07-recipe-tat-by-equipment.md 의
# 이탈 목록), spec §4.2 도 그 결정을 가리킵니다.
#
# 이름은 프론트엔드 `utils/analyticsLimits.ts` 의 MAX_COMPARE_EQPS 와
# 맞춥니다. 2026-08-09 이전에는 여기가 `MAX_EQP_IDS` 였습니다: 같은 숫자가 두
# 이름으로 살면 한쪽만 바뀌어도 아무것도 깨지지 않은 것처럼 보입니다.
MAX_COMPARE_EQPS = 5


@dataclass(frozen=True)
class AnalyticsRequestScope:
    tool_type: ToolType
    fab_names: tuple[str, ...]
    start_date: str
    end_date: str
    lot_cd: str | None
    limit: int
    eqp_ids: tuple[str, ...]


def resolve_analytics_scope(
    tool_slug: str,
    anchor_time: datetime,
) -> AnalyticsRequestScope | None:
    tool_type = resolve_tool_type_from_slug(tool_slug)
    if tool_type is None:
        return None

    anchor = anchor_time.date()
    end_date = (request.args.get("end_date") or "").strip() or anchor.isoformat()
    start_date = (request.args.get("start_date") or "").strip()
    if not start_date:
        start_date = (anchor - timedelta(days=DEFAULT_DAYS)).isoformat()

    try:
        limit = int(request.args.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    return AnalyticsRequestScope(
        tool_type=tool_type,
        fab_names=tuple(
            part.strip().upper()
            for part in (request.args.get("fab_name") or "").split(",")
            if part.strip()
        ),
        start_date=start_date,
        end_date=end_date,
        lot_cd=(request.args.get("lot_cd") or "").strip() or None,
        limit=max(0, limit),
        # eqp_id 는 정확 일치 키입니다. fab_name 과 달리 대문자로 정규화하지
        # 않습니다 — 사무실 인덱스의 표기를 그대로 term 조회해야 합니다.
        eqp_ids=tuple(
            part.strip()
            for part in (request.args.get("eqp_id") or "").split(",")
            if part.strip()
        )[:MAX_COMPARE_EQPS],
    )


def bad_tool_slug_response():
    return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
