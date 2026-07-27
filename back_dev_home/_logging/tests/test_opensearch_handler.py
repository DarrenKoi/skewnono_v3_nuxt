"""The environment-selected internal OpenSearch log shipper.

Every test replaces the network hop — ``_flush`` is overridden, or the
``client_factory`` is one that fails the test if anyone calls it. Nothing in
this file may dial OpenSearch.

The contract worth protecting is the negative one: log shipping runs on the
Flask request thread's doorstep, and an OpenSearch outage must cost dropped log
lines, never a failed request.
"""

import io
import logging
import sys
import time

import pytest

from back_dev_home._logging import opensearch_handler as osh
from back_dev_home._logging.opensearch_handler import OpenSearchBulkHandler


def _never_dial():
    raise AssertionError("the tests must never construct an OpenSearch client")


def _record(
    msg="hello %s",
    args=("world",),
    level=logging.INFO,
    message: str | None = None,
    **extra,
):
    actual_message = message if message is not None else msg
    actual_args = () if message is not None else args
    record = logging.LogRecord(
        name="skewnono.activity",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=actual_message,
        args=actual_args,
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class _Shipper(OpenSearchBulkHandler):
    """The real handler with the bulk call replaced by a list."""

    def __init__(self, **kwargs):
        self.flushed: list[dict] = []
        kwargs.setdefault("client_factory", _never_dial)
        kwargs.setdefault("deployment", "test")
        kwargs.setdefault("flush_interval", 0.01)
        kwargs.setdefault("host", "test-host")
        super().__init__(**kwargs)

    def _flush(self, items):
        self.flushed.extend(items)


class _ParkedShipper(_Shipper):
    """...and the drain thread parked, so the queue can be inspected."""

    def _run(self):
        self._stopped.wait()


@pytest.fixture
def shipper():
    handler = _Shipper()
    yield handler
    handler.close()


@pytest.fixture
def parked():
    handler = _ParkedShipper()
    yield handler
    handler.close()


def test_the_worker_thread_ships_what_emit_queues(shipper):
    """emit() only enqueues; a daemon thread does the batching. If that wiring
    breaks, nothing raises — the logs just silently stop arriving."""
    shipper.emit(_record())

    deadline = time.monotonic() + 2.0
    while not shipper.flushed and time.monotonic() < deadline:
        time.sleep(0.01)

    assert [doc["message"] for doc in shipper.flushed] == ["hello world"]


def test_a_document_carries_the_fields_the_index_template_maps(parked):
    doc = parked._record_to_doc(
        _record(
            user_id="2067928",
            feature="sem_list",
            status=200,
            latency_ms=12,
            activity_weight=1,
        )
    )

    assert doc["@timestamp"].endswith("+00:00")  # UTC, not the host's timezone
    assert doc["level"] == "INFO"
    assert doc["logger"] == "skewnono.activity"
    assert doc["message"] == "hello world"  # %-args rendered, not shipped raw
    assert doc["host"] == "test-host"
    assert doc["user_id"] == "2067928"
    assert doc["feature"] == "sem_list"
    assert doc["status"] == 200
    assert doc["latency_ms"] == 12
    assert doc["activity_weight"] == 1


def test_document_has_identity_environment_and_bounded_fields(parked):
    parked._deployment = "local"
    doc = parked._record_to_doc(
        _record(
            message="x" * 5000,
            request_id="req-1",
            activity_kind="entry",
            fab_name_list=["M14", "M16"],
            error_name="e" * 2000,
        )
    )
    assert doc["event_id"]
    assert doc["service"] == "skewnono"
    assert doc["deployment"] == "local"
    assert doc["request_id"] == "req-1"
    assert doc["activity_kind"] == "entry"
    assert doc["fab_name_list"] == ["M14", "M16"]
    assert len(doc["message"]) == 4096
    assert len(doc["error_name"]) == 1024


def test_unmapped_extras_are_dropped_and_absent_ones_omitted(parked):
    """Anything outside _KNOWN_EXTRA_KEYS would arrive as a dynamically mapped
    field, and one bad type there poisons the mapping for the whole index."""
    doc = parked._record_to_doc(
        _record(
            surprise={"nested": "thing"},
            authorization="Bearer secret",
            cookie="session=secret",
            request_body={"password": "secret"},
        )
    )

    assert "surprise" not in doc
    assert "authorization" not in doc
    assert "cookie" not in doc
    assert "request_body" not in doc
    assert "secret" not in repr(doc)
    assert "user_id" not in doc  # None extras never become null columns


def test_an_exception_record_ships_its_stack(parked):
    """The activity middleware's request_exception record is the only place a
    traceback exists; it has to survive the trip to the index."""
    try:
        raise RuntimeError("kaboom")
    except RuntimeError as exc:
        record = _record(level=logging.ERROR)
        record.exc_info = (type(exc), exc, exc.__traceback__)

    doc = parked._record_to_doc(record)

    assert doc["exception"]["type"] == "RuntimeError"
    assert doc["exception"]["message"] == "kaboom"
    assert "Traceback" in doc["exception"]["stack"]


def test_an_unformattable_record_is_dropped_not_raised(parked, monkeypatch):
    """logging must never raise into the caller: this record's args do not
    match its format string, which blows up inside getMessage(). The record is
    dropped, but handleError still says so on stderr — a silent drop here would
    mean losing log lines with nothing to notice.

    stderr is swapped by hand rather than read via capsys so the assertion
    holds under `pytest -s` too.
    """
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)

    parked.emit(_record(msg="%d items", args=("not-a-number",)))

    assert parked._queue.empty()
    assert parked.flushed == []
    assert "Logging error" in stderr.getvalue()


def test_full_queue_increments_drop_count_without_blocking():
    """The alternative is a blocking put on the Flask worker thread: an
    OpenSearch outage would then stall every request that logs."""
    handler = _ParkedShipper(queue_size=1)
    try:
        handler.emit(_record())
        handler.emit(_record())
        snapshot = handler.snapshot()
        assert snapshot.enqueued == 1
        assert snapshot.queue_full_dropped == 1
        assert snapshot.bulk_dropped == 0
        assert snapshot.dropped == 1
        assert snapshot.queue_depth == 1
    finally:
        handler.close()


def test_close_ships_the_leftovers_once(parked):
    """close() is the atexit hook. A uwsgi reload must not lose the buffer, and
    the second call (atexit after an explicit close) must be a no-op."""
    parked.emit(_record(msg="last words", args=()))

    parked.close()
    assert [doc["message"] for doc in parked.flushed] == ["last words"]

    parked.close()
    assert len(parked.flushed) == 1


def test_the_default_index_is_the_alias_ops_index_mgmt_provisions():
    """The handler writes to an alias it does not create. If these two names
    drift, production logging fails on every flush against an index that
    OpenSearch auto-creates with no template and no retention policy."""
    provisioning = pytest.importorskip("ops_index_mgmt.skewnono_logging")

    assert osh.DEFAULT_INDEX == provisioning.target_for("production").alias


# -- bulk preflight and retry ------------------------------------------------


class _ParkedBulkShipper(OpenSearchBulkHandler):
    def __init__(self, **kwargs):
        kwargs.setdefault("client_factory", lambda: object())
        kwargs.setdefault("deployment", "local")
        kwargs.setdefault("host", "test-host")
        super().__init__(**kwargs)

    def _run(self):
        self._stopped.wait()


class _BulkRecorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def bulk(self, actions, **_kwargs):
        self.calls.append(list(actions))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _IndexDescription:
    def __init__(self, description):
        self.description = description

    def describe(self, _index):
        return self.description


def _ready_index_factory(_client, _index):
    return _IndexDescription(
        {
            "is_alias": True,
            "rollover": {"ready": True, "uses_numbered_suffix": True},
        }
    )


def _plain_index_factory(_client, _index):
    return _IndexDescription(
        {
            "is_alias": False,
            "rollover": {"ready": False, "uses_numbered_suffix": False},
        }
    )


def test_bulk_actions_use_event_id_as_opensearch_id():
    docs = _BulkRecorder(responses=[(1, [])])
    handler = _ParkedBulkShipper(
        index_service_factory=_ready_index_factory,
        doc_service_factory=lambda _client, _index: docs,
    )
    try:
        doc = handler._record_to_doc(_record())
        handler._flush([doc])
        action = docs.calls[0][0]
        assert action["_id"] == doc["event_id"]
        assert action["_source"] == doc
    finally:
        handler.close()


def test_transport_failure_retries_twice_then_succeeds():
    docs = _BulkRecorder(
        responses=[ConnectionError("one"), ConnectionError("two"), (1, [])]
    )
    sleeps = []
    handler = _ParkedBulkShipper(
        index_service_factory=_ready_index_factory,
        doc_service_factory=lambda _client, _index: docs,
        sleep_fn=sleeps.append,
    )
    try:
        handler._flush([handler._record_to_doc(_record())])
        snapshot = handler.snapshot()
        assert sleeps == [0.5, 1.0]
        assert snapshot.indexed == 1
        assert snapshot.retries == 2
        assert snapshot.queue_full_dropped == 0
        assert snapshot.bulk_dropped == 0
        assert snapshot.dropped == 0
    finally:
        handler.close()


def test_non_rollover_alias_is_never_bulk_written():
    docs = _BulkRecorder(responses=[])
    handler = _ParkedBulkShipper(
        index_service_factory=_plain_index_factory,
        doc_service_factory=lambda _client, _index: docs,
    )
    try:
        handler._flush([handler._record_to_doc(_record())])
        snapshot = handler.snapshot()
        assert snapshot.indexed == 0
        assert snapshot.bulk_dropped == 1
        assert snapshot.dropped == 1
        assert docs.calls == []
    finally:
        handler.close()


def test_only_retryable_partial_failures_are_sent_again():
    handler = _ParkedBulkShipper(
        index_service_factory=_ready_index_factory,
        sleep_fn=lambda _seconds: None,
    )
    try:
        retry_doc = handler._record_to_doc(_record(message="retry"))
        reject_doc = handler._record_to_doc(_record(message="reject"))
        docs = _BulkRecorder(
            responses=[
                (
                    0,
                    [
                        {
                            "index": {
                                "_id": retry_doc["event_id"],
                                "status": 429,
                                "error": {"type": "too_many_requests"},
                            }
                        },
                        {
                            "index": {
                                "_id": reject_doc["event_id"],
                                "status": 400,
                                "error": {"type": "mapper_parsing_exception"},
                            }
                        },
                    ],
                ),
                (1, []),
            ]
        )
        handler._doc_service_factory = lambda _client, _index: docs

        handler._flush([retry_doc, reject_doc])

        assert [item["_id"] for item in docs.calls[1]] == [
            retry_doc["event_id"]
        ]
        snapshot = handler.snapshot()
        assert snapshot.indexed == 1
        assert snapshot.bulk_dropped == 1
        assert snapshot.retries == 1
    finally:
        handler.close()


# -- install_opensearch_logging ---------------------------------------------


class _StubHandler(logging.Handler):
    """Stands in for the real handler so install() starts no thread."""

    made: list["_StubHandler"] = []

    def __init__(self, **kwargs):
        super().__init__(level=kwargs.get("level", logging.INFO))
        self.kwargs = kwargs
        self.index = kwargs["index"]
        self.deployment = kwargs["deployment"]
        _StubHandler.made.append(self)

    def emit(self, record):  # pragma: no cover - never exercised
        pass


@pytest.fixture
def stub_handler(monkeypatch):
    _StubHandler.made = []
    monkeypatch.setattr(osh, "OpenSearchBulkHandler", _StubHandler)
    monkeypatch.setattr(osh, "_startup_preflight", lambda _handler: None)
    return _StubHandler


def test_no_credentials_means_no_handler_at_all(preserve_logger, stub_handler):
    """A cloud host booting before its OPENSEARCH_PASSWORD is set, and every
    non-cloud checkout that reaches this by accident: skip shipping and serve
    traffic rather than crash or retry a connection nobody configured."""
    root = preserve_logger("")
    preserve_logger("skewnono.activity")
    handlers_before = list(root.handlers)

    assert osh.install_opensearch_logging() is None
    assert stub_handler.made == []
    assert list(root.handlers) == handlers_before


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
def test_the_kill_switch_wins_over_a_configured_password(
    monkeypatch, preserve_logger, stub_handler, value
):
    """OPENSEARCH_LOGGING_DISABLED is the one lever an operator has on a live
    cloud host when the cluster is the thing that is broken."""
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "s3cret")
    monkeypatch.setenv("OPENSEARCH_LOGGING_DISABLED", value)
    preserve_logger("")
    preserve_logger("skewnono.activity")

    assert osh.install_opensearch_logging() is None
    assert stub_handler.made == []


def test_it_attaches_to_the_root_and_to_the_activity_logger(
    monkeypatch, preserve_logger, stub_handler
):
    """skewnono.activity sets propagate=False, so a root handler alone would
    ship everything EXCEPT the request records that are the point of the index.
    The explicit second attach is load-bearing."""
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "s3cret")
    monkeypatch.setenv("SKEWNONO_LOG_ENV", "local")
    root = preserve_logger("")
    activity = preserve_logger("skewnono.activity")

    handler = osh.install_opensearch_logging()

    assert handler in root.handlers
    assert handler in activity.handlers
    assert handler.kwargs["index"] == "skewnono_logging_local"
    assert handler.kwargs["deployment"] == "local"


def test_installing_twice_does_not_double_ship(
    monkeypatch, preserve_logger, stub_handler
):
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "s3cret")
    monkeypatch.setenv("SKEWNONO_LOG_ENV", "production")
    root = preserve_logger("")
    activity = preserve_logger("skewnono.activity")

    first = osh.install_opensearch_logging()
    second = osh.install_opensearch_logging()

    assert sum(isinstance(h, _StubHandler) for h in root.handlers) == 1
    assert sum(isinstance(h, _StubHandler) for h in activity.handlers) == 1
    assert first is second
    assert len(_StubHandler.made) == 1


def test_a_quiet_root_is_lowered_to_the_shipping_level(
    monkeypatch, preserve_logger, stub_handler
):
    """uwsgi leaves the root at WARNING; the index would then hold only errors."""
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "s3cret")
    monkeypatch.setenv("SKEWNONO_LOG_ENV", "production")
    root = preserve_logger("")
    preserve_logger("skewnono.activity")
    root.setLevel(logging.WARNING)

    osh.install_opensearch_logging()

    assert root.level == logging.INFO


def test_a_chattier_root_is_left_alone(monkeypatch, preserve_logger, stub_handler):
    """Someone debugging at DEBUG must not be quietly turned back down."""
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "s3cret")
    monkeypatch.setenv("SKEWNONO_LOG_ENV", "production")
    root = preserve_logger("")
    preserve_logger("skewnono.activity")
    root.setLevel(logging.DEBUG)

    osh.install_opensearch_logging()

    assert root.level == logging.DEBUG


def test_configured_password_without_target_fails_closed(
    monkeypatch, preserve_logger, stub_handler
):
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "s3cret")
    preserve_logger("")
    preserve_logger("skewnono.activity")

    with pytest.raises(osh.LoggingConfigurationError, match="SKEWNONO_LOG_ENV"):
        osh.install_opensearch_logging()

    assert stub_handler.made == []


def test_existing_handler_for_another_target_is_rejected(
    monkeypatch, preserve_logger, stub_handler
):
    monkeypatch.setenv("OPENSEARCH_PASSWORD", "s3cret")
    monkeypatch.setenv("SKEWNONO_LOG_ENV", "local")
    root = preserve_logger("")
    preserve_logger("skewnono.activity")
    root.addHandler(
        _StubHandler(
            index="skewnono_logging",
            deployment="production",
            level=logging.INFO,
        )
    )

    with pytest.raises(osh.LoggingConfigurationError, match="does not match"):
        osh.install_opensearch_logging()


# -- _startup_preflight ------------------------------------------------------


class _Describer:
    """Index-service fake whose describe() answer is fixed at construction."""

    def __init__(self, description):
        self._description = description

    def describe(self, _index):
        return self._description


def _preflight_stderr(monkeypatch, handler):
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    osh._startup_preflight(handler)
    return stderr.getvalue()


def _preflight_handler(description=None, client_factory=None):
    handler = _ParkedShipper(
        index="skewnono_logging_local",
        index_service_factory=lambda _client, _index: _Describer(description),
    )
    if client_factory is not None:
        handler._client_factory = client_factory
    else:
        handler._client_factory = lambda: object()
    return handler


def test_preflight_warns_when_the_alias_is_not_ready(monkeypatch):
    """The spec promises a startup warning, not a first-flush one: an operator
    who forgot the ops_index_mgmt run should learn it from the boot log, hours
    before the first request would have tried to ship."""
    handler = _preflight_handler(description={"is_alias": False})
    try:
        out = _preflight_stderr(monkeypatch, handler)
    finally:
        handler.close()

    assert "skewnono_logging_local is not a ready numbered rollover alias" in out


def test_preflight_is_silent_when_the_alias_is_ready(monkeypatch):
    handler = _preflight_handler(
        description={
            "is_alias": True,
            "rollover": {"ready": True, "uses_numbered_suffix": True},
        }
    )
    try:
        out = _preflight_stderr(monkeypatch, handler)
    finally:
        handler.close()

    assert out == ""


def test_preflight_bounds_a_connection_failure_to_its_type_name(monkeypatch):
    """No host, no credentials, no exception text — the boot log line must be
    safe to paste anywhere."""

    def _refuse():
        raise ConnectionError("opensearch://user:secret@10.0.0.1 refused")

    handler = _preflight_handler(client_factory=_refuse)
    try:
        out = _preflight_stderr(monkeypatch, handler)
    finally:
        handler.close()

    assert "cannot reach skewnono_logging_local at startup: ConnectionError" in out
    assert "secret" not in out
    assert "10.0.0.1" not in out

