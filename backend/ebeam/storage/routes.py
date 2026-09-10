from flask import Blueprint, jsonify, request

from .._slug_routes import bad_tool_slug_response, is_sem_tool_slug
from .data import get_storage, get_ppid_unavailable


bp = Blueprint("storage", __name__)


def _parse_fab_names() -> list[str]:
    fab_name_param = request.args.get("fab_name", "")
    return [value.strip() for value in fab_name_param.split(",") if value.strip()]


def _validate_slug(tool_slug: str) -> str | None:
    return tool_slug if is_sem_tool_slug(tool_slug) else None


@bp.get("/<tool_slug>/storage")
def storage(tool_slug: str):
    slug = _validate_slug(tool_slug)
    if not slug:
        return bad_tool_slug_response()

    rows = get_storage(slug, _parse_fab_names())
    return jsonify(rows)


@bp.get("/<tool_slug>/ppid-unavailable")
def ppid_unavailable(tool_slug: str):
    slug = _validate_slug(tool_slug)
    if not slug:
        return bad_tool_slug_response()

    rows = get_ppid_unavailable(slug, _parse_fab_names())
    return jsonify(rows)
