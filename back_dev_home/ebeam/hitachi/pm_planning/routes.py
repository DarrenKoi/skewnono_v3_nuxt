from flask import Blueprint, jsonify

from back_dev_home._core.request_args import resolve_fab_name
from back_dev_home.ebeam.hitachi._tool_specs import VALID_TOOL_SLUGS
from back_dev_home.ebeam.hitachi.pm_planning.data import get_pm_planning_fleet


bp = Blueprint("ebeam_pm_planning", __name__)


def _bad_slug_response():
    return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400


@bp.get("/<tool_slug>/pm-planning/fleet")
def pm_planning_fleet(tool_slug: str):
    if tool_slug not in VALID_TOOL_SLUGS:
        return _bad_slug_response()
    if tool_slug != "cdsem":
        return jsonify({"error": "pm-planning is available for CD-SEM only"}), 400

    fab_name = resolve_fab_name()
    if not fab_name:
        return jsonify({"error": "fab_name query parameter is required"}), 400

    return jsonify(get_pm_planning_fleet(fab_name))
