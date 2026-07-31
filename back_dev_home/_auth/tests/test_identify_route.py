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


def test_an_unreachable_directory_accepts_unverified(client, directory_says):
    """§11's `디렉터리 도달 불가 → 200` row. Refusing here would deny access on
    the strength of our own outage, and the home/mock path takes exactly this
    branch — so it is also the row every home session exercises."""
    directory_says(Probe(None, "unavailable"))

    response = client.post(
        "/api/identify", json={"empno": "2067928", "emp_nm": "고대영"}
    )

    assert response.status_code == 200
    assert response.get_json()["verified"] is False


def test_a_declared_identity_is_not_admin_under_either_phase_default(
    client, directory_says, monkeypatch
):
    """With no SKEWNONO_ADMIN_USERS set, `admin.py` picks its default set from
    is_cloud(). The other admin test pins an explicit allowlist, so neither
    default is exercised there — and a declared caller must be refused under
    both, not just the one this machine happens to run.
    """
    monkeypatch.delenv("SKEWNONO_ADMIN_USERS", raising=False)
    directory_says(Probe(MEMBER_DOC, "found"))

    for cloud in (True, False):
        monkeypatch.setattr(
            "back_dev_home._auth.admin.is_cloud", lambda cloud=cloud: cloud
        )
        admin_mod._parse_allowlist.cache_clear()

        body = client.post(
            "/api/identify", json={"empno": "2067928", "emp_nm": "고대영"}
        ).get_json()

        assert body["is_admin"] is False

    admin_mod._parse_allowlist.cache_clear()


def test_an_unverified_declaration_keeps_the_entered_name(client, directory_says):
    """Otherwise an accepted employee number would carry no name at all, which
    is the unattributable traffic this feature exists to remove."""
    directory_says(Probe(None, "absent"))

    client.post("/api/identify", json={"empno": "9999999", "emp_nm": "홍길동"})

    with client.session_transaction() as session:
        assert session["declared"]["emp_nm"] == "홍길동"
        assert session["declared"]["verified"] is False


def test_a_missing_name_is_refused_server_side(client, directory_says):
    """The /identify screen requires a name, but that gate is client-side. An
    `absent` probe accepts with no directory name to fall back on, so a curl
    caller omitting `emp_nm` would otherwise store the accepted-with-no-name
    state Decision's docstring rules out — attributed traffic with nobody
    attached."""
    directory_says(Probe(None, "absent"))

    response = client.post("/api/identify", json={"empno": "9999999"})

    assert response.status_code == 422
    assert response.get_json()["error"] == "invalid_input"
    assert client.get("/api/me").get_json()["user_id"] == "anonymous"


def test_a_blank_name_is_refused_server_side(client, directory_says):
    """Whitespace must read as absent, mirroring the empno handling."""
    directory_says(Probe(None, "absent"))

    response = client.post(
        "/api/identify", json={"empno": "9999999", "emp_nm": "   "}
    )

    assert response.status_code == 422
    assert response.get_json()["error"] == "invalid_input"


def _nameless_member(user_id):
    """What lookup_member returns on the cloud for an empno with no members
    row — the home mock always fabricates a name, so the None path the merge
    below exists for has to be planted (the documented mock value-domain
    blind spot)."""
    return {
        "empno": user_id,
        "emp_nm": None,
        "dept_nm": None,
        "organ_cd": None,
        "upper_organ_nm": None,
    }


def test_the_declared_name_fills_a_nameless_member(
    client, directory_says, monkeypatch
):
    """An absent directory row leaves the member nameless, and the name the
    caller typed is then the only attribution there is — without the merge,
    the header greets a self-identified caller by raw empno."""
    directory_says(Probe(None, "absent"))
    monkeypatch.setattr(routes_mod, "lookup_member", _nameless_member)

    client.post("/api/identify", json={"empno": "9999999", "emp_nm": "김철수"})
    body = client.get("/api/me").get_json()

    assert body["identity_source"] == "declared"
    assert body["member"]["emp_nm"] == "김철수"


def test_a_stale_declaration_never_renames_a_cookie_caller(
    client, directory_says, monkeypatch
):
    """The chain prefers a LASTUSER cookie over the declared session, so a
    declaration left behind in the session must not leak its stored name onto
    the cookie identity — that would attribute one person's name to another's
    empno. The nameless member is the truth for the cookie caller."""
    directory_says(Probe(None, "absent"))
    monkeypatch.setattr(routes_mod, "lookup_member", _nameless_member)

    client.post("/api/identify", json={"empno": "9999999", "emp_nm": "김철수"})
    client.set_cookie("LASTUSER", "1234567")
    body = client.get("/api/me").get_json()

    assert body["identity_source"] == "cookie"
    assert body["user_id"] == "1234567"
    assert body["member"]["emp_nm"] is None


def test_an_oversized_input_is_refused_before_the_directory(
    client, directory_says
):
    """The pair rides into the session cookie (silently dropped past ~4KB —
    the declaration would evaporate on reload) and into the OpenSearch
    user_id keyword field. The bound fires before probe_member so the
    directory never sees garbage."""
    directory_says(Probe(None, "absent"))

    huge = "9" * 65
    for payload in (
        {"empno": huge, "emp_nm": "김철수"},
        {"empno": "9999999", "emp_nm": "김" * 65},
    ):
        response = client.post("/api/identify", json=payload)
        assert response.status_code == 422
        assert response.get_json()["error"] == "invalid_input"

    assert client.get("/api/me").get_json()["user_id"] == "anonymous"


@pytest.mark.parametrize("empno", ["anonymous", "Anonymous", "local-dev", "LOCAL-DEV"])
def test_the_fallback_ids_cannot_be_declared(client, directory_says, empno):
    """`anonymous`/`local-dev` are vocabulary, not people: a declared
    `anonymous` would muddy exactly the log distinction this feature creates,
    and `local-dev` would wear home's admin id in the cloud activity log.
    Case-insensitive so `Anonymous` cannot slip in as a distinct log id."""
    directory_says(Probe(None, "absent"))

    response = client.post("/api/identify", json={"empno": empno, "emp_nm": "김철수"})

    assert response.status_code == 422
    assert response.get_json()["error"] == "invalid_input"
    assert client.get("/api/me").get_json()["user_id"] == "anonymous"
