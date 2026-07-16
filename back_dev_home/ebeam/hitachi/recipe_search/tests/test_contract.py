"""Contract gate for recipe_search. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search
Office: SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.recipe_search import data
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    RecipeCompareResponse,
    RecipeDetailResponse,
    RecipeSearchResponse,
)


def test_recipe_catalog_matches_contract():
    catalog = data.get_recipe_catalog("cd-sem")
    assert_matches(catalog, RecipeSearchResponse)


def test_recipe_open_and_compare_match_contract():
    # Prefer a real catalog recipe, but never silently skip on an empty catalog
    # — get_recipe_open_data accepts any id, so a deterministic fallback keeps
    # detail/compare exercised even when the catalog is empty.
    catalog = data.get_recipe_catalog("cd-sem")
    rows = catalog["rows"]
    recipe_name = rows[0] if rows else "RECIPE-CONTRACT-0001"

    detail = data.get_recipe_open_data(recipe_id=recipe_name)
    assert_matches(detail, RecipeDetailResponse)

    compare = data.get_recipe_compare_data("cd-sem", None, [recipe_name])
    assert_matches(compare, RecipeCompareResponse)
