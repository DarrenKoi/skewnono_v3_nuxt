from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import VALID_TOOL_SLUGS
from back_dev_home.ebeam.hitachi.hardware.data import (
    VALID_SERVICES,
    get_hardware_service
)


bp = Blueprint("ebeam_hardware", __name__)


def _resolve_eqp_id() -> str | None:
    raw = (request.args.get("eqp_id") or "").strip()
    return raw or None


def _resolve_fab_id() -> str | None:
    raw = (request.args.get("fab_id") or "").strip()
    return raw or None


@bp.get("/<tool_slug>/hardware/<service>")
def hardware_service(tool_slug: str, service: str):
    if tool_slug not in VALID_TOOL_SLUGS:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    if service not in VALID_SERVICES:
        allowed = ", ".join(repr(s) for s in sorted(VALID_SERVICES))
        return jsonify({"error": f"service must be one of {allowed}"}), 400

    payload = get_hardware_service(
        tool_slug,
        service,  # type: ignore[arg-type]
        _resolve_eqp_id(),
        _resolve_fab_id()
    )
    return jsonify(payload)
