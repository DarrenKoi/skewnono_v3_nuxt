from flask import Blueprint, jsonify, request

from back_dev_home._core.request_args import resolve_fab_name
from back_dev_home.ebeam._slug_routes import (
    bad_tool_slug_response,
    resolve_sem_tool_type,
)
from back_dev_home.ebeam.lateral_recipe.data import get_lateral_recipe


bp = Blueprint("lateral_recipe", __name__)


@bp.get("/<tool_slug>/recipe-search/lateral")
def recipe_search_lateral(tool_slug: str):
    tool_type = resolve_sem_tool_type(tool_slug)
    if not tool_type:
        return bad_tool_slug_response()

    recipe_name = (request.args.get("recipe_name") or "").strip()
    if not recipe_name:
        return jsonify({"error": "recipe_name is required"}), 400

    return jsonify(get_lateral_recipe(tool_type, resolve_fab_name(), recipe_name))
