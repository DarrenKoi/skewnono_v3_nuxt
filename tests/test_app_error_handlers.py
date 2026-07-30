"""The app factory's JSON error handlers.

Driven against a purpose-built Flask app with only
``_install_json_error_handlers`` applied, rather than ``create_app``: the point
under test is the handler table itself, not blueprint discovery, and isolating
it keeps these tests free of identity, rate-limit and logging setup.

Why this file exists: the handler table had no test coverage at all, and three
office adapters now reason explicitly about which exception becomes which
status. The rules it encodes are:

* bare ``LookupError``  -> 502, an adapter saying "the upstream data is bad"
* bare ``RuntimeError`` -> 503, an adapter saying "the backend is unreachable
  or unconfigured"
* a SUBCLASS of either -> 500, because those are programming bugs, not adapter
  signals (``KeyError``, ``NotImplementedError``, ``StoreUnavailableError``, ...)
* driver connection failures -> 503
* anything else -> a JSON 500

That last rule needs no catch-all handler and does not have one: Flask wraps an
unhandled exception in ``InternalServerError``, which IS an ``HTTPException``,
so the ``HTTPException`` handler above serves it as JSON and the traceback goes
to the log rather than to the client. These tests pin that down, because it is
load-bearing and entirely implicit — nothing in the factory says so.

The consequence the office adapters have to work around: an exception that is a
genuine outage but not one of the two registered driver types (a redis
``ResponseError``, a bare ``OSError``) lands in that last rule and reads as
"we have a bug" (500) rather than "infrastructure is down, retry" (503). Which
is why adapters convert their own outages to the bare-``RuntimeError`` signal
instead of letting driver exceptions escape.
"""

import json

import pytest
import redis
from flask import Flask

from back_dev_home import _install_json_error_handlers


def _client(exc: BaseException):
    """A client whose one route raises ``exc``."""
    app = Flask(__name__)
    _install_json_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise exc

    app.config["PROPAGATE_EXCEPTIONS"] = False
    return app.test_client()


def _body(response) -> dict:
    """Parse the body as JSON, failing loudly if it is an HTML error page."""
    raw = response.get_data(as_text=True)
    try:
        return json.loads(raw)
    except ValueError:  # pragma: no cover - only on regression
        pytest.fail(
            f"expected a JSON error body, got {response.content_type}: {raw[:200]!r}"
        )


# ── adapter signals: the exact base types ───────────────────────────────


def test_bare_lookup_error_is_a_502_upstream_data_error():
    response = _client(LookupError("bad parquet")).get("/boom")

    assert response.status_code == 502
    assert _body(response)["error"]["code"] == "upstream_data_error"


def test_bare_runtime_error_is_a_503_backend_unavailable():
    response = _client(RuntimeError("REDIS_HOST is not set")).get("/boom")

    assert response.status_code == 503
    assert _body(response)["error"]["code"] == "backend_unavailable"


def test_the_runtime_error_message_reaches_the_client():
    """The message is the actionable part — an operator reads it to learn which
    env var is missing."""
    response = _client(RuntimeError("REDIS_HOST is not set")).get("/boom")

    assert "REDIS_HOST" in _body(response)["error"]["message"]


# ── subclasses are bugs, not signals ────────────────────────────────────


def test_a_runtime_error_subclass_is_a_500_not_a_503():
    """access_control's StoreUnavailableError subclasses RuntimeError. It is
    only ever safe because routes.py catches it first; if one escapes, it must
    read as the bug it is rather than as a routine backend outage."""

    class StoreUnavailableError(RuntimeError):
        pass

    assert _client(StoreUnavailableError("x")).get("/boom").status_code == 500


def test_a_lookup_error_subclass_is_a_500_not_a_502():
    assert _client(KeyError("missing")).get("/boom").status_code == 500


# ── driver connection failures ──────────────────────────────────────────


def test_redis_connection_error_is_a_503_backend_unreachable():
    response = _client(redis.exceptions.ConnectionError("refused")).get("/boom")

    assert response.status_code == 503
    assert _body(response)["error"]["code"] == "backend_unreachable"


def test_redis_timeout_is_a_503_backend_unreachable():
    assert (
        _client(redis.exceptions.TimeoutError("slow")).get("/boom").status_code == 503
    )


# ── the implicit safety net: unhandled still answers in JSON ────────────


def test_a_redis_response_error_answers_in_json_but_as_a_500_not_a_503():
    """WRONGTYPE and friends subclass RedisError, NOT ConnectionError, so they
    match none of the driver handlers and fall through to InternalServerError.

    The body is still JSON, but the status says "bug" rather than "outage" —
    which is exactly why an adapter must not let a raw driver exception escape
    when it knows the cause is an outage."""
    response = _client(redis.exceptions.ResponseError("WRONGTYPE")).get("/boom")

    assert response.status_code == 500
    assert _body(response)["error"]["code"] == "internal_server_error"


def test_a_bare_os_error_answers_in_json_but_as_a_500_not_a_503():
    """redis-py lets socket-level failures through unwrapped, and redis's own
    ConnectionError does not subclass OSError, so these reach no driver
    handler either."""
    response = _client(OSError("socket gone")).get("/boom")

    assert response.status_code == 500
    assert _body(response)["error"]["code"] == "internal_server_error"


def test_an_arbitrary_exception_still_answers_in_json():
    response = _client(ValueError("anything at all")).get("/boom")

    assert response.status_code == 500
    assert _body(response)["error"]["code"] == "internal_server_error"


def test_an_unhandled_exception_never_leaks_its_message():
    """A 500 is a bug, and its detail may quote internal state or a secret. The
    traceback goes to the log; the client gets a fixed string."""
    response = _client(ValueError("password=hunter2")).get("/boom")

    assert "hunter2" not in response.get_data(as_text=True)


# ── ordinary HTTP errors are unaffected ─────────────────────────────────


def test_an_unknown_route_is_still_a_404():
    """The InternalServerError path must not have swallowed ordinary HTTP
    errors: a missing route is still a 404, not a 500."""
    response = _client(ValueError("unused")).get("/no-such-route")

    assert response.status_code == 404
    assert _body(response)["error"]["code"] == "not_found"


def test_a_wrong_method_is_still_a_405():
    response = _client(ValueError("unused")).post("/boom")

    assert response.status_code == 405
