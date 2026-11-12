from datetime import date

from flask import Blueprint, jsonify, request

from backend._core.request_args import resolve_fab_names
from backend.ebeam._tool_specs import (
    SEM_TOOL_SLUGS,
    SLUG_TO_TOOL_TYPE,
    VALID_TOOL_SLUGS,
)
from backend.ebeam.recipe_usage.data import (
    WindowError,
    get_catalog,
    get_recipe_detail,
    get_status,
)


bp = Blueprint("recipe_usage", __name__)

# Derived, never spelled out: the families the CD/HV-only screens refuse. A
# Hitachi slug gets a 400 here for the same reason an AMAT slug gets one
# there -- these keys do not exist for it.
AMAT_TOOL_SLUGS: frozenset[str] = VALID_TOOL_SLUGS - SEM_TOOL_SLUGS


def _tool_type(tool_slug: str):
    slug = (tool_slug or "").strip().lower()
    return SLUG_TO_TOOL_TYPE[slug] if slug in AMAT_TOOL_SLUGS else None


def _bad_request(message: str):
    return jsonify({"error": message}), 400


def _bad_tool_slug():
    allowed = " or ".join(repr(slug) for slug in sorted(AMAT_TOOL_SLUGS))
    return _bad_request(f"tool_slug must be {allowed}")


def _date_arg(name: str) -> date | None:
    raw = (request.args.get(name) or "").strip()
    return date.fromisoformat(raw) if raw else None


@bp.get("/<tool_slug>/recipe-usage/recipes")
def recipe_usage_recipes(tool_slug: str):
    tool_type = _tool_type(tool_slug)
    if tool_type is None:
        return _bad_tool_slug()
    return jsonify(get_catalog(tool_type, resolve_fab_names()))


@bp.get("/<tool_slug>/recipe-usage/recipe")
def recipe_usage_recipe(tool_slug: str):
    tool_type = _tool_type(tool_slug)
    if tool_type is None:
        return _bad_tool_slug()
    # A query param, not a path segment: recipe_id contains "/".
    recipe_id = (request.args.get("recipe_id") or "").strip()
    if not recipe_id:
        return _bad_request("recipe_id is required")
    return jsonify(get_recipe_detail(tool_type, recipe_id, resolve_fab_names()))


@bp.get("/<tool_slug>/recipe-usage/status")
def recipe_usage_status(tool_slug: str):
    tool_type = _tool_type(tool_slug)
    if tool_type is None:
        return _bad_tool_slug()
    try:
        start, end = _date_arg("start_date"), _date_arg("end_date")
    except ValueError:
        return _bad_request("start_date and end_date must be YYYY-MM-DD")
    try:
        return jsonify(get_status(tool_type, resolve_fab_names(), start, end))
    except WindowError as err:
        return _bad_request(str(err))
