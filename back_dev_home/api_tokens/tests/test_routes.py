"""Route-level gate for /api/account/api-tokens.

The contract suite (test_contract.py) exercises the data layer through
data.py; nothing there proves the HTTP surface — the per-user scoping via
g.user_id, the 400 label validation, or the 403 that keeps a bearer-token
caller from managing tokens. These tests drive the real identity middleware
(cookie AND bearer paths) against the real blueprint, pinned to the mock
provider so they are deterministic regardless of site.
"""

import pytest
from flask import Flask

from back_dev_home._auth.middleware import install_identity_middleware
from back_dev_home._auth.provider import CloudIdentityProvider
from back_dev_home.api_tokens.providers import mock
from back_dev_home.api_tokens.routes import bp

USER_A = "1234567"
USER_B = "7654321"


@pytest.fixture
def client(monkeypatch):
    """Identity middleware + the api_tokens blueprint, nothing else.

    The real middleware is installed so the bearer-token path
    (_try_api_token → g.api_token_id) is the production one, not a stub —
    the 403 guard below only exists because of that path. The store is the
    mock provider, reset around each test since it is module-global.
    """
    monkeypatch.setenv("SKEWNONO_API_TOKENS_PROVIDER", "mock")
    mock.reset_for_tests()
    app = Flask(__name__)
    install_identity_middleware(app, CloudIdentityProvider())
    app.register_blueprint(bp, url_prefix="/api")
    yield app.test_client()
    mock.reset_for_tests()


def _as(client, user_id):
    client.set_cookie("LASTUSER", user_id)
    return client


def test_create_list_delete_roundtrip(client):
    _as(client, USER_A)

    created = client.post("/api/account/api-tokens", json={"label": "laptop"})
    assert created.status_code == 201
    body = created.get_json()
    assert body["plaintext"].startswith("skn_")
    token = body["token"]
    assert token["label"] == "laptop"
    # The secret is a sibling of the row, never embedded in it.
    assert set(token) == {"id", "label", "created_at", "last_used_at"}

    listed = client.get("/api/account/api-tokens").get_json()["tokens"]
    assert [row["id"] for row in listed] == [token["id"]]

    deleted = client.delete(f"/api/account/api-tokens/{token['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json() == {"revoked": token["id"]}
    assert client.get("/api/account/api-tokens").get_json()["tokens"] == []


def test_delete_is_idempotent_second_call_is_404(client):
    _as(client, USER_A)
    token_id = client.post(
        "/api/account/api-tokens", json={"label": "once"}
    ).get_json()["token"]["id"]

    assert client.delete(f"/api/account/api-tokens/{token_id}").status_code == 200
    second = client.delete(f"/api/account/api-tokens/{token_id}")
    assert second.status_code == 404
    assert second.get_json()["error"]["code"] == "not_found"


def test_an_owner_cannot_see_or_delete_another_owners_token(client):
    _as(client, USER_A)
    token_id = client.post(
        "/api/account/api-tokens", json={"label": "mine"}
    ).get_json()["token"]["id"]

    _as(client, USER_B)
    # Not in B's list...
    assert client.get("/api/account/api-tokens").get_json()["tokens"] == []
    # ...and not deletable by B either — 404, with no hint the id exists.
    stolen = client.delete(f"/api/account/api-tokens/{token_id}")
    assert stolen.status_code == 404

    # A still owns it, untouched.
    _as(client, USER_A)
    listed = client.get("/api/account/api-tokens").get_json()["tokens"]
    assert [row["id"] for row in listed] == [token_id]


def test_a_bearer_token_cannot_manage_tokens(client):
    plaintext = _as(client, USER_A).post(
        "/api/account/api-tokens", json={"label": "leaked"}
    ).get_json()["plaintext"]

    bearer = {"Authorization": f"Bearer {plaintext}"}
    # The bearer identity works — listing is allowed...
    listed = client.get("/api/account/api-tokens", headers=bearer)
    assert listed.status_code == 200
    assert len(listed.get_json()["tokens"]) == 1

    # ...but minting a sibling or revoking one is refused.
    minted = client.post(
        "/api/account/api-tokens", json={"label": "spawn"}, headers=bearer
    )
    assert minted.status_code == 403
    assert minted.get_json()["error"]["message"] == "API tokens cannot manage tokens"

    token_id = listed.get_json()["tokens"][0]["id"]
    revoked = client.delete(f"/api/account/api-tokens/{token_id}", headers=bearer)
    assert revoked.status_code == 403
    assert revoked.get_json()["error"]["code"] == "forbidden"


def test_an_invalid_bearer_token_is_401_not_403(client):
    response = client.post(
        "/api/account/api-tokens",
        json={"label": "x"},
        headers={"Authorization": "Bearer skn_not-a-real-token"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_token"


@pytest.mark.parametrize(
    "body",
    [None, {}, {"label": ""}, {"label": "   "}, {"label": "x" * 81}],
    ids=["no-body", "no-label", "empty", "whitespace", "too-long"],
)
def test_label_validation_rejects_bad_input(client, body):
    _as(client, USER_A)
    response = client.post("/api/account/api-tokens", json=body)

    assert response.status_code == 400
    assert response.get_json()["error"]["code"] == "invalid_request"
    assert client.get("/api/account/api-tokens").get_json()["tokens"] == []


def test_an_80_char_label_is_the_accepted_boundary(client):
    _as(client, USER_A)
    response = client.post("/api/account/api-tokens", json={"label": "x" * 80})

    assert response.status_code == 201
    assert response.get_json()["token"]["label"] == "x" * 80
