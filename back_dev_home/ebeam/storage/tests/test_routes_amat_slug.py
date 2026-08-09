"""storage 는 CD/HV 전용입니다 -- AMAT 슬러그는 400 이어야 합니다.

이 파일이 있는 이유는 실패 방식이 조용하기 때문입니다. `VALID_TOOL_SLUGS` 가
2계열에서 4계열로 넓어졌을 때, storage 라우트는 아무 변경 없이
`/api/veritysem/storage` 를 200 으로 받아들이기 시작했습니다. mock 이 fleet 을
`model_to_tool_type(...) == tool_type` 으로 고르는데 분류기가 AMAT 을 해석하게
됐으니, sem_list 의 AMAT 장비가 그대로 storage 행으로 지어내진 것입니다 --
veritysem 17행, provision 19행. 오류도 경고도 없었습니다.

집에서는 채워진 화면, 사무실에서는 (어댑터가 없으므로) 빈 화면. 없는 데이터는
없다고 답해야 합니다. 400 은 이 브랜치 이전의 동작이기도 합니다.
"""

import pytest

from back_dev_home import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize("tool_slug", ["veritysem", "provision"])
@pytest.mark.parametrize("path", ["storage", "ppid-unavailable"])
def test_amat_slugs_are_rejected(client, tool_slug, path):
    response = client.get(f"/api/{tool_slug}/{path}")
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "tool_slug must be 'cdsem' or 'hvsem'"
    }


@pytest.mark.parametrize("tool_slug", ["cdsem", "hvsem"])
@pytest.mark.parametrize("path", ["storage", "ppid-unavailable"])
def test_sem_slugs_still_answer(client, tool_slug, path):
    assert client.get(f"/api/{tool_slug}/{path}").status_code == 200
