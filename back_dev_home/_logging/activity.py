import logging
import time
from http import HTTPStatus

from flask import Flask, g, request
from flask.signals import got_request_exception

from .._runtime.env import is_cloud
from ..activity.data import _feature_of, record_request
from .opensearch_handler import install_opensearch_logging

logger = logging.getLogger("skewnono.activity")

_STATUS_PHRASE = {status.value: status.phrase for status in HTTPStatus}


def _activity_weight(user_id: str | None, path: str, status: int) -> int:
    if not user_id or user_id == "-":
        return 0
    if not path.startswith("/api/"):
        return 0
    if path.startswith("/api/activity/") or path.startswith("/api/admin/logs"):
        return 0
    if status >= 400:
        return 0
    return 1


def _status_error_name(status: int) -> str | None:
    if status < 400:
        return None
    return _STATUS_PHRASE.get(status, "HTTP error")


def _build_extra(*, event, status, ms, user_id, remote, error_code, error_name):
    path = request.path
    query_string = (
        request.query_string.decode("utf-8", errors="replace")
        if request.query_string
        else ""
    )
    return {
        "event": event,
        "user_id": str(user_id),
        "method": request.method,
        "path": path,
        "request_path": path,
        "query_string": query_string,
        "status": status,
        "latency_ms": ms,
        "remote_addr": remote,
        "feature": _feature_of(path),
        "activity_weight": _activity_weight(user_id, path, status),
        "error_code": error_code,
        "error_name": error_name,
    }


def install_activity_logging(app: Flask) -> None:
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    if is_cloud():
        install_opensearch_logging()

    @app.before_request
    def _stamp_start():
        g._activity_t0 = time.perf_counter()

    @app.after_request
    def _emit(response):
        t0 = getattr(g, "_activity_t0", None)
        ms = round((time.perf_counter() - t0) * 1000) if t0 else -1
        user_id = getattr(g, "user_id", "-")
        remote = request.remote_addr or "-"
        status = response.status_code
        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        logger.log(
            level,
            "user=%s method=%s path=%s status=%s ms=%s remote=%s",
            user_id,
            request.method,
            request.path,
            status,
            ms,
            remote,
            extra=_build_extra(
                event="request",
                status=status,
                ms=ms,
                user_id=user_id,
                remote=remote,
                error_code=str(status) if status >= 400 else None,
                error_name=_status_error_name(status),
            ),
        )
        record_request(user_id, request.method, request.path, status)
        return response

    def _emit_exception(_sender, exception, **_extra):
        t0 = getattr(g, "_activity_t0", None)
        ms = round((time.perf_counter() - t0) * 1000) if t0 else -1
        user_id = getattr(g, "user_id", "-")
        remote = request.remote_addr or "-"
        logger.error(
            "request exception user=%s method=%s path=%s ms=%s remote=%s error=%s",
            user_id,
            request.method,
            request.path,
            ms,
            remote,
            exception,
            exc_info=(type(exception), exception, exception.__traceback__),
            extra=_build_extra(
                event="request_exception",
                status=500,
                ms=ms,
                user_id=user_id,
                remote=remote,
                error_code=type(exception).__name__,
                error_name=str(exception),
            ),
        )

    got_request_exception.connect(_emit_exception, app, weak=False)
