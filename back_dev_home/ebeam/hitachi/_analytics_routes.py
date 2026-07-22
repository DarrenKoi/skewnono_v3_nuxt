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


@dataclass(frozen=True)
class AnalyticsRequestScope:
    tool_type: ToolType
    fab_name: str | None
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
        fab_name=(request.args.get("fab_name") or "").strip() or None,
        start_date=start_date,
        end_date=end_date,
        lot_cd=(request.args.get("lot_cd") or "").strip() or None,
        limit=max(0, limit),
    )


def bad_tool_slug_response():
    return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
