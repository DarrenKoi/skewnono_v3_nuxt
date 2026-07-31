"""Route-level auth gate: per-employee enumeration is admin-only.

/activity/me, /activity/summary and /activity/fabs stay open to every
identified user (aggregates), while /activity/users and /activity/users/<id>
require a trusted admin identity.
"""

import pytest
from flask import Flask, g

from back_dev_home.activity import routes


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
