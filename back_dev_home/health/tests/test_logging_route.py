"""The log-shipper diagnostics endpoint.

Like /health/providers, this reads the runtime directly instead of going
through health/data.py: the shipper drops documents rather than fail requests,
so its loss counters must come from the real installed handler, not a
swappable stand-in that could hide exactly the loss being asked about.

Admin-only, like /health/providers — it names the log index alias and the
deployment. At home the no-cookie fallback identity IS `local-dev`, an admin,
so the 403 case has to send a normal member id explicitly.
"""

import logging

import pytest

from back_dev_home import create_app
from back_dev_home._logging.opensearch_handler import OpenSearchBulkHandler


def _never_dial():
    raise AssertionError("the tests must never construct an OpenSearch client")


@pytest.fixture
def client():
    test_client = create_app().test_client()
    test_client.set_cookie("LASTUSER", "local-dev")
    return test_client


def test_logging_health_is_admin_only():
    normal_user = create_app().test_client()
    normal_user.set_cookie("LASTUSER", "1234567")

    response = normal_user.get("/api/health/logging")

    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "forbidden"


def test_logging_health_reports_not_installed_at_home(client):
    response = client.get("/api/health/logging")
    assert response.status_code == 200
    assert response.get_json() == {
        "installed": False,
        "target": None,
        "diagnostics": None,
    }


def test_logging_health_reports_the_installed_shipper(client):
    handler = OpenSearchBulkHandler(
        client_factory=_never_dial,
        deployment="local",
        index="skewnono_logging_local",
    )
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        body = client.get("/api/health/logging").get_json()
    finally:
        root.removeHandler(handler)
        handler.close()

    assert body["installed"] is True
    assert body["target"] == {
        "alias": "skewnono_logging_local",
        "deployment": "local",
    }
    diagnostics = body["diagnostics"]
    assert diagnostics["enqueued"] == 0
    assert diagnostics["indexed"] == 0
    assert diagnostics["dropped"] == 0
    assert diagnostics["queue_depth"] == 0
    assert "last_success_at" in diagnostics
    assert "last_failure_at" in diagnostics
