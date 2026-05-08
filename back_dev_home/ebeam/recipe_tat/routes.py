from datetime import timedelta

from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.recipe_tat.data import (
    ANCHOR_TIME,
    get_daily_trend,
    get_devices,
    get_ranking,
    get_summary
)


bp = Blueprint("ebeam_recipe_tat", __name__)

DEFAULT_DAYS = 30
SUPPORTED_TOOL_TYPES = ("cd-sem", "hv-sem")


def _resolve_tool_type() -> str | None:
    raw = (request.args.get("tool_type") or "").strip().lower()
    return raw if raw in SUPPORTED_TOOL_TYPES else None


def _resolve_dates() -> tuple[str, str]:
    """Default to last 30 days ending at the mock data anchor date.

    The mock generator captures `ANCHOR_TIME` once at module import, so the
    data window is fixed for the life of the Flask process. Defaulting to
    `datetime.now(...).date()` here would drift past the mock ceiling as
    the process keeps running — clients hitting the route hours later
    would silently get an empty trailing window. Pinning to
    `ANCHOR_TIME.date()` keeps the route's default exactly aligned with
    the data that actually exists.
    """
    end = (request.args.get("end_date") or "").strip()
    start = (request.args.get("start_date") or "").strip()

    anchor = ANCHOR_TIME.date()
    if not end:
        end = anchor.isoformat()
    if not start:
        start = (anchor - timedelta(days=DEFAULT_DAYS)).isoformat()

    return start, end


def _resolve_fab_id() -> str | None:
    raw = (request.args.get("fab_id") or "").strip()
    return raw or None


def _resolve_lot_cd() -> str | None:
    raw = (request.args.get("lot_cd") or "").strip()
    return raw or None


def _resolve_limit(default: int = 1000, cap: int = 1000) -> int:
    try:
        value = int(request.args.get("limit", default))
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, cap))


@bp.get("/cdsem/recipe-tat/ranking")
def recipe_tat_ranking():
    tool_type = _resolve_tool_type()
    if not tool_type:
        return jsonify({"error": "tool_type must be 'cd-sem' or 'hv-sem'"}), 400

    fab_id = _resolve_fab_id()
    start_date, end_date = _resolve_dates()
    limit = _resolve_limit()
    lot_cd = _resolve_lot_cd()

    rows = get_ranking(tool_type, fab_id, start_date, end_date, limit=limit, lot_cd=lot_cd)
    return jsonify({
        "tool_type": tool_type,
        "fab_id": fab_id,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "lot_cd": lot_cd,
        "rows": rows
    })


@bp.get("/cdsem/recipe-tat/summary")
def recipe_tat_summary():
    tool_type = _resolve_tool_type()
    if not tool_type:
        return jsonify({"error": "tool_type must be 'cd-sem' or 'hv-sem'"}), 400

    fab_id = _resolve_fab_id()
    start_date, end_date = _resolve_dates()
    lot_cd = _resolve_lot_cd()

    return jsonify(get_summary(tool_type, fab_id, start_date, end_date, lot_cd=lot_cd))


@bp.get("/cdsem/recipe-tat/daily-trend")
def recipe_tat_daily_trend():
    tool_type = _resolve_tool_type()
    if not tool_type:
        return jsonify({"error": "tool_type must be 'cd-sem' or 'hv-sem'"}), 400

    fab_id = _resolve_fab_id()
    start_date, end_date = _resolve_dates()
    lot_cd = _resolve_lot_cd()

    points = get_daily_trend(tool_type, fab_id, start_date, end_date, lot_cd=lot_cd)
    return jsonify({
        "tool_type": tool_type,
        "fab_id": fab_id,
        "start_date": start_date,
        "end_date": end_date,
        "lot_cd": lot_cd,
        "points": points
    })


@bp.get("/cdsem/recipe-tat/devices")
def recipe_tat_devices():
    tool_type = _resolve_tool_type()
    if not tool_type:
        return jsonify({"error": "tool_type must be 'cd-sem' or 'hv-sem'"}), 400

    fab_id = _resolve_fab_id()
    start_date, end_date = _resolve_dates()

    devices = get_devices(tool_type, fab_id, start_date, end_date)
    return jsonify({
        "tool_type": tool_type,
        "fab_id": fab_id,
        "start_date": start_date,
        "end_date": end_date,
        "devices": devices
    })
