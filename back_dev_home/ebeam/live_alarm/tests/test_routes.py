import pytest

from back_dev_home import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_returns_a_board_for_a_valid_tool_slug(client):
    # "cdsem" (no hyphen), not "cd-sem": resolve_tool_type_from_slug (Task 1's
    # _tool_specs.py) only recognizes VALID_TOOL_SLUGS = {"cdsem", "hvsem"} —
    # same convention every sibling ebeam route already uses (fail_issue,
    # recipe_tat, hardware, ...), and the one the frontend's own toolSlug()
    # translators (useFailIssueApi.ts, useStorageApi.ts) convert down to.
    response = client.get("/api/cdsem/live-alarm?fab_name=R3")
    assert response.status_code == 200
    assert response.get_json()["fab_names"] == ["R3"]


def test_hv_sem_url_exists_too(client):
    assert client.get("/api/hvsem/live-alarm?fab_name=R3").status_code == 200


def test_unknown_tool_slug_is_400(client):
    assert client.get("/api/nope/live-alarm?fab_name=R3").status_code == 400


def test_missing_fab_name_is_400(client):
    assert client.get("/api/cdsem/live-alarm").status_code == 400


def test_comma_list_fab_name_returns_every_requested_fab(client):
    response = client.get("/api/cdsem/live-alarm?fab_name=R3,M16A")
    assert response.status_code == 200
    assert response.get_json()["fab_names"] == ["R3", "M16A"]


def test_a_partially_unconfigured_multi_fab_selection_still_renders(client):
    response = client.get("/api/cdsem/live-alarm?fab_name=R3,ZZZ")
    assert response.status_code == 200
    body = response.get_json()
    assert body["not_configured_fabs"] == ["ZZZ"]
    assert body["feed_status"] != "not_configured"


def test_unconfigured_fab_is_200_not_configured(client):
    # An unknown/unwired fab is not a 404: the endpoint answers 200 with
    # feed_status="not_configured", so the page renders a clear "미설정" panel
    # (nav intact) instead of an error page. Mock and office agree on this.
    response = client.get("/api/cdsem/live-alarm?fab_name=ZZZ")
    assert response.status_code == 200
    body = response.get_json()
    assert body["feed_status"] == "not_configured"
    assert body["events"] == []
