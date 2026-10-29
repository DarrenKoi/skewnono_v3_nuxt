import secrets
from datetime import datetime

from flask import Blueprint, jsonify, request

from backend._auth.admin import require_admin
from backend._auth.errors import error_json
from backend.announcements.data import (
    add_announcement,
    get_announcements,
    list_all,
    remove_announcement,
)
from backend.announcements.providers.mock import _DEFAULT_TZ, _parse_bound

bp = Blueprint("announcements", __name__)

_LEVELS = ("info", "warning", "critical")
_TITLE_MAX = 200
_BODY_MAX = 2000


@bp.get("/announcements")
def announcements():
    return jsonify(get_announcements())


@bp.get("/admin/announcements")
@require_admin
def admin_list():
    return jsonify(list_all())


def _build(body: dict):
    """A stored row from the admin form, or an error message.

    The id is server-made and never reused: the banner remembers dismissals by
    id in each browser, so an edit is delete + add and shows again to everyone.
    """
    level = body.get("level", "info")
    title = str(body.get("title") or "").strip()
    text = str(body.get("body") or "").strip()
    if level not in _LEVELS:
        return None, f"level must be one of {', '.join(_LEVELS)}"
    if not title or len(title) > _TITLE_MAX:
        return None, f"title is required (max {_TITLE_MAX} chars)"
    if len(text) > _BODY_MAX:
        return None, f"body is too long (max {_BODY_MAX} chars)"
    row = {
        "id": f"{datetime.now(_DEFAULT_TZ):%Y-%m-%d}-{secrets.token_hex(3)}",
        "level": level,
        "title": title,
        "body": text,
        "dismissible": body.get("dismissible", True) is not False,
    }
    for bound in ("starts_at", "ends_at"):
        value = body.get(bound)
        if value:
            if _parse_bound(value) is None:
                return None, f"{bound} is not an ISO datetime"
            row[bound] = value
    return row, None


@bp.post("/admin/announcements")
@require_admin
def admin_add():
    row, err = _build(request.get_json(silent=True) or {})
    if err:
        return error_json("invalid_announcement", err, 400)
    add_announcement(row)
    return jsonify(row), 201


@bp.delete("/admin/announcements/<announcement_id>")
@require_admin
def admin_remove(announcement_id: str):
    if not remove_announcement(announcement_id):
        return error_json("not_found", f"no announcement {announcement_id!r}", 404)
    return jsonify({"removed": announcement_id})
