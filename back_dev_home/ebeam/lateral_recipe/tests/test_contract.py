"""Contract gate for lateral_recipe. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/lateral_recipe
Office: SKEWNONO_LATERAL_RECIPE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/lateral_recipe
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.lateral_recipe import data
from back_dev_home.ebeam.lateral_recipe.contracts import LateralRecipeResponse


def test_lateral_recipe_matches_contract():
    response = data.get_lateral_recipe("cd-sem", None, "LATERAL-CONTRACT-0001")
    assert_matches(response, LateralRecipeResponse)
