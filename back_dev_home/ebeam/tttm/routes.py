from flask import Blueprint, jsonify, request

from back_dev_home.ebeam._slug_routes import (
    bad_tool_slug_response,
    is_sem_tool_slug,
)
from back_dev_home.ebeam.tttm.data import get_tttm_check, get_tttm_recipes

bp = Blueprint("tttm", __name__)


def _arg(name: str) -> str | None:
    raw = (request.args.get(name) or "").strip()
    return raw or None


@bp.get("/<tool_slug>/tttm/check")
def tttm_check(tool_slug: str):
    if not is_sem_tool_slug(tool_slug):
        return bad_tool_slug_response()
    fab_name = _arg("fab_name")
    if fab_name is None:
        return jsonify({"error": "fab_name is required"}), 400
    recipe_id = _arg("recipe_id")
    parameter = _arg("parameter")
    # A parameter name is a row of ONE recipe's idp_image_info, and the same
    # name in another recipe measures a different feature — so "this parameter,
    # across every recipe" is not a question with an answer. Refused rather than
    # ignored: a silently dropped filter returns a group verdict under a
    # parameter heading the server never applied, and nothing about that
    # response looks wrong to the client.
    if parameter is not None and recipe_id is None:
        return jsonify({"error": "parameter requires recipe_id"}), 400
    payload = get_tttm_check(tool_slug, fab_name, recipe_id, parameter)
    return jsonify(payload)


@bp.get("/<tool_slug>/tttm/recipes")
def tttm_recipes(tool_slug: str):
    """Recipes this fab has measured, for the shared pm-tune / TTTM picker.

    Same slug and fab_name rules as `/tttm/check`, so a fab that answers one
    answers the other — a picker scoped differently from the payload it drives
    would offer recipes the check then finds nothing for.
    """
    if not is_sem_tool_slug(tool_slug):
        return bad_tool_slug_response()
    fab_name = _arg("fab_name")
    if fab_name is None:
        return jsonify({"error": "fab_name is required"}), 400
    return jsonify(get_tttm_recipes(tool_slug, fab_name))
