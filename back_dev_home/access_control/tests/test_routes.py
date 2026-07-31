"""Route-level tests: the @require_admin gate on all three /api/admin/access
routes, and the enforcement path (is_blocked/record_denied) driven through the
real middleware — end to end via the Flask test client.

OVERLAP IS DELIBERATE. The root ``tests/test_access_control.py`` already
asserts most of this (403 for a non-admin on GET and POST, grant→revoke,
denied-attempt recording); what is new here is DELETE — neither its 403 nor
its 404 was covered anywhere — and the three routes as one admin flow rather
than as separate cases. The module exists at all because this feature's
tests live next to the feature (`pytest back_dev_home/access_control` is the
command every MIGRATION.md gives), and the admin gate is the one thing
standing between a normal member and the exception list, so it should not be
covered exclusively from a suite in another tree.

Unlike test_contract.py, which runs against the ACTIVE provider, this module
PINS the mock provider (``SKEWNONO_ACCESS_CONTROL_PROVIDER=mock``): it points
the mock's store at a throwaway file and calls its ``reset_for_tests``, both
mock-only helpers, so an office run of this directory must not resolve these
requests to Redis. The admin/enforcement wiring under test is
provider-independent — ``routes.py`` and ``_auth/middleware.py`` are identical
in every phase.
"""

import pytest

from back_dev_home import create_app
from back_dev_home.access_control.providers import mock as mock_provider

ADMIN = "local-dev"  # home-phase default admin
NORMAL = "1234567"
BLOCKED = "X9999999"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_ACCESS_CONTROL_PROVIDER", "mock")
    # Throwaway store file so these tests never touch the gitignored
    # state/access_exceptions.json a dev server may be using.
    monkeypatch.setenv(
        "SKEWNONO_ACCESS_EXCEPTIONS_FILE", str(tmp_path / "access_exceptions.json")
    )
    mock_provider.reset_for_tests()
    app = create_app()
    app.config["TESTING"] = True
    # The shared limiter state persists across create_app() calls within one
    # process; disable it so assertion-heavy tests don't trip 429s.
    for limiter in app.extensions["limiter"]:
        limiter.enabled = False
    yield app.test_client()
    # Drop the cache (still keyed to the tmp file) and the process-global
    # denied ring buffer this module wrote to.
    mock_provider.reset_for_tests()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/admin/access"),
        ("POST", "/api/admin/access/exceptions"),
        ("DELETE", f"/api/admin/access/exceptions/{BLOCKED}"),
    ],
)
def test_non_admin_gets_403_on_every_admin_route(client, method, path):
    client.set_cookie("LASTUSER", NORMAL)
    kwargs = {"json": {"user_id": BLOCKED}} if method == "POST" else {}
    res = client.open(path, method=method, **kwargs)
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "forbidden"


def test_admin_grant_shows_in_overview_then_delete_removes(client):
    client.set_cookie("LASTUSER", ADMIN)

    res = client.post("/api/admin/access/exceptions", json={"user_id": BLOCKED})
    assert res.status_code == 201
    assert res.get_json()["user_id"] == BLOCKED

    res = client.get("/api/admin/access")
    assert res.status_code == 200
    body = res.get_json()
    assert body["rule"]["blocked_prefix"] == "X"
    assert any(row["user_id"] == BLOCKED for row in body["exceptions"])

    res = client.delete(f"/api/admin/access/exceptions/{BLOCKED}")
    assert res.status_code == 200
    assert res.get_json() == {"removed": BLOCKED}
    overview = client.get("/api/admin/access").get_json()
    assert all(row["user_id"] != BLOCKED for row in overview["exceptions"])

    # Removal is idempotent at the data layer but a 404 at the route: the
    # admin asked to delete something that is not there.
    res = client.delete(f"/api/admin/access/exceptions/{BLOCKED}")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "not_found"


def test_blocked_user_is_denied_on_api_and_recorded(client):
    # Exercises is_blocked/record_denied through the real before_request hook
    # (_auth/middleware.py), not by calling the data layer directly.
    client.set_cookie("LASTUSER", BLOCKED)
    res = client.get("/api/activity/me")
    assert res.status_code == 403
    assert res.get_json()["error"]["code"] == "access_denied"

    client.set_cookie("LASTUSER", ADMIN)
    denied = client.get("/api/admin/access").get_json()["denied"]
    assert any(row["user_id"] == BLOCKED for row in denied)
