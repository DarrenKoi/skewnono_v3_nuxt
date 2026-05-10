from flask import Blueprint, jsonify, request

from .._tool_specs import VALID_TOOL_SLUGS
from .data import get_storage, get_storage_unavailable


bp = Blueprint("hitachi_storage", __name__)


def _parse_fac_ids() -> list[str]:
    fac_id_param = request.args.get("fac_id", "")
    return [value.strip() for value in fac_id_param.split(",") if value.strip()]


def _validate_slug(tool_slug: str) -> str | None:
    return tool_slug if tool_slug in VALID_TOOL_SLUGS else None


@bp.get("/<tool_slug>/storage")
def storage(tool_slug: str):
    slug = _validate_slug(tool_slug)
    if not slug:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    rows = get_storage(slug, _parse_fac_ids())
    return jsonify(rows)


@bp.get("/<tool_slug>/storage-unavailable")
def storage_unavailable(tool_slug: str):
    slug = _validate_slug(tool_slug)
    if not slug:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    rows = get_storage_unavailable(slug, _parse_fac_ids())
    return jsonify(rows)
