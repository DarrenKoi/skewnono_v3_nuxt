import logging

from flask import Blueprint, g, jsonify

from .._auth.errors import error_json
from .data import (
    get_fab_page_usage,
    get_me,
    get_summary,
    get_user_history,
    get_users_list,
)

bp = Blueprint("activity", __name__)
logger = logging.getLogger(__name__)


def _query(loader, *, not_found: str | None = None):
    try:
        payload = loader()
    except Exception:
        logger.exception("Failed to query OpenSearch activity")
        return error_json(
            "activity_query_failed",
            "Could not query OpenSearch activity",
            503,
        )
    if payload is None and not_found is not None:
        return error_json("not_found", not_found, 404)
    return jsonify(payload)


@bp.get("/activity/me")
def activity_me():
    return _query(lambda: get_me(g.user_id))


@bp.get("/activity/summary")
def activity_summary():
    return _query(get_summary)


@bp.get("/activity/fabs")
def activity_fabs():
    return _query(get_fab_page_usage)


@bp.get("/activity/users")
def activity_users():
    return _query(get_users_list)


@bp.get("/activity/users/<user_id>")
def activity_user_detail(user_id: str):
    return _query(
        lambda: get_user_history(user_id),
        not_found=f"no activity for user {user_id!r}",
    )
