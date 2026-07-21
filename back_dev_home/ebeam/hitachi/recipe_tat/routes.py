from flask import Blueprint, jsonify

from back_dev_home.ebeam.hitachi._analytics_routes import (
    bad_tool_slug_response,
    resolve_analytics_scope,
)
from back_dev_home.ebeam.hitachi.recipe_tat.data import (
    get_anchor_time,
    get_daily_trend,
    get_devices,
    get_ranking,
    get_summary
)


bp = Blueprint("ebeam_recipe_tat", __name__)

@bp.get("/<tool_slug>/recipe-tat/ranking")
def recipe_tat_ranking(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    rows = get_ranking(
        scope.tool_type,
        scope.fab_name,
        scope.start_date,
        scope.end_date,
        limit=scope.limit,
        lot_cd=scope.lot_cd,
    )
    return jsonify({
        "tool_type": scope.tool_type,
        "fab_name": scope.fab_name,
        "start_date": scope.start_date,
        "end_date": scope.end_date,
        "limit": scope.limit,
        "lot_cd": scope.lot_cd,
        "rows": rows
    })


@bp.get("/<tool_slug>/recipe-tat/summary")
def recipe_tat_summary(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    return jsonify(get_summary(
        scope.tool_type,
        scope.fab_name,
        scope.start_date,
        scope.end_date,
        lot_cd=scope.lot_cd,
    ))


@bp.get("/<tool_slug>/recipe-tat/daily-trend")
def recipe_tat_daily_trend(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    points = get_daily_trend(
        scope.tool_type,
        scope.fab_name,
        scope.start_date,
        scope.end_date,
        lot_cd=scope.lot_cd,
    )
    return jsonify({
        "tool_type": scope.tool_type,
        "fab_name": scope.fab_name,
        "start_date": scope.start_date,
        "end_date": scope.end_date,
        "lot_cd": scope.lot_cd,
        "points": points
    })


@bp.get("/<tool_slug>/recipe-tat/devices")
def recipe_tat_devices(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    devices = get_devices(
        scope.tool_type,
        scope.fab_name,
        scope.start_date,
        scope.end_date,
    )
    return jsonify({
        "tool_type": scope.tool_type,
        "fab_name": scope.fab_name,
        "start_date": scope.start_date,
        "end_date": scope.end_date,
        "devices": devices
    })
