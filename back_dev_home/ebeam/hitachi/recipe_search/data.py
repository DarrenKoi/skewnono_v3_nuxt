"""SWAP SURFACE for ebeam/hitachi recipe_search.

Routes import only this module. The selected adapter lives in
providers/mock.py or providers/office.py. ``ToolType`` is a
provider-independent type alias and lives here.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    AlignDetailResponse,
    IdpLocator,
    ParamDetailRequestItem,
    ParamDetailResponse,
)
from back_dev_home.ebeam.hitachi.recipe_search.providers.mock import (
    RecipeCompareResponse,
    RecipeDetailResponse,
    RecipeSearchResponse,
    ToolType,
)


__all__ = [
    "ToolType",
    "fetch_recipe_image",
    "get_align_detail",
    "get_param_detail",
    "get_recipe_catalog",
    "get_recipe_compare_data",
    "get_recipe_open_data",
]


def _provider():
    if get_data_provider("recipe_search") == "office":
        from back_dev_home.ebeam.hitachi.recipe_search.providers import office
        return office
    from back_dev_home.ebeam.hitachi.recipe_search.providers import mock
    return mock


def get_recipe_catalog(tool_type: ToolType, fab_name: str | None = None) -> RecipeSearchResponse:
    return _provider().get_recipe_catalog(tool_type, fab_name)


def get_recipe_open_data(
    recipe_id: str | None = None,
    fab_name: str | None = None,
    tool_category: str | None = None,
) -> RecipeDetailResponse:
    return _provider().get_recipe_open_data(recipe_id, fab_name, tool_category)


def get_recipe_compare_data(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_names: list[str],
) -> RecipeCompareResponse:
    return _provider().get_recipe_compare_data(tool_type, fab_name, recipe_names)


def get_param_detail(
    items: list[ParamDetailRequestItem],
) -> list[ParamDetailResponse]:
    return _provider().get_param_detail(items)


def get_align_detail(
    locator: IdpLocator,
    p_numbers: list[int],
) -> AlignDetailResponse:
    return _provider().get_align_detail(locator, p_numbers)


def fetch_recipe_image(locator: IdpLocator, name: str) -> tuple[bytes, str]:
    """``(bytes, content_type)`` for one raw-recipe image.

    Raises:
        LookupError: the image is absent on the tool. The route turns this into
            a 404 so ``<img>`` falls back to its own broken state rather than
            decoding a JSON error body as a picture.
    """
    return _provider().fetch_recipe_image(locator, name)
