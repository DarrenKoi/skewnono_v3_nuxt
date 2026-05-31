from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import VALID_TOOL_SLUGS
from back_dev_home.ebeam.hitachi.pm_planning.data import get_pm_planning_fleet


bp = Blueprint("ebeam_pm_planning", __name__)


def _resolve_fab_id() -> str | None:
    raw = (request.args.get("fab_id") or "").strip()
    return raw or None


def _bad_slug_response():
    return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400


@bp.get("/<tool_slug>/pm-planning/fleet")
def pm_planning_fleet(tool_slug: str):
    if tool_slug not in VALID_TOOL_SLUGS:
        return _bad_slug_response()
    if tool_slug != "cdsem":
        return jsonify({"error": "pm-planning is available for CD-SEM only"}), 400

    fab_id = _resolve_fab_id()
    if not fab_id:
        return jsonify({"error": "fab_id query parameter is required"}), 400

    return jsonify(get_pm_planning_fleet(fab_id))
