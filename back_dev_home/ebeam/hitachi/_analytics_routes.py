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
# equipment-compare 가 한 번에 받는 장비 수 상한. 요청 형태에 관한 값이라
# 계약이 아니라 파서가 소유합니다. fail_issue 도 같은 헬퍼를 쓰지만 이
# 필드를 읽지 않으므로 무해합니다.
MAX_EQP_IDS = 5


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
        )[:MAX_EQP_IDS],
    )


def bad_tool_slug_response():
    return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
