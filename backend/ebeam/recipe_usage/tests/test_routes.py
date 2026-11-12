from datetime import timedelta

import pytest

from backend import create_app
from backend.ebeam.recipe_usage.providers import mock


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


PATHS = ("recipes", "recipe?recipe_id=A/B/C", "status")


@pytest.mark.parametrize("tool_slug", ["cdsem", "hvsem", "amat", "cd-sem"])
@pytest.mark.parametrize("path", PATHS)
def test_only_the_amat_families_are_served(client, tool_slug, path):
    response = client.get(f"/api/{tool_slug}/recipe-usage/{path}")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "tool_slug must be 'provision' or 'veritysem'"
    }


@pytest.mark.parametrize("tool_slug", ["veritysem", "provision", "VeritySEM"])
@pytest.mark.parametrize("path", PATHS)
def test_amat_slugs_answer(client, tool_slug, path):
    response = client.get(f"/api/{tool_slug}/recipe-usage/{path}")

    assert response.status_code == 200
    assert response.get_json()["tool_type"] == tool_slug.lower()


def test_recipe_requires_recipe_id(client):
    response = client.get("/api/veritysem/recipe-usage/recipe")

    assert response.status_code == 400
    assert response.get_json() == {"error": "recipe_id is required"}


def test_recipe_id_with_slashes_round_trips_as_a_query_param(client):
    recipe_id = mock.load_usage_rows("provision")[0]["recipe_id"]

    body = client.get(
        "/api/provision/recipe-usage/recipe", query_string={"recipe_id": recipe_id}
    ).get_json()

    assert body["recipe_id"] == recipe_id
    assert recipe_id.count("/") == 2
    assert body["tools"] and body["daily"]


def test_unknown_recipe_is_an_empty_answer_not_a_404(client):
    response = client.get("/api/veritysem/recipe-usage/recipe?recipe_id=NO/SUCH/RECIPE/X")

    assert response.status_code == 200
    assert response.get_json()["tools"] == []
    assert response.get_json()["daily"] == []


def test_fab_filter_is_a_comma_list_matched_case_insensitively(client):
    everything = client.get("/api/veritysem/recipe-usage/recipes").get_json()
    scoped = client.get("/api/veritysem/recipe-usage/recipes?fab_name=r4, m14b").get_json()

    assert everything["fab_names"] == []
    assert scoped["fab_names"] == ["R4", "M14B"]
    assert {row["fab_name"] for row in scoped["rows"]} == {"R4", "M14B"}
    assert 0 < scoped["total"] < everything["total"]


def test_fab_filter_scopes_the_status_roster(client):
    body = client.get("/api/veritysem/recipe-usage/status?fab_name=R4").get_json()

    assert {row["fab_name"] for row in body["equipments"]} == {"R4"}
    assert body["summary"]["tool_count"] == len(body["equipments"]) == 2


def test_status_honours_an_explicit_window(client):
    end = mock.ANCHOR_DATE - timedelta(days=3)
    start = end - timedelta(days=2)

    body = client.get(
        f"/api/provision/recipe-usage/status?start_date={start}&end_date={end}"
    ).get_json()

    assert (body["start_date"], body["end_date"]) == (str(start), str(end))
    assert [point["date"] for point in body["daily"]] == [
        str(start), str(start + timedelta(days=1)), str(end),
    ]
    assert body["anchor_date"] == str(mock.ANCHOR_DATE)


@pytest.mark.parametrize("query", [
    "start_date=yesterday",
    "end_date=2026-13-40",
    "start_date=2026-11-10&end_date=2026-11-01",
    "start_date=2020-01-01&end_date=2026-11-01",
])
def test_status_rejects_bad_dates(client, query):
    response = client.get(f"/api/veritysem/recipe-usage/status?{query}")

    assert response.status_code == 400
    assert "error" in response.get_json()
