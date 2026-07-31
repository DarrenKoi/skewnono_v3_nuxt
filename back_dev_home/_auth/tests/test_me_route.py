"""`/api/me`: the endpoint the SPA boots against.

It answers three separate questions in one round trip — who am I, may I see
admin surfaces, and what is my name — because the alternative is three requests
against a 20-per-5s rate limit on the first paint of every page.
"""

import json

import pytest
from flask import Flask

from back_dev_home._auth import directory as directory_mod
from back_dev_home._auth import middleware as middleware_mod
from back_dev_home._auth.middleware import install_identity_middleware
from back_dev_home._auth.provider import CloudIdentityProvider
from back_dev_home._auth.routes import bp as auth_bp

MEMBER_DOC = {
    "empno": "2067928",
    "emp_nm": "고대영",
    "dept_nm": "계측기술팀",
    "organ_cd": "A1234",
    "upper_organ_nm": "제조기술",
}


class _FakeRedis:
    def __init__(self, values):
        self._values = values

    def hget(self, key, field):
        value = self._values.get(field)
        return value if value is None else value.encode("utf-8")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(middleware_mod, "is_blocked", lambda user_id: False)
    monkeypatch.setattr(middleware_mod, "record_denied", lambda user_id: None)
    # The real allowlist, driven by the env var it actually reads, rather than
    # a stubbed is_admin — this test's whole point is which source decides.
    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "2067928")
    monkeypatch.setattr(
        directory_mod,
        "redis_client_or_none",
        lambda: _FakeRedis({"2067928": json.dumps(MEMBER_DOC)}),
    )
    directory_mod.reset_cache()

    app = Flask(__name__, static_folder=None)
    install_identity_middleware(app, CloudIdentityProvider())
    app.register_blueprint(auth_bp, url_prefix="/api")
    yield app.test_client()
    directory_mod.reset_cache()


def test_an_identified_caller_gets_their_directory_row(client):
    client.set_cookie("LASTUSER", "2067928")

    body = client.get("/api/me").get_json()

    assert body["user_id"] == "2067928"
    assert body["member"] == MEMBER_DOC


def test_a_caller_with_no_directory_row_still_gets_their_id(client):
    """The fallback the whole directory is built around, seen end to end."""
    client.set_cookie("LASTUSER", "9999999")

    body = client.get("/api/me").get_json()

    assert body["user_id"] == "9999999"
    assert body["member"]["empno"] == "9999999"
    assert body["member"]["emp_nm"] is None


def test_admin_status_comes_from_the_allowlist_not_the_directory(client):
    """The directory is descriptive, never authoritative: a member row must not
    be able to promote anyone. Same id, both answers, one source."""
    client.set_cookie("LASTUSER", "2067928")
    assert client.get("/api/me").get_json()["is_admin"] is True

    client.set_cookie("LASTUSER", "9999999")
    assert client.get("/api/me").get_json()["is_admin"] is False


def test_an_unidentified_caller_is_refused_by_the_gate(client):
    """No carve-out: /api/me is an API path like any other, and the 401 is
    itself the answer the SPA needs."""
    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "unauthenticated"


def test_the_route_is_registered_in_every_phase():
    """Mounted outside the is_cloud() branch, unlike the SPA. A home session
    that could not answer this would build against a screen the cloud never
    shows."""
    from back_dev_home import create_app

    rules = {str(rule) for rule in create_app().url_map.iter_rules()}

    assert "/api/me" in rules
