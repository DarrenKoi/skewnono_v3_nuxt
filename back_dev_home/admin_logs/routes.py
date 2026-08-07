import logging

from flask import Blueprint, jsonify, request

from back_dev_home._auth.admin import require_admin
from back_dev_home._auth.directory import lookup_members
from back_dev_home._auth.errors import error_json

from .contracts import NamedLogQueryResponse
from .data import query_logs

bp = Blueprint("admin_logs", __name__)
logger = logging.getLogger("skewnono.admin_logs")


def _named_logs(params) -> NamedLogQueryResponse:
    """The log page with each employee number expanded into a name.

    The join lives here rather than in the providers because it is the same
    join on both sides of the swap: ``lookup_members`` decides for itself
    whether to dial office Redis or fabricate a home row, so neither
    ``mock.py`` nor ``office.py`` has anything to contribute.

    A directory that cannot answer costs the names and not the page:
    ``lookup_members`` never raises, and the map simply comes back empty.
    """
    payload = query_logs(params)
    members = lookup_members(
        item["user_id"] for item in payload["items"] if item.get("user_id")
    )
    return {
        **payload,
        # Only the ones that resolved. An id the directory could not name is
        # absent, not None — the caller shows the number either way.
        "members": {
            user_id: member["emp_nm"]
            for user_id, member in members.items()
            if member.get("emp_nm")
        },
    }


@bp.get("/admin/logs")
@require_admin
def admin_logs():
    try:
        return jsonify(_named_logs(request.args))
    except ValueError as exc:
        return error_json("invalid_log_query", str(exc), 400)
    except Exception:  # Admin view must fail closed without leaking details.
        logger.exception("Failed to query OpenSearch logs")
        return error_json(
            "log_query_failed",
            "Could not query OpenSearch logs",
            503,
        )
