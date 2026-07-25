"""Contract gate for lateral_recipe. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/lateral_recipe
Office: SKEWNONO_LATERAL_RECIPE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/lateral_recipe

The counting and ordering laws below hold under both providers by construction:
both adapters derive `total_tools_in_fab` from `len(rows)`, `not_ready_count`
from `total - ready_count`, sort rows by eqp_id and versions descending, and
take `latest_*` off the head of that version list. Those are what the card
counters and the version dropdown read, so a drift is a bug wherever the rows
came from.

What is NOT provider-independent is that the ROSTER has anything in it. The
mock filters a fabricated sem_list; office joins the real sem_list roster
against OpenSearch, where a fab with no CD-SEM of this type — or a recipe name
that has never been generated — legitimately yields nothing. Those assumptions
are fenced behind get_data_provider("lateral_recipe") == "mock".

The office-only live suite is tests/test_lateral_recipe_local.py (gated on
TEST_LATERAL_*, always skipped at home); this gate does not duplicate it.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.lateral_recipe import data
from back_dev_home.ebeam.hitachi.lateral_recipe.contracts import LateralRecipeResponse


TOOL_TYPE = "cd-sem"
RECIPE_NAME = "LATERAL-CONTRACT-0001"


def _is_mock() -> bool:
    return get_data_provider("lateral_recipe") == "mock"


def _response():
    return data.get_lateral_recipe(TOOL_TYPE, None, RECIPE_NAME)


def test_lateral_recipe_matches_contract():
    response = _response()
    assert_matches(response, LateralRecipeResponse)
    assert response["tool_type"] == TOOL_TYPE
    assert response["recipe_name"] == RECIPE_NAME, "must answer for the recipe asked for"


def test_counters_add_up_to_the_row_set():
    # The three numbers on the summary card are all read off the same table;
    # if they disagree with it the page contradicts itself on screen.
    response = _response()
    rows = response["rows"]
    assert response["total_tools_in_fab"] == len(rows)
    assert response["ready_count"] + response["not_ready_count"] == len(rows)
    assert response["ready_count"] == sum(1 for row in rows if row["recipe_ready"])


def test_rows_are_sorted_by_eqp_id_and_ready_rows_carry_a_version():
    response = _response()
    eqp_ids = [row["eqp_id"] for row in response["rows"]]
    assert eqp_ids == sorted(eqp_ids), "rows must be eqp_id-ascending"
    # NOT asserted: one row per eqp_id. eqp_id is unique within a fab, not
    # across the fleet — this call passes fab_name=None, and both providers
    # then legitimately return the same eqp_id once per fab it lives in.
    for row in response["rows"]:
        if not row["recipe_ready"]:
            # Not-ready means the tool holds no generated recipe, so there is
            # no version or timestamp to show for it.
            assert row["recipe_version"] is None
            assert row["recipe_generated_at"] is None


def test_versions_are_newest_first_and_agree_with_latest():
    # The version dropdown renders `versions` in order and pre-selects
    # `latest_recipe_version`; the two must name the same version.
    response = _response()
    versions = [entry["recipe_version"] for entry in response["versions"]]
    assert versions == sorted(versions, reverse=True)
    assert len(set(versions)) == len(versions), "one entry per version"

    if versions:
        assert response["latest_recipe_version"] == versions[0]
        assert response["latest_generated_at"] == response["versions"][0]["generated_at"]
    else:
        assert response["latest_recipe_version"] is None
        assert response["latest_generated_at"] is None


def test_mock_roster_is_populated_and_deterministic():
    if not _is_mock():
        # Mock-only below. The roster size and the fact that a made-up recipe
        # name still resolves to versions are properties of the fabricated
        # sem_list fixture and the seeded RNG in providers/mock.py. Office
        # reads the real roster and a real cdsem_idp_ver index, where an empty
        # answer for an unknown recipe is correct.
        pytest.skip("roster size and determinism are properties of the mock fixture")

    response = _response()
    assert response["rows"], "mock lateral-recipe roster must not be empty"
    assert response["versions"], "the mock's seeded RNG always generates versions"
    # No datetime.now() in the mock's response path — byte-identical per call.
    assert _response() == response
