"""Status codes and guards for the three tiered read endpoints.

These run against the MOCK provider, so they assert shape and status rather
than values: the mock draws Parameter values at random, and a test that
depended on a particular one would be flaky by construction. The composition
itself is tested in test_param_info.py against a fixed payload.
"""

import pytest
from flask import Flask

from back_dev_home.ebeam.recipe_search import routes


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/api")
    return app.test_client()


def _listing(client):
    return client.get(
        "/api/cdsem/recipe-search/parameters?recipe_name=RCP_001"
    ).get_json()


def _any_parameter(client):
    return _listing(client)["rows"][0]["Parameter"]


# ── parameters ────────────────────────────────────────────────────────────


def test_parameters_returns_row_and_parameter_counts(client):
    response = client.get("/api/cdsem/recipe-search/parameters?recipe_name=RCP_001")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total_rows"] == len(body["rows"])
    assert body["distinct_parameters"] <= body["total_rows"]
    assert set(body["locator"]) == {"eqp_ip", "class_name", "idw", "idp"}


def test_parameters_requires_a_recipe_name(client):
    assert client.get("/api/cdsem/recipe-search/parameters").status_code == 400


def test_parameters_rejects_an_unknown_tool_slug(client):
    response = client.get("/api/xxsem/recipe-search/parameters?recipe_name=R")
    assert response.status_code == 400


# ── measurement-points ────────────────────────────────────────────────────


def test_measurement_points_returns_only_the_named_parameter(client):
    parameter = _any_parameter(client)
    response = client.get(
        "/api/cdsem/recipe-search/measurement-points"
        f"?recipe_name=RCP_001&parameter={parameter}"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert all(point["Parameter"] == parameter for point in body["points"])
    assert body["total"] == len(body["points"])


def test_measurement_points_requires_a_parameter(client):
    response = client.get(
        "/api/cdsem/recipe-search/measurement-points?recipe_name=RCP_001"
    )
    assert response.status_code == 400


def test_measurement_points_404s_on_a_parameter_the_recipe_lacks(client):
    response = client.get(
        "/api/cdsem/recipe-search/measurement-points"
        "?recipe_name=RCP_001&parameter=Para_does_not_exist"
    )
    assert response.status_code == 404


# ── param-info ────────────────────────────────────────────────────────────


def test_param_info_returns_an_occurrence_per_row(client):
    parameter = _any_parameter(client)
    rows = _listing(client)["rows"]
    expected = sum(1 for row in rows if row["Parameter"] == parameter)

    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        f"?recipe_name=RCP_001&parameter={parameter}"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["occurrences"]) == expected
    assert body["include"] == ["amp", "af_pr", "images"]


def test_param_info_include_narrows_the_response(client):
    parameter = _any_parameter(client)
    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        f"?recipe_name=RCP_001&parameter={parameter}&include=amp"
    )
    assert response.status_code == 200
    occurrence = response.get_json()["occurrences"][0]
    assert "amp" in occurrence
    assert "af_pr" not in occurrence
    assert "images" not in occurrence


def test_param_info_rejects_an_unknown_include_part(client):
    parameter = _any_parameter(client)
    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        f"?recipe_name=RCP_001&parameter={parameter}&include=beam"
    )
    assert response.status_code == 400


def test_param_info_404s_on_a_parameter_the_recipe_lacks(client):
    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        "?recipe_name=RCP_001&parameter=Para_does_not_exist"
    )
    assert response.status_code == 404


def test_param_info_requires_recipe_name_and_parameter(client):
    assert client.get(
        "/api/cdsem/recipe-search/param-info?parameter=Para_1"
    ).status_code == 400
    assert client.get(
        "/api/cdsem/recipe-search/param-info?recipe_name=RCP_001"
    ).status_code == 400


def test_param_info_turns_an_unreachable_tool_into_503(client, monkeypatch):
    """A tool that refuses the connection is a 503, not a 500 traceback.

    Same contract param-detail, align-detail and recipe-image already keep.
    """
    from back_dev_home.msr_image.errors import SourceUnavailable

    parameter = _any_parameter(client)

    def boom(_items):
        raise SourceUnavailable("tool refused the connection")

    monkeypatch.setattr(routes, "get_param_detail", boom)
    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        f"?recipe_name=RCP_001&parameter={parameter}"
    )
    assert response.status_code == 503


@pytest.mark.parametrize("path", [
    "/api/cdsem/recipe-search/parameters?recipe_name=RCP_001",
    "/api/cdsem/recipe-search/measurement-points?recipe_name=RCP_001&parameter=P",
    "/api/cdsem/recipe-search/param-info?recipe_name=RCP_001&parameter=P",
    # recipe-detail predates this change and had NO guard: locating the .idp is
    # I/O at the office, so an unreachable tool escaped as a 500 traceback on
    # the feature's most-used endpoint. The blueprint errorhandler covers it.
    "/api/cdsem/recipe-search/recipe-detail?recipe_name=RCP_001",
])
def test_an_unreachable_tool_is_503_on_every_recipe_route(client, monkeypatch, path):
    from back_dev_home.msr_image.errors import SourceUnavailable

    def boom(**_kwargs):
        raise SourceUnavailable("tool refused the connection")

    monkeypatch.setattr(routes, "get_recipe_open_data", boom)
    response = client.get(path)
    assert response.status_code == 503
    # The flat body this surface has always used, NOT the app-wide nested one.
    assert set(response.get_json()) == {"error", "code"}
