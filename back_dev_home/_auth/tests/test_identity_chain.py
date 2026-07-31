"""The four-step identity chain and its precedence.

`test_middleware.py` covers the gate's other duty — that it must never answer a
page request, the invariant whose violation produced the Phase 3 blank window.
This file covers what the chain decides: which step wins, and what each one
calls itself.

The source name is not decoration. `admin.py` reads it to decide whether an
identity may hold admin at all, so a step that mislabelled itself would either
hand authority to a self-declared identity or take it away from every home
developer.
"""

import pytest
from flask import Flask, g

from back_dev_home._auth import middleware as middleware_mod
from back_dev_home._auth.middleware import install_identity_middleware
from back_dev_home._auth.provider import (
    SOURCE_ANONYMOUS,
    SOURCE_COOKIE,
    SOURCE_DECLARED,
    SOURCE_LOCAL,
    SOURCE_TOKEN,
    CloudIdentityProvider,
    LocalIdentityProvider,
)
from back_dev_home._auth.self_id import write_declared

SPA_MARK = "<!-- SPA INDEX -->"


@pytest.fixture(autouse=True)
def no_access_control(monkeypatch):
    """Neutralize the access-control store, as test_middleware.py does."""
    monkeypatch.setattr(middleware_mod, "is_blocked", lambda user_id: False)
    monkeypatch.setattr(middleware_mod, "record_denied", lambda user_id: None)


@pytest.fixture
def make_client():
    """A client for an app running the chain under the given provider."""

    def _make(provider):
        app = Flask(__name__, static_folder=None)
        app.secret_key = "test-key-not-the-real-one"
        install_identity_middleware(app, provider)

        @app.get("/api/whoami")
        def _whoami():
            return {
                "user_id": getattr(g, "user_id", None),
                "identity_source": getattr(g, "identity_source", None),
            }

        @app.post("/api/declare")
        def _declare():
            write_declared(
                empno="7654321",
                emp_nm="선언자",
                verified=False,
                declared_from="10.0.0.9",
            )
            return {"ok": True}

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def _spa(path: str):
            return SPA_MARK

        return app.test_client()

    return _make


@pytest.fixture
def cloud(make_client):
    return make_client(CloudIdentityProvider())


def test_an_api_token_is_tagged_token_and_outranks_everything(make_client, monkeypatch):
    """Step 1, the only step that can answer with a response instead of an
    identity — which is why it sits outside `resolve_identity`. Tested through
    the gate because a token that authenticated without tagging its source
    would be non-admin everywhere, breaking automation rather than security.
    """
    row = type("Row", (), {"owner_user_id": "2067928", "id": "tok_1"})()
    monkeypatch.setattr(middleware_mod, "find_by_plaintext", lambda text: row)
    monkeypatch.setattr(middleware_mod, "touch_last_used", lambda token_id: None)
    client = make_client(CloudIdentityProvider())
    client.set_cookie("LASTUSER", "9999999")

    body = client.get(
        "/api/whoami", headers={"Authorization": "Bearer skn_whatever"}
    ).get_json()

    assert body == {"user_id": "2067928", "identity_source": SOURCE_TOKEN}


def test_a_cookie_identity_is_tagged_cookie(cloud):
    cloud.set_cookie("LASTUSER", "2067928")

    assert cloud.get("/api/whoami").get_json() == {
        "user_id": "2067928",
        "identity_source": SOURCE_COOKIE,
    }


def test_no_cookie_on_the_cloud_is_tagged_anonymous(cloud):
    assert cloud.get("/api/whoami").get_json() == {
        "user_id": "anonymous",
        "identity_source": SOURCE_ANONYMOUS,
    }


def test_no_cookie_at_home_is_tagged_local(make_client):
    """Home's fallback must be distinguishable from a real cookie — that
    distinction is what lets `local` hold admin while `anonymous` cannot."""
    home = make_client(LocalIdentityProvider())

    assert home.get("/api/whoami").get_json() == {
        "user_id": "local-dev",
        "identity_source": SOURCE_LOCAL,
    }


def test_a_declared_session_beats_the_fallback(cloud):
    cloud.post("/api/declare")

    assert cloud.get("/api/whoami").get_json() == {
        "user_id": "7654321",
        "identity_source": SOURCE_DECLARED,
    }


def test_a_cookie_beats_a_declared_session(cloud):
    """Precedence in the direction that matters: infrastructure identity
    outranks a typed one, so a user who is later given a real cookie stops
    being their own declaration without having to clear anything."""
    cloud.post("/api/declare")
    cloud.set_cookie("LASTUSER", "2067928")

    assert cloud.get("/api/whoami").get_json() == {
        "user_id": "2067928",
        "identity_source": SOURCE_COOKIE,
    }


def test_a_declaration_survives_the_request_that_made_it(cloud):
    """The session round trip. A declaration that did not outlive its own POST
    would send the user back to the form on the very next navigation."""
    cloud.post("/api/declare")

    assert cloud.get("/api/whoami").get_json()["user_id"] == "7654321"
    assert cloud.get("/api/whoami").get_json()["user_id"] == "7654321"


def test_a_declared_page_request_still_reaches_the_spa(cloud):
    """The invariant re-checked on the new branch: nothing added to the chain
    may answer a non-/api path, or index.html dies with it."""
    cloud.post("/api/declare")
    response = cloud.get("/")

    assert response.status_code == 200
    assert SPA_MARK in response.get_data(as_text=True)


def test_a_declared_identity_cannot_escape_access_control(make_client, monkeypatch):
    """The bypass `_deny_if_blocked` had to close.

    Access control blocks X-prefixed ids but exempts admins. While that exempt
    check asked `is_admin` — an id-only question — anyone could declare an
    admin's employee number and inherit the exemption. It now asks
    `is_admin_request`, so a declared identity is never exempt.
    """
    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "X1234567")
    from back_dev_home._auth import admin as admin_mod

    admin_mod._parse_allowlist.cache_clear()

    app = Flask(__name__, static_folder=None)
    app.secret_key = "test-key-not-the-real-one"
    install_identity_middleware(app, CloudIdentityProvider())

    @app.get("/api/sem-list")
    def _sem_list():
        return {"rows": [], "user": getattr(g, "user_id", None)}

    @app.post("/api/declare-admin")
    def _declare_admin():
        write_declared(
            empno="X1234567", emp_nm=None, verified=False, declared_from=None
        )
        return {"ok": True}

    client = app.test_client()

    # Declare BEFORE blocking is switched on. With is_blocked already True the
    # declaring POST is itself denied, the session is never written, and the
    # 403 below would arrive for an anonymous caller — the test would pass
    # while proving nothing about declared identities.
    client.post("/api/declare-admin")
    assert client.get("/api/sem-list").get_json()["user"] == "X1234567"

    monkeypatch.setattr(middleware_mod, "is_blocked", lambda user_id: True)
    denied = client.get("/api/sem-list")

    assert denied.status_code == 403
    assert denied.get_json()["error"]["code"] == "access_denied"
    admin_mod._parse_allowlist.cache_clear()
