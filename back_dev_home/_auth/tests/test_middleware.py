"""The identity gate: what answers a request before any route sees it.

``install_identity_middleware`` registers the app's first ``before_request``,
so it decides the fate of every request — including the one that fetches the
SPA's index.html. That position is why a defect here looks like a dead site
rather than a broken endpoint.

The Phase 3 deploy failed exactly that way: ``GET /`` answered 302 forever and
the browser rendered nothing. The log line named the culprit precisely —
``user=- method=GET path=/ status=302 ms=-1`` — because ``ms=-1`` is emitted
only when the activity timer never started, and the timer is a
``before_request`` registered *after* this one.

So the invariants below are the deploy's health, not a unit's tidiness: a page
request from an unidentified visitor must fall THROUGH to whatever serves the
SPA, only ``/api/*`` may be refused, and nothing here may ever redirect.
"""

import pytest
from flask import Flask, g

from back_dev_home._auth import middleware as middleware_mod
from back_dev_home._auth.middleware import install_identity_middleware
from back_dev_home._auth.provider import CloudIdentityProvider

SPA_MARK = "<!-- SPA INDEX -->"


@pytest.fixture
def no_access_control(monkeypatch):
    """Neutralize the access-control store.

    The office provider makes ``is_blocked`` a Redis round trip and
    ``record_denied`` a write; the home mock keeps process-global counters that
    leak between tests. Blocking is re-enabled per-test where it is the subject.
    """
    monkeypatch.setattr(middleware_mod, "is_blocked", lambda user_id: False)
    monkeypatch.setattr(middleware_mod, "record_denied", lambda user_id: None)
    monkeypatch.setattr(middleware_mod, "is_admin", lambda user_id: False)


@pytest.fixture
def client(no_access_control):
    """An app shaped like the cloud one: identity gate, an API, an SPA mount.

    The catch-all stands in for ``_spa/serving.py`` so the assertions read as
    "the visitor got the app" rather than "some 200 came back", and it is
    registered in the same order ``create_app`` uses.
    """
    app = Flask(__name__, static_folder=None)
    install_identity_middleware(app, CloudIdentityProvider())

    @app.get("/api/sem-list")
    def _sem_list():
        return {"rows": [], "user": getattr(g, "user_id", None)}

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _spa(path: str):
        return SPA_MARK

    return app.test_client()


def test_a_page_request_without_a_cookie_reaches_the_spa(client):
    """The regression. An unidentified visitor asking for a page must get the
    page. Answering with a redirect sent the browser to SSO, which sent it
    straight back — an infinite loop that renders as a blank window with no
    console error to grep for."""
    response = client.get("/")

    assert response.status_code == 200
    assert SPA_MARK in response.get_data(as_text=True)


def test_no_page_path_is_ever_answered_with_a_redirect(client):
    """Broader than the one failing path: a deep-link reload lands on an
    arbitrary client-side route, and any of them redirecting reopens the loop."""
    for path in ("/", "/sem-list", "/ebeam/hitachi/storage", "/skewvoir/1/detail"):
        response = client.get(path)

        assert response.status_code == 200, path
        assert not (300 <= response.status_code < 400), path


def test_static_assets_load_for_an_unidentified_visitor(client):
    """The index alone is not a working page. If the gate refused the bundle,
    the SPA would boot into a white screen just the same."""
    assert client.get("/_nuxt/entry.abc12345.js").status_code == 200
    assert client.get("/favicon.ico").status_code == 200


def test_an_api_request_without_a_cookie_runs_as_anonymous(client):
    """The cloud substitutes `anonymous` rather than refusing — the network is
    already internal, so an unidentified caller gets a working app. What
    matters is that the request is still *attributed*: a null user in the
    activity log is indistinguishable from a logging bug."""
    response = client.get("/api/sem-list")

    assert response.status_code == 200
    assert response.get_json()["user"] == "anonymous"


def test_the_refusal_path_survives_a_provider_that_identifies_nobody(
    no_access_control,
):
    """`CloudIdentityProvider` never returns None now, which would leave the
    gate's 401 branch dead — and dead code guarding an API is exactly the kind
    that rots unnoticed until something reintroduces None. Driven through a
    provider that does return None, so the branch stays honest."""
    app = Flask(__name__, static_folder=None)

    class _IdentifiesNobody:
        def identify(self, request):
            return None

    install_identity_middleware(app, _IdentifiesNobody())

    @app.get("/api/sem-list")
    def _sem_list():
        return {"rows": []}

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _spa(path: str):
        return SPA_MARK

    client = app.test_client()
    refused = client.get("/api/sem-list")

    assert client.get("/").status_code == 200  # the page still opens
    assert refused.status_code == 401
    assert refused.get_json()["error"]["code"] == "unauthenticated"


def test_the_cookie_becomes_the_user_id(client):
    """The identity itself, end to end through the gate."""
    client.set_cookie("LASTUSER", "2067928")

    assert client.get("/api/sem-list").get_json()["user"] == "2067928"


def test_the_legacy_cookie_spelling_still_identifies(client):
    """afm/routes.py has read both spellings since before this app existed."""
    client.set_cookie("LAST_USER", "1234567")

    assert client.get("/api/sem-list").get_json()["user"] == "1234567"


def test_a_blocked_member_loses_the_api_but_keeps_the_page(client, monkeypatch):
    """Access control's contract, unchanged by the cookie switch: an X-prefixed
    member is denied data with a 403 the SPA turns into a friendly screen — so
    the HTML must still load, or there is nothing to show it in."""
    monkeypatch.setattr(middleware_mod, "is_blocked", lambda user_id: True)
    client.set_cookie("LASTUSER", "X123456")

    page = client.get("/")
    api = client.get("/api/sem-list")

    assert page.status_code == 200
    assert SPA_MARK in page.get_data(as_text=True)
    assert api.status_code == 403
    assert api.get_json()["error"]["code"] == "access_denied"
