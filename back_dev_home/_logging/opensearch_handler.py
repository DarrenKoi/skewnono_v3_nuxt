"""Buffered OpenSearch logging handler used in production mode.

Each log record is converted to a JSON document and pushed onto an in-memory
queue. A daemon thread drains the queue in batches via `ops_store.OSDoc.bulk`,
so request handling never blocks on OpenSearch. If OpenSearch is unreachable,
records are dropped (or the queue fills and new records are dropped) — the
Flask request path must never fail because of a log shipping outage.

The handler writes to the `skewnono_logging` write/search alias provisioned
by `ops_index_mgmt/skewnono_logging.py`.
"""

import atexit
import logging
import os
import queue
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

DEFAULT_INDEX = "skewnono_logging"
DEFAULT_BUFFER_SIZE = 100
DEFAULT_FLUSH_INTERVAL = 5.0
DEFAULT_QUEUE_SIZE = 10_000

# Extras we promote into typed top-level fields. Anything else passed via
# `logger.info(..., extra={...})` is ignored — keep mappings predictable.
_KNOWN_EXTRA_KEYS = (
    "event",
    "user_id",
    "request_id",
    "method",
    "path",
    "status",
    "latency_ms",
    "remote_addr",
)


class OpenSearchBulkHandler(logging.Handler):
    """Logging handler that bulk-indexes records into an OpenSearch alias."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any],
        index: str = DEFAULT_INDEX,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        host: str | None = None,
        level: int = logging.INFO,
    ) -> None:
        super().__init__(level=level)
        self._client_factory = client_factory
        self._index = index
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._host = host or socket.gethostname()
        self._queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._stopped = threading.Event()
        self._doc_service: Any = None
        self._worker = threading.Thread(
            target=self._run, name="skewnono-os-log", daemon=True
        )
        self._worker.start()
        atexit.register(self.close)

    # -- logging.Handler API ------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        try:
            doc = self._record_to_doc(record)
        except Exception:  # noqa: BLE001 - logging must never raise
            self.handleError(record)
            return
        try:
            self._queue.put_nowait(doc)
        except queue.Full:
            # Drop silently. An OpenSearch outage must not back-pressure
            # the Flask request thread.
            pass

    def close(self) -> None:
        if self._stopped.is_set():
            return
        self._stopped.set()
        leftovers: list[dict[str, Any]] = []
        while True:
            try:
                leftovers.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if leftovers:
            self._flush(leftovers)
        super().close()

    # -- internals ----------------------------------------------------

    def _record_to_doc(self, record: logging.LogRecord) -> dict[str, Any]:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        doc: dict[str, Any] = {
            "@timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "host": self._host,
        }
        for key in _KNOWN_EXTRA_KEYS:
            val = getattr(record, key, None)
            if val is not None:
                doc[key] = val
        if record.exc_info:
            exc_type, exc, _tb = record.exc_info
            doc["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": str(exc) if exc else None,
                "stack": logging.Formatter().formatException(record.exc_info),
            }
        return doc

    def _run(self) -> None:
        while not self._stopped.is_set():
            batch = self._collect_batch()
            if batch:
                self._flush(batch)

    def _collect_batch(self) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        deadline = time.monotonic() + self._flush_interval
        while len(batch) < self._buffer_size:
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                break
            try:
                batch.append(self._queue.get(timeout=timeout))
            except queue.Empty:
                break
        return batch

    def _flush(self, items: list[dict[str, Any]]) -> None:
        try:
            doc_service = self._ensure_doc_service()
            actions = (
                {"_index": self._index, "_source": item} for item in items
            )
            doc_service.bulk(actions, refresh=False, raise_on_error=False)
        except Exception as exc:  # noqa: BLE001 - never propagate
            sys.stderr.write(f"[opensearch-log] flush failed: {exc!r}\n")
            # Force reconnect on next flush; transient outages recover.
            self._doc_service = None

    def _ensure_doc_service(self) -> Any:
        if self._doc_service is None:
            from ops_store import OSDoc

            client = self._client_factory()
            self._doc_service = OSDoc(client=client, index=self._index)
        return self._doc_service


def install_opensearch_logging(
    *,
    index: str = DEFAULT_INDEX,
    level: int = logging.INFO,
    extra_logger_names: tuple[str, ...] = ("skewnono.activity",),
) -> OpenSearchBulkHandler | None:
    """Attach an `OpenSearchBulkHandler` to root + selected named loggers.

    Returns the handler, or `None` if OpenSearch credentials are missing in
    the environment. Idempotent — calling twice does not double-attach.
    """

    if os.environ.get("OPENSEARCH_LOGGING_DISABLED", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        return None

    if not os.environ.get("OPENSEARCH_PASSWORD"):
        sys.stderr.write(
            "[opensearch-log] OPENSEARCH_PASSWORD not set; "
            "skipping OpenSearch log handler.\n"
        )
        return None

    def _factory() -> Any:
        from ops_store import create_client

        # `create_client()` falls back to `OSConfig.from_env()` when no
        # explicit kwargs are passed, so OPENSEARCH_HOST / USER / PASSWORD
        # in the production env drive the connection.
        return create_client()

    handler = OpenSearchBulkHandler(
        client_factory=_factory,
        index=index,
        level=level,
    )

    root = logging.getLogger()
    if not _has_handler(root, OpenSearchBulkHandler):
        root.addHandler(handler)
        if root.level == logging.NOTSET or root.level > level:
            root.setLevel(level)

    # `skewnono.activity` is configured with `propagate=False`, so it would
    # otherwise miss the root handler. Attach explicitly.
    for name in extra_logger_names:
        sub = logging.getLogger(name)
        if not _has_handler(sub, OpenSearchBulkHandler):
            sub.addHandler(handler)

    return handler


def _has_handler(logger_obj: logging.Logger, handler_cls: type) -> bool:
    return any(isinstance(h, handler_cls) for h in logger_obj.handlers)
