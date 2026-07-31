"""`POST`/`DELETE /api/identify`.

The endpoint a caller nobody could name uses to name themselves. It is an
ordinary `/api/*` path with no exemption in the identity gate, and it needs
none: the cloud provider gives every caller `anonymous`, so an unidentified
visitor reaches this route already identified.

The tests below drive the route through a real gate rather than a stub, because
the interesting behaviour is the handoff — the declaration has to change who
the *next* request is, and a route that wrote a session the chain then ignored
would pass every unit test and strand the user on the form.
"""

import pytest
from flask import Flask

from back_dev_home._auth import admin as admin_mod
from back_dev_home._auth import directory as directory_mod
from back_dev_home._auth import middleware as middleware_mod
from back_dev_home._auth import routes as routes_mod
from back_dev_home._auth.directory import Probe
from back_dev_home._auth.middleware import install_identity_middleware
from back_dev_home._auth.provider import CloudIdentityProvider

MEMBER_DOC = {
    "empno": "2067928",
    "emp_nm": "고대영",
    "dept_nm": "계측기술팀",
    "organ_cd": "A1234",
    "upper_organ_nm": "제조기술",
}


@pytest.fixture(autouse=True)
def no_access_control(monkeypatch):
    monkeypatch.setattr(middleware_mod, "is_blocked", lambda user_id: False)
    monkeypatch.setattr(middleware_mod, "record_denied", lambda user_id: None)


@pytest.fixture(autouse=True)
def clean_directory_cache():
    directory_mod.reset_cache()
    yield
    directory_mod.reset_cache()


@pytest.fixture
def client():
    app = Flask(__name__, static_folder=None)
    app.secret_key = "test-key-not-the-real-one"
    install_identity_middleware(app, CloudIdentityProvider())
    app.register_blueprint(routes_mod.bp, url_prefix="/api")
    return app.test_client()


@pytest.fixture
def directory_says(monkeypatch):
    """Plant a probe result, standing in for the whole Redis path."""

    def _install(probe):
        monkeypatch.setattr(routes_mod, "probe_member", lambda user_id: probe)

    return _install


def test_a_matching_name_is_accepted_and_verified(client, directory_says):
    directory_says(Probe(MEMBER_DOC, "found"))

    response = client.post(
        "/api/identify", json={"empno": "2067928", "emp_nm": "고대영"}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["user_id"] == "2067928"
    assert body["identity_source"] == "declared"
    assert body["verified"] is True


def test_the_identity_survives_the_next_request(client, directory_says):
    """The handoff. A declaration that did not outlive its own POST would send
    the user straight back to the form on the next navigation."""
    directory_says(Probe(MEMBER_DOC, "found"))
    client.post("/api/identify", json={"empno": "2067928", "emp_nm": "고대영"})

    body = client.get("/api/me").get_json()

    assert body["user_id"] == "2067928"
    assert body["identity_source"] == "declared"
    assert body["verified"] is True


def test_a_wrong_name_is_refused(client, directory_says):
    directory_says(Probe(MEMBER_DOC, "found"))

    response = client.post(
        "/api/identify", json={"empno": "2067928", "emp_nm": "홍길동"}
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == "not_verified"


def test_a_refused_declaration_leaves_the_caller_anonymous(client, directory_says):
    """A rejection must not half-succeed: no session, no partial identity."""
    directory_says(Probe(MEMBER_DOC, "found"))
    client.post("/api/identify", json={"empno": "2067928", "emp_nm": "홍길동"})

    assert client.get("/api/me").get_json()["user_id"] == "anonymous"


def test_an_absent_row_is_accepted_unverified(client, directory_says):
    """Contractors and service accounts have no directory row; refusing them
    would lock out a population `directory.py` documents as ordinary."""
    directory_says(Probe(None, "absent"))

    response = client.post(
        "/api/identify", json={"empno": "9999999", "emp_nm": "홍길동"}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["user_id"] == "9999999"
    assert body["verified"] is False


def test_a_missing_empno_is_refused(client, directory_says):
    directory_says(Probe(MEMBER_DOC, "found"))

    response = client.post("/api/identify", json={"emp_nm": "고대영"})

    assert response.status_code == 422
    assert response.get_json()["error"] == "invalid_input"


def test_a_body_that_is_not_json_is_refused_not_crashed(client, directory_says):
    directory_says(Probe(MEMBER_DOC, "found"))

    response = client.post("/api/identify", data="not json")

    assert response.status_code == 422


def test_both_refusals_use_the_same_user_facing_message(client, directory_says):
    """Row-missing and name-wrong would be distinguishable by message
    otherwise, which turns the endpoint into a directory-membership oracle for
    anyone willing to read the response text."""
    directory_says(Probe(MEMBER_DOC, "found"))
    mismatch = client.post(
        "/api/identify", json={"empno": "2067928", "emp_nm": "홍길동"}
    )
    directory_says(Probe({**MEMBER_DOC, "emp_nm": "다른사람"}, "found"))
    other = client.post("/api/identify", json={"empno": "1111111", "emp_nm": "홍길동"})

    assert mismatch.get_json()["message"] == other.get_json()["message"]


def test_a_declared_identity_is_never_admin(client, directory_says, monkeypatch):
    """The feature's only server-side boundary, end to end: typing the admin's
    employee number into the form must not produce an admin session."""
    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "2067928")
    admin_mod._parse_allowlist.cache_clear()
    directory_says(Probe(MEMBER_DOC, "found"))

    body = client.post(
        "/api/identify", json={"empno": "2067928", "emp_nm": "고대영"}
    ).get_json()

    assert body["is_admin"] is False
    admin_mod._parse_allowlist.cache_clear()


def test_a_cookie_caller_is_admin_for_the_same_id(client, directory_says, monkeypatch):
    """The other half of the previous test: the id IS an admin's, so the
    refusal above must come from the source and not from the allowlist being
    empty."""
    monkeypatch.setenv("SKEWNONO_ADMIN_USERS", "2067928")
    admin_mod._parse_allowlist.cache_clear()
    client.set_cookie("LASTUSER", "2067928")

    assert client.get("/api/me").get_json()["is_admin"] is True
    admin_mod._parse_allowlist.cache_clear()


def test_delete_clears_the_declaration(client, directory_says):
    directory_says(Probe(MEMBER_DOC, "found"))
    client.post("/api/identify", json={"empno": "2067928", "emp_nm": "고대영"})

    body = client.delete("/api/identify").get_json()

    assert body["user_id"] == "anonymous"
    assert body["identity_source"] == "anonymous"
    assert client.get("/api/me").get_json()["identity_source"] == "anonymous"


def test_delete_with_nothing_declared_is_not_an_error(client):
    """Reachable from a page whose session already expired."""
    assert client.delete("/api/identify").status_code == 200


def test_delete_returns_the_cookie_identity_when_one_exists(client, directory_says):
    """The response describes what the NEXT request will compute, not a blanket
    `anonymous` — a caller holding a cookie is still that person afterwards."""
    directory_says(Probe(MEMBER_DOC, "found"))
    client.post("/api/identify", json={"empno": "9999999", "emp_nm": "홍길동"})
    client.set_cookie("LASTUSER", "2067928")

    body = client.delete("/api/identify").get_json()

    assert body["user_id"] == "2067928"
    assert body["identity_source"] == "cookie"


def test_the_declaring_ip_is_recorded(client, directory_says):
    """One employee number declared from many addresses, or many from one, is
    the pattern this field exists to make visible."""
    directory_says(Probe(MEMBER_DOC, "found"))

    client.post(
        "/api/identify",
        json={"empno": "2067928", "emp_nm": "고대영"},
        environ_overrides={"REMOTE_ADDR": "10.251.122.42"},
    )

    with client.session_transaction() as session:
        assert session["declared"]["declared_from"] == "10.251.122.42"


def test_the_directory_name_is_stored_not_the_entered_one(client, directory_says):
    directory_says(Probe(MEMBER_DOC, "found"))

    client.post("/api/identify", json={"empno": "2067928", "emp_nm": "  고대영  "})

    with client.session_transaction() as session:
        assert session["declared"]["emp_nm"] == "고대영"


def test_an_unverified_declaration_keeps_the_entered_name(client, directory_says):
    """Otherwise an accepted employee number would carry no name at all, which
    is the unattributable traffic this feature exists to remove."""
    directory_says(Probe(None, "absent"))

    client.post("/api/identify", json={"empno": "9999999", "emp_nm": "홍길동"})

    with client.session_transaction() as session:
        assert session["declared"]["emp_nm"] == "홍길동"
        assert session["declared"]["verified"] is False
