"""Contract gate for recipe_search. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search
Office: SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_search

`get_recipe_catalog` (Redis) and `get_recipe_open_data` (tool FTP + the 사내 IDP
parser) both swap; only `get_recipe_compare_data` is still re-exported from
providers/mock.py behind a TODO(office). So under the office provider this file
does REAL I/O — an OpenSearch lookup and an FTP download per detail call — and
is the closest thing recipe_search has to an end-to-end office check.

The mapping itself is gated separately and without infrastructure, in
`test_idp_mapping.py`, which feeds hand-built DataFrames to the pure
`_to_detail_response`. That file is where a column or JSON-safety regression
should be caught; this one answers "does the real chain still run".

The shape and self-consistency checks hold under both providers — MIGRATION.md
requires `total == len(rows)` of the office adapter too. What is NOT
provider-independent is the SIZE of the catalog: the mock synthesizes 50,000
sha256-seeded names, while office looks the fab up in a Redis hash where a
missing *field* (unknown fab) is a legitimate empty result. That assumption is
fenced behind get_data_provider("recipe_search") == "mock".
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.recipe_search import data
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    ParamDetailResponse,
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

    try:
        detail = data.get_recipe_open_data(recipe_id=recipe_name)
    except LookupError as exc:
        # Office only, and only for this one cause: the catalog lists every
        # recipe that EXISTS, while recipe open needs one that has RUN — the
        # .idp location is derived from a measurement document. Picking an
        # unmeasured name is a property of the fixture, not a contract break,
        # so it must not read as a failing gate. Any other exception still
        # fails, and under mock this path is unreachable.
        if _is_mock():
            raise
        pytest.skip(f"catalog recipe {recipe_name!r} has no measurement doc: {exc}")

    assert_matches(detail, RecipeDetailResponse)
    assert detail["recipe_id"] == recipe_name, "detail must answer for the id asked for"

    # AMP no longer rides on the detail response — it is fetched per click from
    # the raw-recipe folder (spec 2026-07-29). What the detail response owes the
    # follow-up calls is the locator, so that is what is pinned here.
    assert set(detail["locator"]) == {"eqp_ip", "class_name", "idw", "idp"}
    assert all(detail["locator"][field] for field in detail["locator"]), (
        "an empty locator field would make param-detail unaddressable"
    )

    # The per-parameter panel posts a parameter's own img_* values back as
    # `slots`, so every declared parameter must carry all five.
    for row in detail["idp_image_info"]:
        for slot in ("img_add1", "img_add2", "image_add3", "img_meas1", "img_meas2"):
            assert slot in row, f"{row['Parameter']!r} is missing {slot}"

    param_detail = data.get_param_detail([{
        "locator": detail["locator"],
        "parameter": detail["idp_image_info"][0]["Parameter"],
        "slots": {
            slot: detail["idp_image_info"][0][slot]
            for slot in ("img_add1", "img_add2", "image_add3", "img_meas1", "img_meas2")
        },
    }]) if detail["idp_image_info"] else []
    for entry in param_detail:
        assert_matches(entry, ParamDetailResponse)

    compare = data.get_recipe_compare_data(TOOL_TYPE, None, [recipe_name])
    assert_matches(compare, RecipeCompareResponse)
    assert compare["tool_type"] == TOOL_TYPE
    # The compare view columns the recipes side by side under the headers the
    # caller passed; a recipe nobody asked for has no column to land in.
    assert {entry["recipe_id"] for entry in compare["recipes"]} <= {recipe_name}
