from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.recipe_search.data import ToolType, get_recipe_catalog, get_recipe_open_data


bp = Blueprint("ebeam_recipe_search", __name__)

TOOL_BY_SLUG: dict[str, ToolType] = {
    "cdsem": "cd-sem",
    "hvsem": "hv-sem"
}


def _resolve_tool_type(tool_slug: str) -> ToolType | None:
    return TOOL_BY_SLUG.get(tool_slug.strip().lower())


def _resolve_fab_name() -> str | None:
    raw = (request.args.get("fab_name") or "").strip().upper()
    return raw or None


@bp.get("/<tool_slug>/recipe-search/recipes")
def recipe_search_recipes(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    return jsonify(get_recipe_catalog(tool_type, _resolve_fab_name()))


@bp.get("/<tool_slug>/recipe-search/recipe-detail")
def recipe_search_recipe_detail(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    recipe_name = (request.args.get("recipe_name") or "").strip()
    if not recipe_name:
        return jsonify({"error": "recipe_name is required"}), 400

    return jsonify(get_recipe_open_data(
        recipe_id=recipe_name,
        fac_id=_resolve_fab_name(),
        tool_category=tool_type
    ))
