"""MOCK-ONLY invariants for lateral_recipe. Imports providers.mock directly.

The sibling test_contract.py is the provider-independent gate (runs via
data.py) — do not merge these files. What is pinned here is a property of the
Phase 1 fixture universe, not of the office indices: at the office a recipe
really can be removed from a tool that measured it last week, so
`measured ⊆ ready` is a mock guarantee only.
"""

from back_dev_home.ebeam.hitachi.lateral_recipe.providers.mock import get_lateral_recipe
from back_dev_home.meas_hist.providers.mock import get_meas_hist


# Fabs and recipes wide enough that both tool families and a recipe the mock
# universe has never heard of (→ synthesized 측정 이력) are covered.
_FABS = ("M11A", "M14A", "M14B", "M15", "M16", "R3")
_RECIPES = (
    "ADI_CD_BIAS_001",
    "CNT_HOLE_001",
    "QC_DAILY_MATCH_001",
    "GATE_PITCH_001",
    "NO_SUCH_RECIPE_0001",
)


def test_measured_tools_are_never_listed_as_not_ready():
    """측정했으면 보유 — 횡전개 must not contradict 측정 이력.

    Both views take the same (tool_type, fab_name, recipe_name), so a tool
    showing measurement rows on one screen and 미보유 on the other is a mock
    self-contradiction, not a data finding.
    """
    for tool_type in ("cd-sem", "hv-sem"):
        for fab_name in _FABS:
            for recipe_name in _RECIPES:
                response = get_lateral_recipe(tool_type, fab_name, recipe_name)
                if response["total_tools_in_fab"] == 0:
                    continue

                measured = {row["eqp_id"] for row in get_meas_hist(tool_type, fab_name, recipe_name)["rows"]}
                not_ready = {row["eqp_id"] for row in response["rows"] if not row["recipe_ready"]}

                assert not (measured & not_ready), (
                    f"{tool_type}/{fab_name}/{recipe_name}: "
                    f"{sorted(measured & not_ready)} have 측정 이력 but are listed 미보유"
                )


def test_version_cards_account_for_every_ready_tool():
    """Each version card's ready_count must be countable in the table below it."""
    for tool_type in ("cd-sem", "hv-sem"):
        for fab_name in _FABS:
            for recipe_name in _RECIPES:
                response = get_lateral_recipe(tool_type, fab_name, recipe_name)

                assert response["ready_count"] + response["not_ready_count"] == response["total_tools_in_fab"]
                assert sum(v["ready_count"] for v in response["versions"]) == response["ready_count"]


def test_ready_rows_always_carry_a_version():
    """A 보유 row with no version would land in the frontend's 'version 미상' bucket."""
    response = get_lateral_recipe("cd-sem", "M14B", "ADI_CD_BIAS_001")

    for row in response["rows"]:
        if row["recipe_ready"]:
            assert row["recipe_version"] is not None
            assert row["recipe_generated_at"] is not None
        else:
            assert row["recipe_version"] is None
            assert row["recipe_generated_at"] is None
