from flask import Blueprint, jsonify, request

from back_dev_home.ebeam._slug_routes import (
    bad_tool_slug_response,
    resolve_sem_tool_type,
)
from back_dev_home.ebeam.live_alarm.data import get_board


bp = Blueprint("live_alarm", __name__)


@bp.get("/<tool_slug>/live-alarm")
def live_alarm_board(tool_slug: str):
    tool_type = resolve_sem_tool_type(tool_slug)
    if tool_type is None:
        return bad_tool_slug_response()

    raw = request.args.get("fab_name") or ""
    fab_names = tuple(part.strip().upper() for part in raw.split(",") if part.strip())
    if not fab_names:
        return jsonify(error="fab_name is required"), 400

    return jsonify(get_board(tool_type, fab_names))
