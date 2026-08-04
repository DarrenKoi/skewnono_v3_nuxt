"""Route-level auth gate: per-employee enumeration is admin-only.

/activity/me, /activity/summary and /activity/fabs stay open to every
identified user (aggregates), while /activity/users and /activity/users/<id>
require a trusted admin identity.
"""

import pytest
from flask import Flask, g

from back_dev_home._logging.activity import install_activity_logging
from back_dev_home.activity import routes
from back_dev_home.activity.providers import mock


@pytest.fixture
def make_client(monkeypatch):
    """Client factory with stubbed loaders and a chosen identity."""

    monkeypatch.delenv("SKEWNONO_ADMIN_USERS", raising=False)
    monkeypatch.setattr(routes, "get_me", lambda user_id: {"user_id": user_id})
    monkeypatch.setattr(routes, "get_summary", lambda: {"dau": 0})
    monkeypatch.setattr(routes, "get_fab_page_usage", lambda: {"fabs_7d": []})
    monkeypatch.setattr(routes, "get_users_list", lambda: {"users": []})
    monkeypatch.setattr(
        routes, "get_user_history", lambda user_id: {"user_id": user_id}
    )

    def build(user_id, identity_source):
        app = Flask(__name__)

        @app.before_request
        def identity():
            g.user_id = user_id
            g.identity_source = identity_source

        app.register_blueprint(routes.bp, url_prefix="/api")
        return app.test_client()

    return build


@pytest.mark.parametrize(
    "path",
    ["/api/activity/users", "/api/activity/users/2067928"],
)
def test_user_enumeration_is_forbidden_for_non_admins(make_client, path):
    client = make_client("1234567", "cookie")

    response = client.get(path)

    assert response.status_code == 403
    assert response.json["error"]["code"] == "forbidden"


@pytest.mark.parametrize(
    "path",
    ["/api/activity/users", "/api/activity/users/2067928"],
)
def test_user_enumeration_is_allowed_for_the_home_admin(make_client, path):
    # local-dev via the trusted local identity source is home's admin.
    client = make_client("local-dev", "local")

    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    "path",
    ["/api/activity/me", "/api/activity/summary", "/api/activity/fabs"],
)
def test_aggregate_views_stay_open_to_normal_users(make_client, path):
    client = make_client("1234567", "cookie")

    assert client.get(path).status_code == 200


def test_a_declared_admin_id_does_not_pass_the_gate(make_client):
    # Typing an admin's id through self-identification proves nothing; only
    # trusted identity sources may hold admin.
    client = make_client("local-dev", "declared")

    assert client.get("/api/activity/users").status_code == 403


# The brief's sketch used a bare `client` fixture; this module only offers
# `make_client(user_id, identity_source)`, so these reuse that factory with a
# normal identified user — the beacon has no admin gate, but the handler still
# expects an identified request, matching every other route in this file.


def test_page_view_beacon_returns_204(make_client):
    client = make_client("1234567", "cookie")

    response = client.post("/api/page-view", json={"path": "/mag-pixel"})

    assert response.status_code == 204
    assert response.get_data() == b""


def test_page_view_beacon_rejects_a_missing_path(make_client):
    client = make_client("1234567", "cookie")

    assert client.post("/api/page-view", json={}).status_code == 400
    assert client.post("/api/page-view", json={"path": ""}).status_code == 400
    assert client.post("/api/page-view", data="not json").status_code == 400


@pytest.fixture
def beacon_client(monkeypatch):
    """A beacon client with the REAL activity middleware and an empty store.

    The plain ``make_client`` app has no after_request middleware, so it can
    only observe the status code. Recording happens in
    ``_logging/activity.py``, so proving "not ranked" needs that installed and
    the mock provider's process-local store swapped for a fresh one.
    """
    monkeypatch.setenv("SKEWNONO_ACTIVITY_PROVIDER", "mock")
    store: dict[str, mock._UserState] = {}
    monkeypatch.setattr(mock, "_users", store)

    app = Flask(__name__)

    @app.before_request
    def identity():
        g.user_id = "1234567"
        g.identity_source = "cookie"

    app.register_blueprint(routes.bp, url_prefix="/api")
    install_activity_logging(app)
    return app.test_client(), store


def test_a_resolvable_page_is_recorded_as_that_page(beacon_client):
    """The positive control: without it, an empty store proves nothing."""
    client, store = beacon_client

    assert client.post("/api/page-view", json={"path": "/mag-pixel"}).status_code == 204

    assert store["1234567"].by_feature == {"mag_pixel": 1}


@pytest.mark.parametrize(
    "path",
    [
        "/settings",
        "/admin/logs",
        "/ebeam/cd-sem/M14/recipe-status",
    ],
    ids=["ops-page", "ops-child-page", "recipe-status-without-a-tab"],
)
def test_an_unresolvable_page_is_accepted_but_not_ranked(beacon_client, path):
    """An ops page or a tab-less recipe-status is a 204 that records nothing.

    A 400 here would make the browser console noisy for a case that is not an
    error — the plugin cannot know which paths the backend ranks. But the row
    must not be counted either: with no promoted slug the middleware would
    otherwise fall back to route_to_feature("/api/page-view") and rank the
    literal slug "page-view" as if it were a page.
    """
    client, store = beacon_client

    assert client.post("/api/page-view", json={"path": path}).status_code == 204

    assert store == {}
