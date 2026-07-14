from flask import Blueprint, jsonify, request

from .._auth.admin import require_admin
from .._auth.errors import error_json
from .data import (
    BLOCKED_PREFIX,
    StoreUnavailableError,
    add_exception,
    list_denied,
    list_exceptions,
    remove_exception,
)

bp = Blueprint("access_control", __name__)


# One combined read: the admin page needs all three at once, and separate
# calls would eat into the 20-req/5s per-user rate budget.
@bp.get("/admin/access")
@require_admin
def access_overview():
    return jsonify(
        {
            "rule": {"blocked_prefix": BLOCKED_PREFIX},
            "exceptions": list_exceptions(),
            "denied": list_denied(),
        }
    )


@bp.post("/admin/access/exceptions")
@require_admin
def access_add_exception():
    body = request.get_json(silent=True) or {}
    try:
        row = add_exception(str(body.get("user_id", "")))
    except ValueError as exc:
        return error_json("invalid_member_id", str(exc), 400)
    except (StoreUnavailableError, OSError):
        return error_json("store_unavailable", "exception store unavailable; grant NOT saved", 503)
    return jsonify(row), 201


@bp.delete("/admin/access/exceptions/<user_id>")
@require_admin
def access_remove_exception(user_id: str):
    try:
        removed = remove_exception(user_id)
    except (StoreUnavailableError, OSError):
        return error_json("store_unavailable", "exception store unavailable; removal NOT saved", 503)
    if not removed:
        return error_json("not_found", f"no exception for {user_id!r}", 404)
    return jsonify({"removed": user_id.strip().upper()})
