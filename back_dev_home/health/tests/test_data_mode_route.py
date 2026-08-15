"""The per-feature data-mode endpoint.

Sibling of /health/providers, and deliberately NOT the same endpoint. The
providers table is admin-only because it enumerates every backend feature and
the deployment reason each resolved the way it did. This one answers a single
question about a single named feature — "is what I am looking at generated
data?" — which is precisely the question every user of a chart is entitled to
have answered, so it carries no admin gate and no reason string.

At home the no-cookie fallback identity IS `local-dev`, an admin, so the
normal-member case has to send a member id explicitly.
"""

from back_dev_home import create_app


def test_data_mode_answers_for_one_named_feature():
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "local-dev")

    response = client.get("/api/health/data-mode?feature=msr_file")

    assert response.status_code == 200
    body = response.get_json()
    assert body == {"feature": "msr_file", "provider": "mock"} or body == {
        "feature": "msr_file",
        "provider": "office",
    }


def test_data_mode_is_open_to_a_normal_user():
    """The whole point: a marker that only admins can see is not a marker."""
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "1234567")

    response = client.get("/api/health/data-mode?feature=msr_file")

    assert response.status_code == 200
    assert response.get_json()["provider"] in ("mock", "office")


def test_data_mode_requires_the_feature_param():
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "local-dev")

    response = client.get("/api/health/data-mode")

    assert response.status_code == 400


def test_data_mode_rejects_an_unknown_feature():
    """A typo must not answer 'mock' — that would read as a demo warning on
    real data, or hide one on generated data."""
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "local-dev")

    response = client.get("/api/health/data-mode?feature=not_a_feature")

    assert response.status_code == 404


def test_data_mode_does_not_leak_the_provider_table():
    """The enumeration and the resolution reason stay behind the admin gate on
    /health/providers; this endpoint answers about the one feature asked for."""
    client = create_app().test_client()
    client.set_cookie("LASTUSER", "1234567")

    body = client.get("/api/health/data-mode?feature=msr_file").get_json()

    assert set(body) == {"feature", "provider"}
