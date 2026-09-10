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

# Both mutating routes answer a failed persist with the same 503. One error
# tuple + one response builder so the two handlers cannot drift apart — the
# office adapter does the same for its own strings via _UNAVAILABLE.
_STORE_ERRORS = (StoreUnavailableError, OSError)


def _store_unavailable_503(action: str):
    return error_json(
        "store_unavailable", f"exception store unavailable; {action} NOT saved", 503
    )


# One combined read: the admin page needs all three at once, and separate
# calls would eat into the 50-req/5s per-user rate budget.
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
    except _STORE_ERRORS:
        return _store_unavailable_503("grant")
    return jsonify(row), 201


@bp.delete("/admin/access/exceptions/<user_id>")
@require_admin
def access_remove_exception(user_id: str):
    try:
        removed = remove_exception(user_id)
    except _STORE_ERRORS:
        return _store_unavailable_503("removal")
    if not removed:
        return error_json("not_found", f"no exception for {user_id!r}", 404)
    return jsonify({"removed": user_id.strip().upper()})
