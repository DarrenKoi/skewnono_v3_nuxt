import logging

from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.routing import RequestRedirect

from .._auth.admin import require_admin
from .._auth.directory import lookup_members
from .._auth.errors import error_json
from .._logging.feature_map import page_to_family, page_to_feature
from .contracts import NamedUserListResponse
from .data import (
    get_daily_visitors,
    get_endpoint_stats,
    get_fab_page_usage,
    get_family_page_usage,
    get_me,
    get_request_stats,
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


@bp.get("/activity/families")
def activity_families():
    return _query(get_family_page_usage)


def _named_users_list() -> NamedUserListResponse:
    """The users list with each employee number expanded into a person.

    The join lives here rather than in the providers because it is the same
    join on both sides of the swap: ``lookup_members`` decides for itself
    whether to dial office Redis or fabricate a home row, so neither
    ``mock.py`` nor ``office.py`` has anything to contribute. Putting it in the
    route also keeps the provider contract honest — the logging store records
    employee numbers and no names or teams, so ``UserListRow`` should not
    promise either.

    A directory that cannot answer costs the names and not the table:
    ``lookup_members`` never raises, and the joined fields are simply None.
    """
    payload = get_users_list()
    rows = payload["users"]
    members = lookup_members(row["user_id"] for row in rows)
    return {
        "generated_at": payload["generated_at"],
        "users": [
            {
                **row,
                # .get on both sides: the directory answers for every id it was
                # asked about, but a member row may be partial — a missing team
                # is not worth failing a table over.
                "emp_nm": members.get(row["user_id"], {}).get("emp_nm"),
                "dept_nm": members.get(row["user_id"], {}).get("dept_nm"),
            }
            for row in rows
        ],
    }


# Per-employee enumeration is admin-only; the aggregate views above
# (/me, /summary, /fabs, /families) stay open to every identified user.
@bp.get("/activity/users")
@require_admin
def activity_users():
    return _query(_named_users_list)


# An aggregate, but one the page offers to the administrator only: it is the
# site's traffic over time rather than a snapshot every user already sees.
@bp.get("/activity/visitors")
@require_admin
def activity_visitors():
    return _query(get_daily_visitors)


# Admin-only for the same reason as /visitors: the site's volume over time.
@bp.get("/activity/requests")
@require_admin
def activity_requests():
    return _query(get_request_stats)


#: Where a logged path that no /api rule answers is counted — a 404 probe,
#: a route since removed. One bucket, so stray paths cannot crowd the list.
UNMATCHED_ENDPOINT = "(미등록 경로)"


def _endpoint_of(adapter, call: str) -> str:
    """``"GET /api/hvsem/storage"`` → ``"GET /api/<tool_slug>/storage"``.

    Done here, not in the providers: the Flask url_map is the only thing
    that knows which raw paths are one endpoint, and both adapters hand over
    the same raw ``"<METHOD> <path>"`` keys.
    """
    method, _, path = call.partition(" ")
    try:
        rule, _args = adapter.match(path, method=method, return_rule=True)
    except RequestRedirect:
        # strict_slashes: /api/x/ is the /api/x rule. Fold it there.
        stripped = path.rstrip("/")
        if stripped == path:
            return UNMATCHED_ENDPOINT
        return _endpoint_of(adapter, f"{method} {stripped}")
    except HTTPException:
        return UNMATCHED_ENDPOINT
    # The cloud SPA catch-all answers every path; it is not an /api endpoint.
    if not rule.rule.startswith("/api/"):
        return UNMATCHED_ENDPOINT
    return f"{method} {rule.rule}"


def _endpoint_stats():
    payload = get_endpoint_stats()
    adapter = current_app.url_map.bind("localhost")
    endpoint_cache: dict[str, str] = {}
    days = []
    for day in payload["days"]:
        endpoints: dict[str, int] = {}
        for call, count in day["paths"].items():
            if call not in endpoint_cache:
                endpoint_cache[call] = _endpoint_of(adapter, call)
            name = endpoint_cache[call]
            endpoints[name] = endpoints.get(name, 0) + count
        days.append(
            {
                "date": day["date"],
                "requests": day["requests"],
                "endpoints": endpoints,
                "users": day["users"],
            }
        )
    members = lookup_members({uid for day in days for uid in day["users"]})
    return {
        "generated_at": payload["generated_at"],
        "truncated": payload["truncated"],
        "days": days,
        "names": {
            uid: {"emp_nm": member.get("emp_nm"), "dept_nm": member.get("dept_nm")}
            for uid, member in members.items()
        },
    }


# Admin-only: who calls what, per day. Every /api call, not just user intent.
@bp.get("/activity/endpoints")
@require_admin
def activity_endpoints():
    return _query(_endpoint_stats)


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
#
# The second rule is the same beacon for a page that belongs to a tool family
# (/api/page-view/cdsem). The family sits in the URL, not in a log field, so
# that it lands in the row's `path` — which the index already maps and the
# family card can therefore group on without any change to the index.
@bp.post("/page-view")
@bp.post("/page-view/<family>")
def page_view(family: str | None = None):
    payload = request.get_json(silent=True)
    path = payload.get("path") if isinstance(payload, dict) else None
    if not isinstance(path, str) or not path.strip():
        return error_json("bad_request", "path is required", 400)
    # The URL is what gets counted, so it has to be true. A page posted under
    # another family's URL — or under something that is not a family — is a
    # client bug; a 400 is never a usage event, so it is counted nowhere.
    # A family page posted to the PLAIN url is allowed: that is what a browser
    # still on the previous bundle sends, and it ranks without a family.
    if family is not None and family != page_to_family(path):
        return error_json(
            "bad_request", "family does not match the page", 400
        )
    slug = page_to_feature(path)
    if slug:
        # Imported here, not at module load: _logging.activity imports
        # ..activity.data, which backend/activity/__init__.py pulls in
        # via this very routes module, so a top-level import here is
        # circular. By request time every module is fully initialized.
        from .._logging.activity import promote_page_view

        promote_page_view(slug)
    # An unresolvable path (ops page, tab not yet in the URL) is still a 204:
    # the client cannot know which paths rank, and a 400 would be console noise
    # for something that is not an error.
    return "", 204
