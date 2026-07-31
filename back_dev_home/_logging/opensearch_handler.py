"""Buffered OpenSearch logging for office-local and production targets.

Each record becomes one bounded canonical document and enters an in-memory
queue. A daemon thread validates the configured rollover alias and bulk-indexes
with stable event IDs, so retries cannot duplicate activity. Logging failures
are observable through diagnostics but never propagate into Flask requests.
"""

import atexit
import logging
import os
import queue
import re
import socket
import sys
import threading
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4

from back_dev_home._logging.target import (
    LoggingConfigurationError,
    LoggingTarget,
    resolve_logging_target,
)

DEFAULT_INDEX = "skewnono_logging"
DEFAULT_BUFFER_SIZE = 100
DEFAULT_FLUSH_INTERVAL = 5.0
DEFAULT_QUEUE_SIZE = 10_000

_KNOWN_EXTRA_KEYS = (
    "event",
    "user_id",
    "identity_source",
    "api_token_id",
    "request_id",
    "method",
    "path",
    "query_string",
    "status",
    "latency_ms",
    "remote_addr",
    "feature",
    "activity_kind",
    "activity_weight",
    "fab_name_list",
    "error_code",
    "error_name",
)
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_RETRY_BACKOFFS = (0.5, 1.0)


class AliasNotReadyError(RuntimeError):
    """Raised when the configured write target is not a rollover alias."""


_NUMBERED_SUFFIX = re.compile(r".*-\d+$")


def rollover_write_index(index_service: Any, index: str) -> str | None:
    """Return the alias's numbered write index, or None if it is not usable.

    Reads the per-alias entry rather than ``describe()["is_alias"]`` or its
    ``rollover`` summary. Those two were wrong for every *existing* alias
    until ops_store was fixed: ``describe`` consulted ``exists_alias`` only
    when ``indices.exists`` had said False, but ``HEAD /<target>`` resolves
    aliases, so ``is_alias`` never left its ``False`` default and the rollover
    summary came back empty for a perfectly healthy alias. That blocked Flask
    boot at the office on 2026-07-28.

    Fixed upstream in flask_modules ``56cff99`` and synced into this repo's
    vendored copy, so ``describe()["rollover"]`` is now correct too. This stays
    because it gives the same answer against either version of ops_store, on
    the same two round trips -- worth keeping while home, office and cloud can
    be running vendored copies taken at different times.
    """
    if not index_service.alias_exists(index):
        return None
    summary = index_service.describe(index).get("aliases", {}).get(index, {})
    write_index = summary.get("write_index")
    if isinstance(write_index, str) and _NUMBERED_SUFFIX.fullmatch(write_index):
        return write_index
    return None


def _verify_rollover_alias(index_service: Any, index: str) -> None:
    if rollover_write_index(index_service, index) is None:
        raise AliasNotReadyError(
            f"{index} is not a ready numbered rollover alias; "
            "run ops_index_mgmt/skewnono_logging.py at the office"
        )


@dataclass(frozen=True)
class HandlerDiagnostics:
    enqueued: int
    indexed: int
    queue_full_dropped: int
    bulk_dropped: int
    retries: int
    bulk_failures: int
    last_success_at: str | None
    last_failure_at: str | None
    queue_depth: int

    @property
    def dropped(self) -> int:
        return self.queue_full_dropped + self.bulk_dropped

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "dropped": self.dropped}


def _bounded(value: Any, limit: int) -> str:
    return str(value)[:limit]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_index_service(client: Any, index: str) -> Any:
    from ops_store import OSIndex

    return OSIndex(client=client, index=index)


def _make_doc_service(client: Any, index: str) -> Any:
    from ops_store import OSDoc

    return OSDoc(client=client, index=index)


class OpenSearchBulkHandler(logging.Handler):
    """Bulk-index log records without blocking or failing the caller."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any],
        deployment: str,
        index: str = DEFAULT_INDEX,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        host: str | None = None,
        level: int = logging.INFO,
        uuid_factory: Callable[[], Any] = uuid4,
        sleep_fn: Callable[[float], None] = time.sleep,
        index_service_factory: Callable[[Any, str], Any] = _make_index_service,
        doc_service_factory: Callable[[Any, str], Any] = _make_doc_service,
    ) -> None:
        super().__init__(level=level)
        self._client_factory = client_factory
        self._deployment = deployment
        self._index = index
        self._buffer_size = buffer_size
        self._flush_interval = flush_interval
        self._host = host or socket.gethostname()
        self._uuid_factory = uuid_factory
        self._sleep_fn = sleep_fn
        self._index_service_factory = index_service_factory
        self._doc_service_factory = doc_service_factory
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=queue_size)
        self._stopped = threading.Event()
        self._close_lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self._client: Any = None
        self._doc_service: Any = None
        self._enqueued = 0
        self._indexed = 0
        self._queue_full_dropped = 0
        self._bulk_dropped = 0
        self._retries = 0
        self._bulk_failures = 0
        self._last_success_at: str | None = None
        self._last_failure_at: str | None = None
        self._last_report_at = float("-inf")
        self._worker = threading.Thread(
            target=self._run,
            name="skewnono-os-log",
            daemon=True,
        )
        self._worker.start()
        atexit.register(self.close)

    @property
    def index(self) -> str:
        return self._index

    @property
    def deployment(self) -> str:
        return self._deployment

    def snapshot(self) -> HandlerDiagnostics:
        with self._stats_lock:
            return HandlerDiagnostics(
                enqueued=self._enqueued,
                indexed=self._indexed,
                queue_full_dropped=self._queue_full_dropped,
                bulk_dropped=self._bulk_dropped,
                retries=self._retries,
                bulk_failures=self._bulk_failures,
                last_success_at=self._last_success_at,
                last_failure_at=self._last_failure_at,
                queue_depth=self._queue.qsize(),
            )

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
            self._record_failure(queue_full_dropped=1)
            self._report_failure("queue full")
        else:
            with self._stats_lock:
                self._enqueued += 1

    def close(self) -> None:
        with self._close_lock:
            if self._stopped.is_set():
                return
            self._stopped.set()
            if (
                hasattr(self, "_worker")
                and self._worker is not threading.current_thread()
            ):
                self._worker.join(timeout=2.0)
            leftovers = self._drain_queue()
            if leftovers:
                self._flush(leftovers)
            super().close()

    # -- document conversion -----------------------------------------

    def _record_to_doc(self, record: logging.LogRecord) -> dict[str, Any]:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        doc: dict[str, Any] = {
            "event_id": str(self._uuid_factory()),
            "@timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": _bounded(record.getMessage(), 4096),
            "service": "skewnono",
            "deployment": self._deployment,
            "host": self._host,
        }
        for key in _KNOWN_EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is None:
                continue
            doc[key] = _bounded(value, 1024) if key == "error_name" else value
        if record.exc_info:
            exc_type, exc, _tb = record.exc_info
            doc["exception"] = {
                "type": exc_type.__name__ if exc_type else None,
                "message": _bounded(exc, 4096) if exc else None,
                "stack": _bounded(
                    logging.Formatter().formatException(record.exc_info),
                    32_768,
                ),
            }
        return doc

    # -- worker lifecycle --------------------------------------------

    def _run(self) -> None:
        while not self._stopped.is_set():
            batch = self._collect_batch()
            if batch:
                self._flush(batch)

    def _collect_batch(self) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        deadline = time.monotonic() + self._flush_interval
        while len(batch) < self._buffer_size and not self._stopped.is_set():
            timeout = deadline - time.monotonic()
            if timeout <= 0:
                break
            try:
                batch.append(self._queue.get(timeout=min(timeout, 0.1)))
            except queue.Empty:
                continue
        return batch

    def _drain_queue(self) -> list[dict[str, Any]]:
        leftovers: list[dict[str, Any]] = []
        while True:
            try:
                leftovers.append(self._queue.get_nowait())
            except queue.Empty:
                return leftovers

    # -- OpenSearch delivery -----------------------------------------

    def _action(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "_op_type": "index",
            "_index": self._index,
            "_id": item["event_id"],
            "_source": item,
        }

    def _flush(self, items: list[dict[str, Any]]) -> None:
        pending = [self._action(item) for item in items]
        for attempt in range(3):
            try:
                doc_service = self._ensure_doc_service()
                success_count, errors = doc_service.bulk(
                    pending,
                    refresh=False,
                    raise_on_error=False,
                )
            except AliasNotReadyError as exc:
                self._record_failure(
                    bulk_dropped=len(pending),
                    bulk_failures=1,
                )
                self._reset_services()
                self._report_failure(str(exc))
                return
            except Exception as exc:  # noqa: BLE001 - never propagate
                self._record_failure(bulk_failures=1)
                self._reset_services()
                if attempt < len(_RETRY_BACKOFFS):
                    self._record_retry()
                    self._sleep_fn(_RETRY_BACKOFFS[attempt])
                    continue
                self._record_failure(bulk_dropped=len(pending))
                self._report_failure(repr(exc))
                return

            if success_count:
                with self._stats_lock:
                    self._indexed += success_count
                    self._last_success_at = _utc_now()
            if not errors:
                return

            self._record_failure(bulk_failures=1)
            pending_by_id = {action["_id"]: action for action in pending}
            retry_actions: list[dict[str, Any]] = []
            rejected = 0
            for error in errors:
                details = next(iter(error.values()), {})
                doc_id = details.get("_id")
                status = details.get("status")
                action = pending_by_id.get(doc_id)
                if action is not None and status in _RETRYABLE_STATUSES:
                    retry_actions.append(action)
                else:
                    rejected += 1
            if rejected:
                self._record_failure(bulk_dropped=rejected)
            if not retry_actions:
                self._report_failure("bulk item rejected")
                return
            if attempt >= len(_RETRY_BACKOFFS):
                self._record_failure(bulk_dropped=len(retry_actions))
                self._report_failure("retry budget exhausted")
                return

            pending = retry_actions
            self._record_retry()
            self._sleep_fn(_RETRY_BACKOFFS[attempt])

    def _ensure_doc_service(self) -> Any:
        if self._doc_service is not None:
            return self._doc_service

        client = self._client_factory()
        index_service = self._index_service_factory(client, self._index)
        _verify_rollover_alias(index_service, self._index)
        self._client = client
        self._doc_service = self._doc_service_factory(client, self._index)
        return self._doc_service

    def _reset_services(self) -> None:
        self._doc_service = None
        self._client = None

    # -- diagnostics --------------------------------------------------

    def _record_retry(self) -> None:
        with self._stats_lock:
            self._retries += 1

    def _record_failure(
        self,
        *,
        queue_full_dropped: int = 0,
        bulk_dropped: int = 0,
        bulk_failures: int = 0,
    ) -> None:
        with self._stats_lock:
            self._queue_full_dropped += queue_full_dropped
            self._bulk_dropped += bulk_dropped
            self._bulk_failures += bulk_failures
            self._last_failure_at = _utc_now()

    def _report_failure(self, reason: str) -> None:
        now = time.monotonic()
        with self._stats_lock:
            if now - self._last_report_at < 60:
                return
            self._last_report_at = now
        snapshot = self.snapshot()
        sys.stderr.write(
            "[opensearch-log] "
            f"dropped={snapshot.dropped} "
            f"retries={snapshot.retries} "
            f"failures={snapshot.bulk_failures} "
            f"queue={snapshot.queue_depth} "
            f"last={reason}\n"
        )


def _logging_disabled(values: Mapping[str, str]) -> bool:
    return values.get("OPENSEARCH_LOGGING_DISABLED", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _stderr(message: str) -> None:
    sys.stderr.write(f"[opensearch-log] {message}\n")


def _startup_preflight(handler: OpenSearchBulkHandler) -> None:
    """Warn at boot when the configured alias is unusable, without blocking.

    Runs off-thread with its own client so it can never delay startup or race
    the worker's cached services; the only side effect is a bounded stderr
    line.
    """
    client = None
    try:
        client = handler._client_factory()
        index_service = handler._index_service_factory(client, handler.index)
        _verify_rollover_alias(index_service, handler.index)
    except AliasNotReadyError as exc:
        _stderr(str(exc))
    except Exception as exc:  # noqa: BLE001 - preflight must never raise
        _stderr(f"cannot reach {handler.index} at startup: {type(exc).__name__}")
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            with suppress(Exception):
                close()


def install_opensearch_logging(
    *,
    target: LoggingTarget | None = None,
    level: int = logging.INFO,
    extra_logger_names: tuple[str, ...] = ("skewnono.activity",),
) -> OpenSearchBulkHandler | None:
    """Attach one target-matched handler to root and selected named loggers."""

    if _logging_disabled(os.environ):
        return None
    if not os.environ.get("OPENSEARCH_PASSWORD"):
        _stderr("OPENSEARCH_PASSWORD not set; skipping OpenSearch log handler")
        return None

    actual_target = target or resolve_logging_target()
    root = logging.getLogger()
    existing = _find_handler(root, OpenSearchBulkHandler)
    if existing is not None:
        if (
            existing.index != actual_target.alias
            or existing.deployment != actual_target.deployment
        ):
            raise LoggingConfigurationError(
                "existing OpenSearch logging target does not match "
                f"{actual_target.environment}"
            )
        handler = existing
    else:
        from ops_store import create_client

        handler = OpenSearchBulkHandler(
            client_factory=create_client,
            index=actual_target.alias,
            deployment=actual_target.deployment,
            level=level,
        )
        root.addHandler(handler)
        threading.Thread(
            target=_startup_preflight,
            args=(handler,),
            name="skewnono-os-log-preflight",
            daemon=True,
        ).start()

    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)

    for name in extra_logger_names:
        sub = logging.getLogger(name)
        if handler not in sub.handlers:
            sub.addHandler(handler)

    return handler


def _find_handler(
    logger_obj: logging.Logger,
    handler_cls: type,
) -> Any | None:
    return next(
        (handler for handler in logger_obj.handlers if isinstance(handler, handler_cls)),
        None,
    )


def installed_handler() -> OpenSearchBulkHandler | None:
    """The process-wide shipper install() attached to root, if any."""
    return _find_handler(logging.getLogger(), OpenSearchBulkHandler)
