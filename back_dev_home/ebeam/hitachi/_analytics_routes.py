"""Shared Flask request parsing for Recipe TAT and Fail Issue routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from flask import jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import (
    ToolType,
    resolve_tool_type_from_slug,
)


DEFAULT_DAYS = 30
DEFAULT_LIMIT = 1000
MAX_LIMIT = 1000


@dataclass(frozen=True)
class AnalyticsRequestScope:
    tool_type: ToolType
    fab_id: str | None
    start_date: str
    end_date: str
    lot_cd: str | None
    limit: int


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
        fab_id=(request.args.get("fab_id") or "").strip() or None,
        start_date=start_date,
        end_date=end_date,
        lot_cd=(request.args.get("lot_cd") or "").strip() or None,
        limit=max(1, min(limit, MAX_LIMIT)),
    )


def bad_tool_slug_response():
    return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
