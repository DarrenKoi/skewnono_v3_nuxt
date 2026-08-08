from flask import Blueprint, jsonify, request

from .._tool_specs import VALID_TOOL_SLUGS
from .data import get_storage, get_ppid_unavailable


bp = Blueprint("hitachi_storage", __name__)


def _parse_fab_names() -> list[str]:
    fab_name_param = request.args.get("fab_name", "")
    return [value.strip() for value in fab_name_param.split(",") if value.strip()]


def _validate_slug(tool_slug: str) -> str | None:
    return tool_slug if tool_slug in VALID_TOOL_SLUGS else None


@bp.get("/<tool_slug>/storage")
def storage(tool_slug: str):
    slug = _validate_slug(tool_slug)
    if not slug:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    rows = get_storage(slug, _parse_fab_names())
    return jsonify(rows)


@bp.get("/<tool_slug>/ppid-unavailable")
def ppid_unavailable(tool_slug: str):
    slug = _validate_slug(tool_slug)
    if not slug:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    rows = get_ppid_unavailable(slug, _parse_fab_names())
    return jsonify(rows)
