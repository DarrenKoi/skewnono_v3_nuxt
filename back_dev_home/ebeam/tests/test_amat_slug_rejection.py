"""CD/HV 전용 fleet 라우트 전부가 AMAT 슬러그를 400 으로 거절한다.

storage / lateral_recipe 는 각 기능 폴더에 따로 있습니다(그쪽은 200 + 지어낸
행이 실제로 관측된 자리라 근거를 길게 적어뒀습니다). 여기는 나머지 전부를 한
번에 못박는 sweep 입니다 -- 라우트 하나가 검증을 `VALID_TOOL_SLUGS` 로 되돌려도
여기서 걸립니다.

메시지도 함께 확인합니다. 문구가 14곳에 하드코딩돼 있었기 때문에 계열이 늘었을
때 14개가 동시에 낡았고, 아무 테스트도 깨지지 않았습니다. 이제는
`SEM_TOOL_SLUGS` 에서 파생되므로, 아래 테스트는 파생 결과가 계약과 같은지를
봅니다.
"""

import pytest

from back_dev_home import create_app
from back_dev_home.ebeam._slug_routes import sem_tool_slug_error_message
from back_dev_home.ebeam._tool_specs import SEM_TOOL_SLUGS


EXPECTED_ERROR = {"error": "tool_slug must be 'cdsem' or 'hvsem'"}

# (path template, HTTP method). `{slug}` 만 치환합니다.
CD_HV_ONLY_ROUTES: tuple[tuple[str, str], ...] = (
    ("/api/{slug}/skew/check?fab_name=R3", "GET"),
    ("/api/{slug}/hardware/ECXDX101/vacuum", "GET"),
    ("/api/{slug}/pm-planning/fleet?fab_name=R3", "GET"),
    ("/api/{slug}/live-alarm?fab_name=R3", "GET"),
    ("/api/{slug}/recipe-tat/summary", "GET"),
    ("/api/{slug}/recipe-tat/ranking", "GET"),
    ("/api/{slug}/recipe-tat/equipments", "GET"),
    ("/api/{slug}/recipe-tat/equipment-compare", "GET"),
    ("/api/{slug}/fail-issue/summary", "GET"),
    ("/api/{slug}/fail-issue/equipments", "GET"),
    ("/api/{slug}/recipe-search/recipes", "GET"),
    ("/api/{slug}/recipe-search/recipe-detail?recipe_name=X", "GET"),
    ("/api/{slug}/recipe-search/compare", "POST"),
    ("/api/{slug}/recipe-search/param-detail", "POST"),
)


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize("slug", ["veritysem", "provision"])
@pytest.mark.parametrize("template,method", CD_HV_ONLY_ROUTES)
def test_amat_slug_is_rejected(client, slug, template, method):
    path = template.format(slug=slug)
    response = (
        client.post(path, json={})
        if method == "POST"
        else client.get(path)
    )
    assert response.status_code == 400, path
    assert response.get_json() == EXPECTED_ERROR, path


def test_the_error_message_is_derived_from_the_registry():
    assert sem_tool_slug_error_message() == EXPECTED_ERROR["error"]
    for slug in SEM_TOOL_SLUGS:
        assert repr(slug) in sem_tool_slug_error_message()
