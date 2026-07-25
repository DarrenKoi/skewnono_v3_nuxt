"""Contract gate for recipe_search. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search
Office: SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search

Only `get_recipe_catalog` actually swaps: providers/office_example.py re-exports
`get_recipe_open_data` / `get_recipe_compare_data` from providers/mock.py behind
a TODO(office), so the detail and compare gates below run the same code under
both providers today. They are still written provider-honestly, because the day
that TODO is closed is the day this file has to keep being right.

The shape and self-consistency checks hold under both providers — MIGRATION.md
requires `total == len(rows)` of the office adapter too. What is NOT
provider-independent is the SIZE of the catalog: the mock synthesizes 50,000
sha256-seeded names, while office looks the fab up in a Redis hash where a
missing *field* (unknown fab) is a legitimate empty result. That assumption is
fenced behind get_data_provider("recipe_search") == "mock".
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.recipe_search import data
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    RecipeCompareResponse,
    RecipeDetailResponse,
    RecipeSearchResponse,
)


TOOL_TYPE = "cd-sem"


def _is_mock() -> bool:
    return get_data_provider("recipe_search") == "mock"


def test_recipe_catalog_matches_contract():
    catalog = data.get_recipe_catalog(TOOL_TYPE)
    assert_matches(catalog, RecipeSearchResponse)

    # `total` is what the UI shows above a virtualised list it scrolls through
    # `rows`; MIGRATION.md pins the two together for the office adapter as
    # well, so a drift here is a bug under either provider.
    assert catalog["total"] == len(catalog["rows"])
    assert catalog["tool_type"] == TOOL_TYPE
    assert len(set(catalog["rows"])) == len(catalog["rows"]), "recipe names must be de-duped"

    if _is_mock():
        # The mock synthesizes a fixed 50,000-name catalog, so an empty one
        # means the generator broke. Office returns an empty list for a fab
        # with no hash field, which MIGRATION.md calls valid (the LookupError
        # 502 is reserved for a missing hash KEY — the upstream job never ran).
        assert catalog["rows"], "mock recipe catalog must not be empty"


def test_recipe_open_and_compare_match_contract():
    # Prefer a real catalog recipe, but never silently skip on an empty catalog
    # — get_recipe_open_data accepts any id, so a deterministic fallback keeps
    # detail/compare exercised even when the catalog is empty.
    catalog = data.get_recipe_catalog(TOOL_TYPE)
    rows = catalog["rows"]
    recipe_name = rows[0] if rows else "RECIPE-CONTRACT-0001"

    detail = data.get_recipe_open_data(recipe_id=recipe_name)
    assert_matches(detail, RecipeDetailResponse)
    assert detail["recipe_id"] == recipe_name, "detail must answer for the id asked for"

    # amp_info and idp_image_info are joined on `Parameter` to build the
    # per-parameter panel; an AMP row for an undeclared parameter is dropped on
    # the floor whatever produced it. Keyed off the SAME resolved recipe as the
    # detail call above, so closing the TODO(office) cannot leave this asking
    # the office adapter for a recipe that does not exist there.
    declared = {row["Parameter"] for row in detail["idp_image_info"]}
    for amp in detail["amp_info"]:
        assert amp["parameter"] in declared, (
            f"AMP row references undeclared parameter {amp['parameter']!r}"
        )

    compare = data.get_recipe_compare_data(TOOL_TYPE, None, [recipe_name])
    assert_matches(compare, RecipeCompareResponse)
    assert compare["tool_type"] == TOOL_TYPE
    # The compare view columns the recipes side by side under the headers the
    # caller passed; a recipe nobody asked for has no column to land in.
    assert {entry["recipe_id"] for entry in compare["recipes"]} <= {recipe_name}
