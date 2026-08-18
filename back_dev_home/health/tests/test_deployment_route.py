"""The deployment-shape endpoint the SPA reads to hide unvalidated 실험실 pages.

Open to every user, unlike its admin-only sibling /health/providers: the answer
is which deployment the caller is already talking to, which the address bar
gives away anyway. What stays behind the gate there is the feature enumeration
and the per-feature resolution reason, and this endpoint must not carry either.

At home the no-cookie fallback identity IS `local-dev`, an admin, so the
normal-member case has to send a member id explicitly.
"""

import back_dev_home.health.routes as routes
from back_dev_home import create_app


def test_deployment_reports_not_cloud_at_home():
    """Home is a checkout outside /project/workSpace, so is_cloud() is False and
    the unvalidated 실험실 rows stay visible where they are developed."""
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "local-dev")

    response = client.get("/api/health/deployment")

    assert response.status_code == 200
    assert response.get_json() == {"is_cloud": False}


def test_deployment_reports_cloud_when_is_cloud(monkeypatch):
    """The only case that hides anything. Patched at the route's import site
    because is_cloud() is a filesystem-path check that cannot be faked by an
    environment variable — which is the property that makes it trustworthy."""
    monkeypatch.setattr(routes, "is_cloud", lambda: True)
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "local-dev")

    assert client.get("/api/health/deployment").get_json() == {"is_cloud": True}


def test_deployment_is_open_to_a_normal_user():
    """A menu that only admins see the right version of is not the point: the
    rows are hidden from PRODUCTION users, so production users must be able to
    ask."""
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "1234567")

    response = client.get("/api/health/deployment")

    assert response.status_code == 200
    assert response.get_json()["is_cloud"] in (True, False)


def test_deployment_does_not_leak_the_provider_table():
    """The feature enumeration and the resolution reasons stay on
    /health/providers, behind the admin gate."""
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "1234567")

    body = client.get("/api/health/deployment").get_json()

    assert set(body) == {"is_cloud"}
