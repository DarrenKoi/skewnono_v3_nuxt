from flask import Blueprint, jsonify

from back_dev_home.ebeam.hitachi._analytics_routes import (
    bad_tool_slug_response,
    resolve_analytics_scope,
)
from back_dev_home.ebeam.hitachi.fail_issue.data import (
    get_anchor_time,
    get_align_ranking,
    get_daily_trend,
    get_devices,
    get_meas_ranking,
    get_summary
)


bp = Blueprint("ebeam_fail_issue", __name__)

@bp.get("/<tool_slug>/fail-issue/summary")
def fail_issue_summary(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    return jsonify(get_summary(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
        lot_cd=scope.lot_cd,
    ))


@bp.get("/<tool_slug>/fail-issue/daily-trend")
def fail_issue_daily_trend(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    points = get_daily_trend(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
        lot_cd=scope.lot_cd,
    )
    return jsonify({
        "tool_type": scope.tool_type,
        "fab_names": list(scope.fab_names),
        "start_date": scope.start_date,
        "end_date": scope.end_date,
        "lot_cd": scope.lot_cd,
        "points": points
    })


@bp.get("/<tool_slug>/fail-issue/align-ranking")
def fail_issue_align_ranking(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    rows = get_align_ranking(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
        limit=scope.limit,
        lot_cd=scope.lot_cd,
    )
    return jsonify({
        "tool_type": scope.tool_type,
        "fab_names": list(scope.fab_names),
        "start_date": scope.start_date,
        "end_date": scope.end_date,
        "limit": scope.limit,
        "lot_cd": scope.lot_cd,
        "rows": rows
    })


@bp.get("/<tool_slug>/fail-issue/meas-ranking")
def fail_issue_meas_ranking(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    rows = get_meas_ranking(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
        limit=scope.limit,
        lot_cd=scope.lot_cd,
    )
    return jsonify({
        "tool_type": scope.tool_type,
        "fab_names": list(scope.fab_names),
        "start_date": scope.start_date,
        "end_date": scope.end_date,
        "limit": scope.limit,
        "lot_cd": scope.lot_cd,
        "rows": rows
    })


@bp.get("/<tool_slug>/fail-issue/devices")
def fail_issue_devices(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    devices = get_devices(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
    )
    return jsonify({
        "tool_type": scope.tool_type,
        "fab_names": list(scope.fab_names),
        "start_date": scope.start_date,
        "end_date": scope.end_date,
        "devices": devices
    })
