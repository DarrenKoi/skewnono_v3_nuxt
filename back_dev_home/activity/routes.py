from flask import Blueprint, g, jsonify

from .._auth.errors import error_json
from .data import (
    get_me,
    get_summary,
    get_user_history,
    get_users_list,
    is_admin,
)

bp = Blueprint("activity", __name__)


def _require_admin():
    if not is_admin(g.user_id):
        return error_json("forbidden", "admin only", 403)
    return None


@bp.get("/activity/me")
def activity_me():
    return jsonify(get_me(g.user_id))


@bp.get("/activity/summary")
def activity_summary():
    blocked = _require_admin()
    if blocked is not None:
        return blocked
    return jsonify(get_summary())


@bp.get("/activity/users")
def activity_users():
    blocked = _require_admin()
    if blocked is not None:
        return blocked
    return jsonify(get_users_list())


@bp.get("/activity/users/<user_id>")
def activity_user_detail(user_id: str):
    blocked = _require_admin()
    if blocked is not None:
        return blocked
    payload = get_user_history(user_id)
    if payload is None:
        return error_json("not_found", f"no activity for user {user_id!r}", 404)
    return jsonify(payload)
