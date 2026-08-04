import logging

from flask import Blueprint, g, jsonify, request

from .._auth.admin import require_admin
from .._auth.directory import lookup_members
from .._auth.errors import error_json
from .._logging.feature_map import page_to_feature
from .contracts import NamedUserListResponse
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


def _named_users_list() -> NamedUserListResponse:
    """The users list with each employee number expanded into a person.

    The join lives here rather than in the providers because it is the same
    join on both sides of the swap: ``lookup_members`` decides for itself
    whether to dial office Redis or fabricate a home row, so neither
    ``mock.py`` nor ``office.py`` has anything to contribute. Putting it in the
    route also keeps the provider contract honest — the logging store records
    employee numbers and no names, so ``UserListRow`` should not promise one.

    A directory that cannot answer costs the names and not the table:
    ``lookup_members`` never raises, and ``emp_nm`` is simply None.
    """
    payload = get_users_list()
    rows = payload["users"]
    members = lookup_members(row["user_id"] for row in rows)
    return {
        "generated_at": payload["generated_at"],
        "users": [
            {**row, "emp_nm": members.get(row["user_id"], {}).get("emp_nm")}
            for row in rows
        ],
    }


# Per-employee enumeration is admin-only; the aggregate views above
# (/me, /summary, /fabs) stay open to every identified user.
@bp.get("/activity/users")
@require_admin
def activity_users():
    return _query(_named_users_list)


@bp.get("/activity/users/<user_id>")
@require_admin
def activity_user_detail(user_id: str):
    return _query(
        lambda: get_user_history(user_id),
        not_found=f"no activity for user {user_id!r}",
    )


# Deliberately NOT under /api/activity: that prefix is in _OPERATION_PREFIXES,
# so nesting the beacon there would classify every page view as weight 0.
#
# The handler does no work. Its entire purpose is to exist so the after_request
# middleware logs a row, which is what carries the page view to OpenSearch at
# the office and to the mock store at home — no new store, and no office write
# path, which no office_example.py in this repo has.
@bp.post("/page-view")
def page_view():
    payload = request.get_json(silent=True)
    path = payload.get("path") if isinstance(payload, dict) else None
    if not isinstance(path, str) or not path.strip():
        return error_json("bad_request", "path is required", 400)
    slug = page_to_feature(path)
    if slug:
        # Imported here, not at module load: _logging.activity imports
        # ..activity.data, which back_dev_home/activity/__init__.py pulls in
        # via this very routes module, so a top-level import here is
        # circular. By request time every module is fully initialized.
        from .._logging.activity import promote_page_view

        promote_page_view(slug)
    # An unresolvable path (ops page, tab not yet in the URL) is still a 204:
    # the client cannot know which paths rank, and a 400 would be console noise
    # for something that is not an error.
    return "", 204
