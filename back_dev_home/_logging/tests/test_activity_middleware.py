"""Per-request activity logging and the usage-event tap.

``install_activity_logging`` does two jobs on every request: it emits the log
line an operator reads, and it decides whether the request becomes a usage
event. The second one writes to the dashboard's own store, so what it declines
to record matters as much as what it records.

The tests drive a purpose-built Flask app rather than ``create_app`` — the app
factory installs identity, CORS, rate limiting and every blueprint, none of
which this middleware depends on. ``record_request`` is stubbed because the
mock adapter keeps process-global counters that would leak between tests.
"""

import logging

import pytest
from flask import Flask, abort, g

from back_dev_home._logging import activity as activity_mod


@pytest.fixture
def records():
    """Records captured on skewnono.activity itself.

    The logger sets propagate=False, so caplog — a root-logger handler — never
    sees any of this. The sink is attached by `make_app` *after* installation,
    because install only configures the level when it finds no handlers.
    """
    return []


@pytest.fixture
def recorded(monkeypatch):
    """Every record_request call the middleware makes."""
    calls: list[tuple] = []
    monkeypatch.setattr(activity_mod, "record_request", lambda *a: calls.append(a))
    return calls


@pytest.fixture
def make_app(monkeypatch, preserve_logger, records, recorded):
    """Factory: an app with the middleware installed in network-free mode.

    `identity` is what install_identity_middleware would have put on `g`; pass
    api_token_id to stand in for a token-authenticated caller.

    The logger is reset to its just-imported state first: any earlier test that
    built a real app has already configured it process-wide, and install() is a
    no-op once handlers exist — without this the suite order would decide
    whether INFO records are emitted at all.
    """
    monkeypatch.setattr(activity_mod, "install_opensearch_logging", lambda: None)
    logger = preserve_logger("skewnono.activity")
    logger.handlers[:] = []
    logger.setLevel(logging.NOTSET)
    logger.propagate = True

    class _Sink(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    def build(*, early_status=None, **identity):
        app = Flask(__name__)

        @app.before_request
        def _identity():
            for key, value in identity.items():
                setattr(g, key, value)
            if early_status is not None:
                return "IDENTITY REJECTED", early_status

        @app.get("/api/sem-list")
        def _ok():
            return {"rows": []}

        @app.get("/api/cdsem/ppid-unavailable")
        def _side_panel():
            return {"ppids": []}

        @app.get("/api/cdsem/live-alarm")
        def _live_alarm():
            return {"alarms": []}

        @app.get("/api/nope")
        def _missing():
            abort(404)

        @app.get("/api/boom")
        def _boom():
            raise RuntimeError("kaboom")

        @app.get("/login")
        def _login():
            return "LOGIN"

        @app.get("/_nuxt/<name>")
        def _bundle(name):
            # Stands in for _spa/serving.py's found-a-real-file branch, which
            # only ever runs on the cloud host. Spelled literally, like
            # activity.py's own read, so this test needs no _spa import.
            g._spa_static_file = True
            return "BUNDLE"

        @app.get("/deep/link")
        def _index_fallback():
            # The other SPA branch: answered with index.html, flag NOT set.
            return "INDEX"

        activity_mod.install_activity_logging(app)
        logger.addHandler(_Sink())
        return app.test_client()

    return build


def _only(records: list[logging.LogRecord], event: str) -> logging.LogRecord:
    matching = [r for r in records if getattr(r, "event", None) == event]
    assert len(matching) == 1, [getattr(r, "event", None) for r in records]
    return matching[0]


def test_a_request_is_logged_with_the_fields_the_dashboard_reads(make_app, records):
    """These extras are the typed top-level fields OpenSearchBulkHandler
    promotes; anything missing here is a null column in usage_events."""
    client = make_app(user_id="2067928")

    client.get("/api/sem-list?fab_name=M16")

    record = _only(records, "request")
    assert record.levelno == logging.INFO
    assert record.user_id == "2067928"
    assert record.method == "GET"
    assert record.path == "/api/sem-list"
    assert not hasattr(record, "request_path")
    assert record.query_string == "fab_name=M16"
    assert record.status == 200
    assert record.feature == "sem_list"
    assert record.latency_ms >= 0
    assert record.remote_addr
    assert record.error_code is None
    assert record.error_name is None
    assert record.request_id
    assert record.activity_kind == "entry"
    assert record.activity_weight == 1
    assert record.fab_name_list == ["M16"]


def test_multi_fab_query_is_normalized(make_app, records):
    client = make_app(user_id="2067928")
    client.get("/api/cdsem/ppid-unavailable?fab_name=M14,m16,M14")
    assert _only(records, "request").fab_name_list == ["M14", "M16"]


def test_sensitive_query_values_are_redacted(make_app, records):
    client = make_app(user_id="2067928")
    client.get("/api/sem-list?fab_name=M14&access_token=secret")
    query = _only(records, "request").query_string
    assert "secret" not in query
    assert "%5BREDACTED%5D" in query


def test_background_poll_is_logged_but_not_recorded(make_app, records, recorded):
    client = make_app(user_id="2067928")
    client.get("/api/cdsem/live-alarm?fab_name=M14")
    record = _only(records, "request")
    assert (record.activity_kind, record.activity_weight) == ("background", 0)
    assert recorded == []


def test_the_level_tracks_the_status_class(make_app, records):
    """An operator greps the log by level: 5xx is a page, 4xx is a client
    mistake, 2xx is traffic. Logging them all at INFO hides outages."""
    client = make_app(user_id="2067928")

    client.get("/api/sem-list")
    client.get("/api/nope")
    client.get("/api/boom")

    by_status = {r.status: r.levelno for r in records if r.event == "request"}
    assert by_status[200] == logging.INFO
    assert by_status[404] == logging.WARNING
    assert by_status[500] == logging.ERROR


def test_an_error_status_is_labelled_with_its_reason_phrase(make_app, records):
    client = make_app(user_id="2067928")

    client.get("/api/nope")

    record = _only(records, "request")
    assert record.error_code == "404"
    assert record.error_name == "Not Found"


def test_only_weighted_requests_become_usage_events(make_app, recorded):
    client = make_app(user_id="2067928")

    client.get("/api/sem-list?fab_name=M16")
    client.get("/api/nope")
    client.get("/login")

    assert recorded == [
        (
            "2067928",
            "GET",
            "/api/sem-list",
            200,
            "sem_list",
            "entry",
            ["M16"],
        )
    ]


def test_a_cors_preflight_is_logged_but_not_recorded(make_app, records, recorded):
    """Browsers send OPTIONS preflights without cookies, so at home they carry
    the fallback admin identity; counting them would inflate DAU and feature
    usage with traffic no human initiated."""
    client = make_app(user_id="local-dev")

    client.options("/api/sem-list")

    record = _only(records, "request")
    assert (record.activity_kind, record.activity_weight) == ("operation", 0)
    assert recorded == []


def test_an_anonymous_request_is_logged_but_not_recorded(make_app, records, recorded):
    client = make_app()  # no g.user_id, as before identity middleware resolves one

    client.get("/api/sem-list")

    assert _only(records, "request").user_id is None
    assert recorded == []


def test_early_identity_response_gets_request_id_and_operation_semantics(
    make_app, records, recorded
):
    """A before_request gate (rate limiter, blocked user) that answers before
    _stamp_start still produces a log document; it must carry a correlation id
    and never count as activity."""
    client = make_app(user_id="2067928", early_status=403)

    assert client.get("/api/sem-list").status_code == 403

    record = _only(records, "request")
    assert record.request_id
    assert (record.activity_kind, record.activity_weight) == ("operation", 0)
    assert recorded == []


def test_token_calls_are_logged_but_never_scored(make_app, records, recorded):
    """API-token traffic is automation. It stays in the log for auditing, but a
    nightly script must not outrank a human page in the usage dashboard."""
    client = make_app(user_id="2067928", api_token_id="tok_1")

    client.get("/api/sem-list")

    record = _only(records, "request")
    assert record.api_token_id == "tok_1"
    assert record.activity_weight == 0
    assert recorded == []


def test_the_middleware_shares_one_feature_computation_with_the_writer(
    make_app, records, recorded
):
    """The log line and the usage event must agree on the slug, or the two
    stores disagree about the same request."""
    client = make_app(user_id="2067928")

    client.get("/api/cdsem/ppid-unavailable")

    assert _only(records, "request").feature == "storage"
    assert recorded[0][4] == "storage"


def test_an_unhandled_exception_is_logged_with_its_traceback(make_app, records):
    """got_request_exception fires before the 500 response exists, so this is
    the only record that carries the stack. Losing it leaves an error_code of
    "500" and no way to find the raising line."""
    client = make_app(user_id="2067928")

    assert client.get("/api/boom").status_code == 500

    exception_record = _only(records, "request_exception")
    request_record = _only(records, "request")
    assert exception_record.levelno == logging.ERROR
    assert exception_record.status == 500
    assert exception_record.error_code == "RuntimeError"
    assert exception_record.error_name == "kaboom"
    assert exception_record.exc_info and exception_record.exc_info[0] is RuntimeError
    assert exception_record.request_id
    assert exception_record.request_id == request_record.request_id


def test_installing_twice_does_not_duplicate_the_handler(make_app):
    """Two apps in one process (the test suite itself does this) must not turn
    every request into two log lines."""
    logger = logging.getLogger("skewnono.activity")
    make_app()
    installed = [h for h in logger.handlers if type(h) is logging.StreamHandler]
    make_app()

    assert [h for h in logger.handlers if type(h) is logging.StreamHandler] == installed
    assert logger.level == logging.INFO
    assert logger.propagate is False


def test_install_always_delegates_shipping_decision(monkeypatch, preserve_logger):
    preserve_logger("skewnono.activity")
    installs: list[int] = []
    monkeypatch.setattr(
        activity_mod, "install_opensearch_logging", lambda: installs.append(1)
    )

    activity_mod.install_activity_logging(Flask(__name__))
    assert len(installs) == 1


def test_a_static_file_from_the_spa_mount_is_not_logged_at_all(
    make_app, records, recorded
):
    """Phase 3 only: on the cloud host Flask serves the built SPA, so one cold
    page load is 50-100+ bundle, font and icon requests on top of the API
    calls. They carry no information the API calls do not, and would occupy
    the production index for its full 365-day retention.

    Nothing at all is emitted — not the OpenSearch document and not the
    stderr line — so the saving is index volume AND boot-log noise.
    """
    client = make_app(user_id="2067928")

    client.get("/_nuxt/entry.abc12345.js")

    assert records == []
    assert recorded == []


def test_the_index_html_fallback_is_still_logged(make_app, records):
    """The other half of the cut. Everything answered with index.html keeps
    logging: app boot, a deep-link reload, an unknown path, and — because the
    mount swallows NotFound into the same fallback — a missing asset after a
    bad deploy. Skipping by path prefix instead would have lost all four."""
    client = make_app(user_id="2067928")

    client.get("/deep/link")

    record = _only(records, "request")
    assert record.path == "/deep/link"
    assert record.status == 200


def test_the_skip_does_not_leak_into_the_next_request(make_app, records):
    """`g` is request-scoped, but the flag is read with a bare getattr default
    — assert a static request cannot suppress the API call that follows it on
    the same client."""
    client = make_app(user_id="2067928")

    client.get("/_nuxt/entry.abc12345.js")
    client.get("/api/sem-list?fab_name=M16")

    record = _only(records, "request")
    assert record.path == "/api/sem-list"
    assert record.activity_weight == 1
