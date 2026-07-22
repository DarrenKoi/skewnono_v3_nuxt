from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import resolve_tool_type_from_slug
from back_dev_home.ebeam.hitachi.live_alarm.data import get_board


bp = Blueprint("ebeam_live_alarm", __name__)


@bp.get("/ebeam/<tool_slug>/live-alarm")
def live_alarm_board(tool_slug: str):
    tool_type = resolve_tool_type_from_slug(tool_slug)
    if tool_type is None:
        return jsonify(error=f"unknown tool slug: {tool_slug}"), 400

    fab_name = (request.args.get("fab_name") or "").strip()
    if not fab_name:
        return jsonify(error="fab_name is required"), 400

    return jsonify(get_board(tool_type, fab_name))
