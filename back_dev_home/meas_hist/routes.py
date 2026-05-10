from flask import Blueprint, jsonify, request

from back_dev_home.meas_hist.data import ToolType, get_meas_hist


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


@bp.get("/meas-hist")
def meas_hist_index():
    return jsonify(get_meas_hist(
        tool_type=_resolve_tool_type(),
        fab_name=_resolve_fab_name(),
        recipe_name=_resolve_recipe_name()
    ))
