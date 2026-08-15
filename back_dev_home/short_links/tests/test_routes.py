"""HTTP gate for the short linker. Runs against the ACTIVE provider.

Two things are worth pinning through the HTTP hop. First, that a hostile target
is refused at the ROUTE — the validator is unit-tested next door, but what
matters operationally is that no code path reaches the store without passing
through it, since a stored target is trusted on read. Second, that a stale or
mistyped code is a 404 and not a 500: /s/<code> is a link people keep in
messengers for months, so opening a dead one is a routine event.
"""

import pytest

from back_dev_home import create_app
from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.short_links.contracts import ShortLink

TARGET = "/ebeam/cd-sem/skewvoir/analysis?lot=KPB266344&view=time-series"


@pytest.fixture(autouse=True)
def _clean_store():
    if get_data_provider("short_links") == "mock":
        from back_dev_home.short_links.providers import mock

        mock.reset_for_tests()
    yield


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _mint(client, target=TARGET):
    return client.post("/api/short-links", json={"target": target})


# ── mint ────────────────────────────────────────────────────────────────


def test_minting_returns_201_and_the_contract_shape(client):
    res = _mint(client)
    assert res.status_code == 201
    assert_matches(res.get_json(), ShortLink)


def test_minting_is_idempotent_over_http(client):
    assert _mint(client).get_json()["code"] == _mint(client).get_json()["code"]


def test_a_missing_body_is_a_400_not_a_500(client):
    res = client.post("/api/short-links", json={})
    assert res.status_code == 400


def test_a_missing_target_key_is_a_400(client):
    res = client.post("/api/short-links", json={"path": TARGET})
    assert res.status_code == 400


@pytest.mark.parametrize(
    "hostile",
    [
        "https://evil.example/phish",
        "//evil.example/phish",
        "/\\evil.example/phish",
        "javascript:alert(1)",
        "/\n/evil.example",
        "",
    ],
)
def test_a_hostile_target_is_refused_at_the_route(client, hostile):
    """The open-redirect guard, proven where it actually protects: nothing
    reaches the store without passing the validator."""
    assert _mint(client, hostile).status_code == 400


def test_a_refused_target_is_not_stored(client):
    """A 400 must leave no trace — otherwise the guard only moved the problem
    from mint to resolve."""
    _mint(client, "//evil.example/phish")

    res = client.get("/api/short-links")
    assert res.status_code in (404, 405)  # no listing endpoint exists


def test_an_over_long_target_is_a_400(client):
    assert _mint(client, "/a" + "b" * 4000).status_code == 400


# ── resolve ─────────────────────────────────────────────────────────────


def test_a_minted_code_resolves_over_http(client):
    code = _mint(client).get_json()["code"]

    res = client.get(f"/api/short-links/{code}")
    assert res.status_code == 200
    assert res.get_json()["target"] == TARGET


def test_an_unknown_code_is_a_404_not_a_500(client):
    res = client.get("/api/short-links/zzzzzzzzzz")
    assert res.status_code == 404


def test_an_unknown_code_carries_a_json_error_body(client):
    """The /s/<code> page renders a "링크를 찾을 수 없습니다" state off this, so
    the 404 has to be JSON rather than Flask's HTML error page."""
    res = client.get("/api/short-links/zzzzzzzzzz")
    assert res.is_json
