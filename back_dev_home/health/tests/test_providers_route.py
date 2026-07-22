"""The provider introspection endpoint.

Deliberately NOT routed through health/data.py's mock/office swap: this is
runtime introspection, not phase-swappable data. A swappable version could
misreport itself in exactly the situation you would query it.
"""

from back_dev_home import create_app


def test_providers_endpoint_lists_every_feature():
    client = create_app().test_client()
    response = client.get("/api/health/providers")
    assert response.status_code == 200

    body = response.get_json()
    assert body["mode"] in ("mock", "office")
    assert body["site"] in ("home", "office", "unknown")

    features = {row["feature"]: row for row in body["features"]}
    assert {"sem_list", "storage", "hardware"} <= set(features)
    for row in features.values():
        assert row["provider"] in ("mock", "office")
        assert row["reason"]


def test_providers_endpoint_is_not_a_swappable_data_surface():
    """health/data.py must gain no provider function — the endpoint reads the
    runtime directly, so it cannot be swapped out from under itself."""
    from back_dev_home.health import data

    assert not hasattr(data, "get_provider_table")
