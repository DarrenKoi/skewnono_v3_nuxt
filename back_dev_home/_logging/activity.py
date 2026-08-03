import logging
import time
from http import HTTPStatus
from uuid import uuid4

from flask import Flask, g, request
from flask.signals import got_request_exception

from ..activity.data import record_request
from .feature_map import route_to_feature
from .opensearch_handler import install_opensearch_logging
from .policy import (
    classify_activity,
    normalize_fab_name_list,
    sanitize_query_string,
)

logger = logging.getLogger("skewnono.activity")

# Debounce for _note_record_request_failure: a store outage fails every
# request, and one traceback per request would bury the log it reports to.
_RECORD_FAILURE_INTERVAL = 60.0
_record_failure_last = float("-inf")


def _note_record_request_failure() -> None:
    global _record_failure_last
    now = time.monotonic()
    if now - _record_failure_last < _RECORD_FAILURE_INTERVAL:
        return
    _record_failure_last = now
    logger.exception("record_request failed; usage rows are being dropped")


_STATUS_PHRASE = {status.value: status.phrase for status in HTTPStatus}


def _status_error_name(status: int) -> str | None:
    if status < 400:
        return None
    return _STATUS_PHRASE.get(status, "HTTP error")


def _request_id() -> str:
    # A before_request handler registered ahead of this middleware (rate
    # limiter, identity gate) can answer before _stamp_start runs; the log
    # document still needs a correlation id.
    request_id = getattr(g, "_activity_request_id", None)
    if not request_id:
        request_id = str(uuid4())
        g._activity_request_id = request_id
    return request_id


def promote_request_fab_names(*values: str | None) -> None:
    existing = getattr(g, "_activity_fab_name_list", [])
    g._activity_fab_name_list = normalize_fab_name_list([*existing, *values])


def promote_page_view(slug: str) -> None:
    """Declare which PAGE this request represents, overriding the path.

    The beacon's own path is /api/page-view, which says nothing about what
    the user opened. Same mechanism as promote_request_fab_names: the handler
    puts it on ``g``, the after_request middleware reads it.
    """
    g._activity_page_slug = slug


def _build_extra(
    *,
    event,
    status,
    ms,
    user_id,
    remote,
    feature,
    error_code,
    error_name,
):
    path = request.path
    fab_name_list = normalize_fab_name_list(
        [
            *request.args.getlist("fab_name"),
            *getattr(g, "_activity_fab_name_list", []),
        ]
    )
    decision = classify_activity(
        user_id=user_id,
        api_token_id=getattr(g, "api_token_id", None),
        method=request.method,
        path=path,
        status=status,
        feature=feature,
    )
    return {
        "event": event,
        "user_id": str(user_id) if user_id not in (None, "-") else None,
        # How we know who this is: token, cookie, declared, local, anonymous.
        # An `anonymous` row is only actionable when a self-declared identity
        # is distinguishable from an infrastructure-supplied one — a log that
        # merges them is exactly the silence self-identification removes.
        # Read defensively: paths that log before the identity chain has run
        # must record None rather than raise inside the logger, where an
        # exception costs the log line and the request carrying it.
        "identity_source": getattr(g, "identity_source", None),
        "api_token_id": getattr(g, "api_token_id", None),
        "request_id": _request_id(),
        "method": request.method,
        "path": path,
        "query_string": (
            sanitize_query_string(request.query_string)
            if request.query_string
            else ""
        ),
        "status": status,
        "latency_ms": ms,
        "remote_addr": remote,
        "feature": feature,
        "activity_kind": decision.kind,
        "activity_weight": decision.weight,
        "fab_name_list": fab_name_list,
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

    install_opensearch_logging()

    @app.before_request
    def _stamp_start():
        g._activity_t0 = time.perf_counter()
        _request_id()
        g._activity_fab_name_list = []

    @app.after_request
    def _emit(response):
        # Static files off the Phase 3 SPA mount are not activity. A cold load
        # is 50-100+ bundle, font and icon requests that say nothing the API
        # calls beside them do not, and on the cloud host they would sit in the
        # index for the full 365-day retention.
        #
        # `_spa/serving.py` sets this ONLY when it served a real file, so the
        # index.html fallback still logs — that covers app boot, a deep-link
        # reload, and an unknown path. A *missing* asset takes the fallback
        # too (send_from_directory raises NotFound, which the mount swallows),
        # so nothing that could indicate a broken deploy is dropped here. The
        # flag is only ever set on cloud, where register_spa is mounted.
        if getattr(g, "_spa_static_file", False):
            return response

        t0 = getattr(g, "_activity_t0", None)
        ms = round((time.perf_counter() - t0) * 1000) if t0 else -1
        user_id = getattr(g, "user_id", None)
        remote = request.remote_addr or "-"
        status = response.status_code
        path = request.path
        feature = getattr(g, "_activity_page_slug", None) or route_to_feature(path)
        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        extra = _build_extra(
            event="request",
            status=status,
            ms=ms,
            user_id=user_id,
            remote=remote,
            feature=feature,
            error_code=str(status) if status >= 400 else None,
            error_name=_status_error_name(status),
        )
        logger.log(
            level,
            "user=%s method=%s path=%s status=%s ms=%s remote=%s",
            user_id or "-",
            request.method,
            path,
            status,
            ms,
            remote,
            extra=extra,
        )
        if extra["activity_weight"] == 1:
            # The usage store is a swap surface: the mock is in-memory, but an
            # office adapter doing real I/O turns a backing-store blip into a
            # 500 on a response that already succeeded. A failure here costs
            # the usage row, never the request.
            try:
                record_request(
                    user_id,
                    feature,
                    extra["activity_kind"],
                    extra["fab_name_list"],
                )
            except Exception:
                _note_record_request_failure()
        return response

    def _emit_exception(_sender, exception, **_extra):
        t0 = getattr(g, "_activity_t0", None)
        ms = round((time.perf_counter() - t0) * 1000) if t0 else -1
        user_id = getattr(g, "user_id", None)
        remote = request.remote_addr or "-"
        logger.error(
            "request exception user=%s method=%s path=%s ms=%s remote=%s error=%s",
            user_id or "-",
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
                feature=route_to_feature(request.path),
                error_code=type(exception).__name__,
                error_name=str(exception),
            ),
        )

    got_request_exception.connect(_emit_exception, app, weak=False)
