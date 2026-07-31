"""The landing page's health card endpoint.

Open to every user on purpose — a normal user seeing "Redis is down" is the
point of the card — so the two things this pins are that the gate stays off
and that an unexpected provider failure answers a stable JSON 503 rather than
Flask's bare HTML 500.
"""

import pytest

from back_dev_home import create_app
from back_dev_home.health import routes


@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")


@pytest.fixture
def client():
    return create_app().test_client()


def test_services_endpoint_is_open_to_a_normal_user(client):
    client.set_cookie("LASTUSER", "1234567")

    response = client.get("/api/health/services")

    assert response.status_code == 200
    body = response.get_json()
    assert [s["id"] for s in body["services"]] == ["redis", "opensearch", "minio"]
    assert body["checked_at"].endswith("Z")


def test_provider_blowup_answers_a_stable_json_503(client, monkeypatch):
    """Each probe traps its own exceptions, so reaching the route's guard means
    the provider itself broke — a bad office.py import, a config raise. That
    must not surface as an HTML 500, and must not leak the reason."""

    def fail():
        raise RuntimeError("office.py imports secret-internal-host")

    monkeypatch.setattr(routes, "get_services_health", fail)

    response = client.get("/api/health/services")

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"]["code"] == "health_unavailable"
    assert "secret-internal-host" not in str(body)
    # The 3-rows contract covers success only: a failure has no rows at all
    # rather than a short list that would read as "two services are fine".
    assert "services" not in body
