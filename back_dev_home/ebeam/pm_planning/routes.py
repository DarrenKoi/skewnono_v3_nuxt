from flask import Blueprint, jsonify

from back_dev_home._core.request_args import resolve_fab_name
from back_dev_home.ebeam._slug_routes import (
    bad_tool_slug_response,
    is_sem_tool_slug,
)
from back_dev_home.ebeam.pm_planning.data import get_pm_planning_fleet


bp = Blueprint("pm_planning", __name__)


@bp.get("/<tool_slug>/pm-planning/fleet")
def pm_planning_fleet(tool_slug: str):
    if not is_sem_tool_slug(tool_slug):
        return bad_tool_slug_response()
    if tool_slug != "cdsem":
        return jsonify({"error": "pm-planning is available for CD-SEM only"}), 400

    fab_name = resolve_fab_name()
    if not fab_name:
        return jsonify({"error": "fab_name query parameter is required"}), 400

    return jsonify(get_pm_planning_fleet(fab_name))
