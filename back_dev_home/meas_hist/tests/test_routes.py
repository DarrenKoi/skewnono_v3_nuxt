import pytest

from back_dev_home import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.set_cookie("LASTUSER", "local-dev")
        yield c


@pytest.mark.parametrize("path", [
    "/api/meas-hist",
    "/api/meas-hist/search",
    "/api/meas-hist/facets",
])
def test_unknown_tool_type_is_rejected_not_widened(client, path):
    """미지 값이 조용히 '전체'로 떨어지면 필터가 무시된 결과가 나온다."""
    response = client.get(f"{path}?tool_type=zz-sem")
    assert response.status_code == 400
    assert "tool_type" in response.get_json()["error"]


@pytest.mark.parametrize("path", [
    "/api/meas-hist",
    "/api/meas-hist/search",
    "/api/meas-hist/facets",
])
def test_absent_tool_type_still_means_everything(client, path):
    """미지정은 '전체'가 맞다. 파싱 실패와 구분되어야 한다."""
    assert client.get(path).status_code == 200


def test_known_tool_types_are_accepted(client):
    for value in ("cd-sem", "hv-sem"):
        assert client.get(f"/api/meas-hist?tool_type={value}").status_code == 200
