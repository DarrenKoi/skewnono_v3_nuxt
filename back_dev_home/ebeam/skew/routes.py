from flask import Blueprint, jsonify, request

from back_dev_home.ebeam._tool_specs import VALID_TOOL_SLUGS
from back_dev_home.ebeam.skew.data import get_skew_check

bp = Blueprint("ebeam_skew", __name__)


def _arg(name: str) -> str | None:
    raw = (request.args.get(name) or "").strip()
    return raw or None


@bp.get("/<tool_slug>/skew/check")
def skew_check(tool_slug: str):
    if tool_slug not in VALID_TOOL_SLUGS:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    fab_name = _arg("fab_name")
    if fab_name is None:
        return jsonify({"error": "fab_name is required"}), 400
    payload = get_skew_check(tool_slug, fab_name, _arg("recipe_id"))
    return jsonify(payload)
