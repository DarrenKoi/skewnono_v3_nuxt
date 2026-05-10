import logging
import time

from flask import Flask, g, request

from .._runtime.env import is_cloud
from ..activity.data import record_request
from .opensearch_handler import install_opensearch_logging

logger = logging.getLogger("skewnono.activity")


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
        logger.info(
            "user=%s method=%s path=%s status=%s ms=%s remote=%s",
            user_id,
            request.method,
            request.path,
            response.status_code,
            ms,
            remote,
            extra={
                "event": "request",
                "user_id": str(user_id),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "latency_ms": ms,
                "remote_addr": remote,
            },
        )
        record_request(user_id, request.method, request.path, response.status_code)
        return response
