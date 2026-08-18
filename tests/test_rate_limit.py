"""The /api rate limit: one app-wide budget per caller.

Three contracts pinned here, each of which has silently not held before:

- The budget is application-wide, not per-route. ``default_limits`` gives every
  route its own window, so a runaway loop rotating across N endpoints ran at
  N x 50 req/5s and never 429'd — while CLAUDE.md documented a single shared
  budget. ``application_limits`` is what makes the documented contract real
  (and what makes ``application_limits_exempt_when`` meaningful at all).

- Anonymous callers do not share a bucket. Every cookie-less cloud caller
  carries the literal `anonymous` id; keyed on it, a proxy config that strips
  LASTUSER would pool the whole fab into one 50-req budget and the app would
  drown in 429s on first paint.

- Storage follows mode. memory:// counters are per-process (50 per *worker*
  under Phase 3 uwsgi); office mode points at the shared Redis instead, with
  the in-memory fallback so an unreachable Redis degrades rather than fails.

``load_dotenv`` is neutralized as in test_app_factory_session.py, and the mode
is pinned to mock so an office run of this suite cannot leak LIMITER keys into
the real Redis.
"""

import pytest
from flask import Flask, g

import back_dev_home
from back_dev_home import _rate_limit_key, _rate_limit_storage, create_app


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(back_dev_home, "load_dotenv", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")


@pytest.fixture
def client():
    return create_app().test_client()


def test_the_budget_is_shared_across_endpoints_not_per_route(client):
    """Interleaving two endpoints is the discriminating probe: per-route
    windows would sit below 50 each and wave the 51st request through."""
    client.set_cookie("LASTUSER", "7770001")

    statuses = []
    for i in range(50):
        path = "/api/me" if i % 2 == 0 else "/api/health/providers"
        statuses.append(client.get(path).status_code)

    assert 429 not in statuses
    assert client.get("/api/me").status_code == 429


def test_msr_image_stays_exempt_from_the_application_budget(client):
    """The gallery fans out dozens of requests per view. exempt() must cover
    the APPLICATION scope, and the exempt hits must not drain the shared
    budget either — the /api/me probe at the end is what catches that."""
    client.set_cookie("LASTUSER", "7770002")

    statuses = [client.get("/api/msr-images").status_code for _ in range(52)]

    assert 429 not in statuses
    assert client.get("/api/me").status_code == 200


def test_recipe_status_stays_exempt_from_the_application_budget(client):
    """/recipe-status is two blueprints behind one route — its align/meas tabs
    are fail_issue, its tat tab is recipe_tat. Each tab fires ~5 analytics
    calls per filter change, so a few fab-multiselect clicks used to 429 the
    whole app. Interleaving the two proves the exemption covers BOTH, and the
    /api/me probe proves the exempt hits did not drain the shared budget."""
    client.set_cookie("LASTUSER", "7770003")

    paths = ("/api/cdsem/fail-issue/devices", "/api/cdsem/recipe-tat/summary")
    statuses = [client.get(paths[i % 2]).status_code for i in range(52)]

    # == {200}, not `429 not in`: a typo'd path would 404 all 52 times and pass
    # a no-429 assertion while proving nothing about the exemption.
    assert set(statuses) == {200}
    assert client.get("/api/me").status_code == 200


def test_anonymous_callers_get_per_address_buckets():
    app = Flask(__name__)
    with app.test_request_context(environ_base={"REMOTE_ADDR": "10.9.8.7"}):
        g.user_id = "anonymous"
        assert _rate_limit_key() == "anon:10.9.8.7"


def test_identified_callers_are_keyed_by_their_id():
    app = Flask(__name__)
    with app.test_request_context(environ_base={"REMOTE_ADDR": "10.9.8.7"}):
        g.user_id = "2067928"
        assert _rate_limit_key() == "2067928"


def test_storage_is_in_process_at_home_even_with_redis_configured(monkeypatch):
    """The set-but-unreachable trap: home's .env carries the office
    REDIS_HOST, so configuration presence must not decide storage — mode
    does."""
    monkeypatch.setenv("REDIS_HOST", "redis.office.example")

    assert _rate_limit_storage() == {"storage_uri": "memory://"}


def test_storage_is_the_shared_redis_at_the_office(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    monkeypatch.setenv("REDIS_HOST", "redis.office.example")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_PASSWORD", "p@ss/word")

    kwargs = _rate_limit_storage()

    assert kwargs["storage_uri"] == "redis://:p%40ss%2Fword@redis.office.example:6380/0"
    assert kwargs["in_memory_fallback_enabled"] is True
    assert kwargs["storage_options"] == {
        "socket_connect_timeout": 1,
        "socket_timeout": 1,
    }


def test_office_mode_without_a_redis_host_falls_back_to_memory(monkeypatch):
    """Office-localhost (Phase 2) may run without Redis configured; the
    limiter must not invent a redis:// URI out of defaults."""
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    monkeypatch.delenv("REDIS_HOST", raising=False)

    assert _rate_limit_storage() == {"storage_uri": "memory://"}
