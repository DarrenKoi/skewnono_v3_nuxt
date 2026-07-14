from flask import Blueprint, jsonify, request

from back_dev_home.meas_hist.data import (
    DEFAULT_LIMIT,
    ToolType,
    get_meas_hist,
    get_meas_hist_facets,
    search_meas_hist,
)


bp = Blueprint("meas_hist", __name__)

VALID_TOOL_TYPES: tuple[ToolType, ...] = ("cd-sem", "hv-sem")


def _resolve_tool_type() -> ToolType | None:
    raw = (request.args.get("tool_type") or "").strip().lower()
    return raw if raw in VALID_TOOL_TYPES else None


def _resolve_fab_name() -> str | None:
    raw = (request.args.get("fab_name") or "").strip().upper()
    return raw or None


def _resolve_recipe_name() -> str | None:
    raw = (request.args.get("recipe_name") or "").strip()
    return raw or None


def _list_arg(name: str) -> list[str]:
    """Repeated query params (?eq=A&eq=B) — values within a field OR together."""
    return [value.strip() for value in request.args.getlist(name) if value.strip()]


def _int_arg(name: str, default: int) -> int:
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


@bp.get("/meas-hist")
def meas_hist_index():
    return jsonify(get_meas_hist(
        tool_type=_resolve_tool_type(),
        fab_name=_resolve_fab_name(),
        recipe_name=_resolve_recipe_name()
    ))


@bp.get("/meas-hist/search")
def meas_hist_search():
    return jsonify(search_meas_hist(
        tool_type=_resolve_tool_type(),
        fab=_list_arg("fab"),
        model=_list_arg("model"),
        eq=_list_arg("eq"),
        recipe=_list_arg("recipe"),
        lot=_list_arg("lot"),
        msr=_list_arg("msr"),
        q=_list_arg("q"),
        date_from=request.args.get("from"),
        date_to=request.args.get("to"),
        offset=_int_arg("offset", 0),
        limit=_int_arg("limit", DEFAULT_LIMIT)
    ))


@bp.get("/meas-hist/facets")
def meas_hist_facets():
    return jsonify(get_meas_hist_facets(tool_type=_resolve_tool_type()))
