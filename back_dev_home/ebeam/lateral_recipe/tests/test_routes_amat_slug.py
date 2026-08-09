"""횡전개도 CD/HV 전용 -- AMAT 슬러그는 400.

storage 와 같은 함정이었습니다. `providers/mock.py` 의 `_filter_rows()` 가
`model_to_tool_type(row) != tool_type` 으로 걸러내는데, 분류기가 AMAT 을
해석하게 되자 `/api/provision/recipe-search/lateral` 이 200 + 19행 / 4버전을
지어냈습니다.
"""

import pytest

from back_dev_home import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize("tool_slug", ["veritysem", "provision"])
def test_amat_slugs_are_rejected(client, tool_slug):
    response = client.get(
        f"/api/{tool_slug}/recipe-search/lateral?recipe_name=X"
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "tool_slug must be 'cdsem' or 'hvsem'"
    }


@pytest.mark.parametrize("tool_slug", ["cdsem", "hvsem"])
def test_sem_slugs_still_answer(client, tool_slug):
    response = client.get(
        f"/api/{tool_slug}/recipe-search/lateral?recipe_name=X"
    )
    assert response.status_code == 200
