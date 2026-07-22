from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from back_dev_home.ebeam.hitachi._tool_specs import VALID_TOOL_SLUGS
from back_dev_home.ebeam.hitachi.hardware.contracts import VALID_SERVICES
from back_dev_home.ebeam.hitachi.hardware.data import get_hardware_service


bp = Blueprint("ebeam_hardware", __name__)

# Anchor matches the mock generators so the default 30-day window lines up
# with the data they fabricate.
_NOW = datetime(2026, 5, 24, 9, 0)
_DEFAULT_WINDOW_DAYS = 30


def _resolve_eqp_id(raw_segment: str) -> str | None:
    seg = (raw_segment or "").strip()
    # "_" is the frontend's placeholder for "no tool selected yet".
    if not seg or seg == "_":
        return None
    return seg


def _resolve_fab_name() -> str | None:
    raw = (request.args.get("fab_name") or "").strip()
    return raw or None


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "").strip())
    except ValueError:
        return None


def _resolve_window() -> tuple[datetime, datetime]:
    end = _parse_iso(request.args.get("end")) or _NOW
    start = _parse_iso(request.args.get("start")) or (end - timedelta(days=_DEFAULT_WINDOW_DAYS))
    if start > end:
        start, end = end, start
    return start, end


@bp.get("/<tool_slug>/hardware/<eqp_id>/<service>")
def hardware_service(tool_slug: str, eqp_id: str, service: str):
    if tool_slug not in VALID_TOOL_SLUGS:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    if service not in VALID_SERVICES:
        allowed = ", ".join(repr(s) for s in sorted(VALID_SERVICES))
        return jsonify({"error": f"service must be one of {allowed}"}), 400

    start, end = _resolve_window()
    payload = get_hardware_service(
        tool_slug,
        service,  # type: ignore[arg-type]
        _resolve_eqp_id(eqp_id),
        _resolve_fab_name(),
        start,
        end,
    )
    return jsonify(payload)
