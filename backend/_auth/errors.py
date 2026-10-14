from flask import g, has_request_context, jsonify


def error_json(code: str, message: str, status: int = 400):
    """The one JSON error shape, and the one place a handled error is noted.

    Every handled failure — HTTPException, the office adapters' LookupError /
    RuntimeError 502/503s, the driver connection errors — answers through
    here. Stashing ``(code, message)`` on ``g`` lets the activity middleware
    write the REASON into the request row's ``error_name``. Before 2026-10-14
    that row only said "Bad Gateway" and the reason lived in a separate
    ``app.logger.exception`` row with no request_id to join on, so an
    operator reading the logs from outside the office could see that 74
    recipe opens failed but not why.
    """
    if has_request_context():
        g._activity_error = (code, message)
    return jsonify({"error": {"code": code, "message": message}}), status
