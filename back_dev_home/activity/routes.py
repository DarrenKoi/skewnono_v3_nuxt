from flask import Blueprint, g, jsonify

from .._auth.errors import error_json
from .data import (
    get_me,
    get_sem_model_usage,
    get_summary,
    get_user_history,
    get_users_list,
)

bp = Blueprint("activity", __name__)


@bp.get("/activity/me")
def activity_me():
    return jsonify(get_me(g.user_id))


@bp.get("/activity/summary")
def activity_summary():
    return jsonify(get_summary())


@bp.get("/activity/sem-models")
def activity_sem_models():
    return jsonify(get_sem_model_usage())


@bp.get("/activity/users")
def activity_users():
    return jsonify(get_users_list())


@bp.get("/activity/users/<user_id>")
def activity_user_detail(user_id: str):
    payload = get_user_history(user_id)
    if payload is None:
        return error_json("not_found", f"no activity for user {user_id!r}", 404)
    return jsonify(payload)
