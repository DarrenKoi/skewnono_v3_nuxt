"""SWAP SURFACE for ebeam/lateral_recipe.

Routes import only this module. The selected adapter lives in
providers/mock.py or providers/office.py.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi._tool_specs import ToolType
from back_dev_home.ebeam.lateral_recipe.providers.mock import LateralRecipeResponse


__all__ = [
    "get_lateral_recipe",
]


def _provider():
    if get_data_provider("lateral_recipe") == "office":
        from back_dev_home.ebeam.lateral_recipe.providers import office
        return office
    from back_dev_home.ebeam.lateral_recipe.providers import mock
    return mock


def get_lateral_recipe(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_name: str
) -> LateralRecipeResponse:
    return _provider().get_lateral_recipe(tool_type, fab_name, recipe_name)
