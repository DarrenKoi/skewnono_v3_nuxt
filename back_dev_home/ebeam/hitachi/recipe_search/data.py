"""SWAP SURFACE for ebeam/hitachi recipe_search.

Routes import only this module. The selected adapter lives in
providers/mock.py or providers/office.py. ``ToolType`` is a
provider-independent type alias and lives here.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.recipe_search.providers.mock import (
    RecipeCompareResponse,
    RecipeDetailResponse,
    RecipeSearchResponse,
    ToolType,
)


__all__ = [
    "ToolType",
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
    fac_id: str | None = None,
    tool_category: str | None = None,
) -> RecipeDetailResponse:
    return _provider().get_recipe_open_data(recipe_id, fac_id, tool_category)


def get_recipe_compare_data(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_names: list[str],
) -> RecipeCompareResponse:
    return _provider().get_recipe_compare_data(tool_type, fab_name, recipe_names)
