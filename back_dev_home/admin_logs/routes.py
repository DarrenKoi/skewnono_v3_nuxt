import logging

from flask import Blueprint, jsonify, request

from back_dev_home._auth.errors import error_json

from .data import query_logs

bp = Blueprint("admin_logs", __name__)
logger = logging.getLogger("skewnono.admin_logs")


@bp.get("/admin/logs")
def admin_logs():
    try:
        return jsonify(query_logs(request.args))
    except ValueError as exc:
        return error_json("invalid_log_query", str(exc), 400)
    except Exception as exc:  # noqa: BLE001 - admin view must fail closed.
        logger.exception("Failed to query OpenSearch logs")
        return error_json(
            "log_query_failed",
            f"Could not query OpenSearch logs: {exc}",
            503,
        )
