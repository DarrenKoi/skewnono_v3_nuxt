"""tool-files is filed under one slug for both its API and its page."""

import pytest

from backend._logging.feature_map import page_to_feature, route_to_feature


@pytest.mark.parametrize(
    "path",
    [
        "/api/cdsem/tool-files/list",
        "/api/hvsem/tool-files/download",
        "/api/cdsem/tool-files/access",
    ],
)
def test_api_calls_are_filed_under_tool_files(path):
    assert route_to_feature(path) == "tool_files"


def test_the_page_is_filed_under_tool_files():
    assert page_to_feature("/ebeam/cd-sem/R3/tool-files?eqp=HCDX303") == "tool_files"
