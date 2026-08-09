from flask import Blueprint, jsonify, request

from back_dev_home._core.request_args import resolve_fab_name
from back_dev_home.ebeam._tool_specs import SLUG_TO_TOOL_TYPE
from back_dev_home.meas_hist.data import (
    DEFAULT_LIMIT,
    ToolType,
    get_meas_hist,
    get_meas_hist_facets,
    search_meas_hist,
)


bp = Blueprint("meas_hist", __name__)

# 하드코딩하지 않습니다. 계열이 늘어나면 레지스트리만 고칩니다.
VALID_TOOL_TYPES: frozenset[str] = frozenset(SLUG_TO_TOOL_TYPE.values())


class _UnknownToolType(Exception):
    pass


def _resolve_tool_type() -> ToolType | None:
    """미지정이면 None(= 전체), 미지의 값이면 예외.

    둘을 같은 None 으로 뭉개면 'veritysem 으로 필터했는데 전 장비가 나오는'
    조용한 오답이 됩니다. 400 이 정답입니다.
    """
    raw = (request.args.get("tool_type") or "").strip().lower()
    if not raw:
        return None
    if raw not in VALID_TOOL_TYPES:
        raise _UnknownToolType(raw)
    return raw  # type: ignore[return-value]


@bp.errorhandler(_UnknownToolType)
def _reject_unknown_tool_type(exc: _UnknownToolType):
    return jsonify({
        "error": f"unknown tool_type {exc.args[0]!r}; "
                 f"expected one of {sorted(VALID_TOOL_TYPES)}"
    }), 400


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
        fab_name=resolve_fab_name(),
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
