"""Contract gate for tttm. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/tttm
Office: SKEWNONO_TTTM_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/tttm

providers/office_example.py is still a stub, so the office command above fails
with its NotImplementedError rather than a contract violation — that is the
adapter being unwritten, not this gate being wrong.

The matrix laws below hold under both providers because contracts.py states
them as the payload's own meaning: `tools` indexes both axes of `values`,
`values` is symmetric with a zero diagonal, and a null cell means "this pair is
not TTTM-able" rather than zero skew. The client's N배화 (maximal-clique)
grouping reads the matrix under exactly those rules, so an adapter that breaks
them produces silently wrong groups.

What is NOT provider-independent is that a fab HAS data. The mock derives its
roster from `sem_list` for the requested fab and falls back to an
`available: false` payload with every list empty when that fab holds fewer than
two tools of the family — MIGRATION.md calls that the "unknown fab" case, not
an error, and the office adapter is specified to do the same. So the office run
must not be red merely because R3 has no skew statistics yet; the availability
assumptions are fenced behind get_data_provider("tttm") == "mock".
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.tttm import data
from back_dev_home.ebeam.tttm.contracts import TttmCheckPayload, TttmRecipeList


TOOL_SLUG = "cdsem"
# A fab with a real CD-SEM fleet in sem_list (18 tools).
FAB_NAME = "R3"
# In no fleet at all: the documented "unknown fab" case.
UNKNOWN_FAB = "ZZZ-NOT-A-FAB"
# Any recipe/parameter pair: the mock folds both into its seed rather than
# holding a catalogue, and the office adapter filters real rows by them. The
# contract laws here hold for whatever the pair names.
RECIPE_ID = "CDSEM_R3_METAL1_CD"
PARAMETER = "Para_13"


def _is_mock() -> bool:
    return get_data_provider("tttm") == "mock"


def _payload() -> TttmCheckPayload:
    return data.get_tttm_check(TOOL_SLUG, FAB_NAME, None, None)


def _assert_matrix(block, label: str) -> None:
    """The symmetry/diagonal law contracts.py states for every SkewMatrixBlock."""
    tools = block["tools"]
    values = block["values"]
    assert len(values) == len(tools), f"{label}: values rows must index tools"
    for row_index, row in enumerate(values):
        assert len(row) == len(tools), f"{label}: row {row_index} is not square"
        assert row[row_index] == 0, f"{label}: diagonal [{row_index}] must be 0"
        for col_index in range(row_index):
            mirrored = values[col_index][row_index]
            assert row[col_index] == mirrored, (
                f"{label}: [{row_index}][{col_index}] != [{col_index}][{row_index}] "
                "— the skew matrix must be symmetric"
            )


def _band_bounds(band: str) -> tuple[float, float]:
    """(low, high) in nm for a `cd_band` label. High is exclusive."""
    if band.startswith("<"):
        return 0.0, float(band[1:])
    if band.startswith(">="):
        return float(band[2:]), float("inf")
    low, _, high = band.partition("-")
    return float(low), float(high)


def test_tttm_check_matches_contract():
    assert_matches(_payload(), TttmCheckPayload)


def test_median_cd_agrees_with_the_band_it_is_filed_under():
    # Provider-independent cross-field law. `cd_band` buckets the cell and
    # `median_cd_nm` is the median of the same rows, so a median outside its own
    # band means the two were computed over different row sets — which is
    # exactly the mistake an office adapter makes when it takes the band from
    # one frame and the CD from another.
    #
    # It matters because the CD, not the band, sets the PM/BM action limit
    # (1% of CD). A cell mis-filed by band still renders, just against a limit
    # drawn for the wrong pattern size, so nothing looks broken.
    payload = _payload()
    for cell in payload["occupied_cells"]:
        median = cell["median_cd_nm"]
        if median is None:
            continue  # nullable by contract: no CD came back with the stats
        low, high = _band_bounds(cell["cd_band"])
        assert median > 0, f"{cell['cell_id']}: a CD must be positive"
        assert low <= median < high, (
            f"{cell['cell_id']}: median_cd_nm {median} is outside its "
            f"cd_band {cell['cd_band']}"
        )


def test_fleet_today_median_cd_is_positive_when_present():
    # The frontend divides by 1% of this to normalise skew, so a zero or
    # negative CD produces an infinite or inverted limit rather than an error.
    median = _payload()["fleet_today"]["median_cd_nm"]
    if median is not None:
        assert median > 0


def test_current_tolerance_sits_inside_its_own_range():
    # The client renders a slider bounded by tolerance_range and pre-set to
    # current_tolerance; a value outside the range has nowhere to render.
    payload = _payload()
    bounds = payload["tolerance_range"]
    assert bounds["min"] <= payload["current_tolerance"] <= bounds["max"]
    assert bounds["step"] > 0


def test_skew_matrices_are_symmetric_with_a_zero_diagonal():
    payload = _payload()
    for cell in payload["occupied_cells"]:
        for kind in ("direct_skew_matrix", "predicted_skew_matrix"):
            block = cell[kind]
            if block is None:
                continue  # independently nullable by contract
            _assert_matrix(block, f"{cell['cell_id']}.{kind}")
    _assert_matrix(payload["fleet_today"]["matrix"], "fleet_today.matrix")


def test_the_payload_echoes_the_fab_it_was_asked_about():
    # Provider-independent: the client fires one request per fab and files the
    # response under the fab it asked for, so an adapter that echoed anything
    # else renders one fab's matrix under another's heading.
    #
    # This is the fab_name end of the fab_name/fac_id split, and skew is now
    # fab_name throughout (routes -> data -> contracts -> mock). storage is the
    # precedent for why it must be the REQUESTED key: its upstream frame
    # carried fac-level names (`M16` for `M16A`), so trusting the frame's own
    # column emptied every fab but R3. Echoing the argument is what makes that
    # class of mistake impossible here.
    assert _payload()["fab_name"] == FAB_NAME
    # Same law on the fallback path — an unknown fab still names itself rather
    # than answering with a blank or a default fab.
    unknown = data.get_tttm_check(TOOL_SLUG, UNKNOWN_FAB, None, None)
    assert unknown["fab_name"] == UNKNOWN_FAB


def test_matrix_tools_are_drawn_from_the_advertised_roster():
    # `tools` is the fleet the UI labels the axes with. A matrix naming an
    # eqp_id outside it renders an unlabelled row wherever the data came from.
    payload = _payload()
    roster = {tool["eqp_id"] for tool in payload["tools"]}
    if not roster:
        pytest.skip("active provider advertises no tools for this fab")
    assert set(payload["fleet_today"]["matrix"]["tools"]) <= roster
    for deviation in payload["fleet_today"]["consensus_deviation"]:
        assert deviation["eqp_id"] in roster


def test_the_roster_names_each_tool_once():
    # eqp_id INDEXES the matrix, so a roster naming a tool twice produces two
    # identical axes and the client's clique grouping reports a tool as
    # matching itself. sem_list's mock really does collide (it rolls ids at
    # random), and an office roster joined across two frames can hand back a
    # duplicate just as easily — so this is a law for both providers.
    ids = [tool["eqp_id"] for tool in _payload()["tools"]]
    assert len(ids) == len(set(ids)), f"duplicate eqp_id in the roster: {ids}"


def test_every_advertised_tool_carries_a_model_code():
    # The picker groups its chips by eqp_model_cd; a blank one is filed under
    # 기타 rather than dropped, but an adapter that omits the key entirely
    # breaks the group row itself.
    for tool in _payload()["tools"]:
        assert tool["eqp_model_cd"] is not None


def test_mock_derives_its_fleet_from_sem_list():
    if not _is_mock():
        # Mock-only: at the office the roster comes from the skew statistics
        # themselves, and a tool that has not been measured legitimately never
        # appears even though sem_list knows about it.
        pytest.skip("deriving the roster from sem_list is a mock property")

    from back_dev_home.ebeam._tool_specs import SLUG_TO_TOOL_TYPE, model_to_tool_type
    from back_dev_home.sem_list.providers.mock import get_sem_list

    payload = _payload()
    assert payload["available"] is True
    assert payload["occupied_cells"], "a populated fab must advertise cells"

    expected = {
        row["eqp_id"] for row in get_sem_list()
        if row["fab_name"].upper() == FAB_NAME
        and model_to_tool_type(row["eqp_model_cd"]) == SLUG_TO_TOOL_TYPE[TOOL_SLUG]
    }
    # Equality, not containment: the point of deriving from sem_list is that
    # the skew screen offers the SAME tools every other screen shows for this
    # fab. A subset would silently hide a tool from comparison.
    assert {tool["eqp_id"] for tool in payload["tools"]} == expected


def test_mock_a_fab_with_one_tool_is_not_a_comparison():
    if not _is_mock():
        pytest.skip("the one-tool fleet is a mock roster property")

    # HV-SEM in M10B holds a single tool in sem_list. One tool has no pairwise
    # skew at all, so the payload must say unavailable rather than ship a 1x1
    # matrix the frontend would render as a comparison of nothing.
    payload = data.get_tttm_check("hvsem", "M10B", None, None)
    assert_matches(payload, TttmCheckPayload)
    assert payload["available"] is False
    # The MATRIX is what must stay empty — that is the "comparison of nothing"
    # this branch exists to refuse. The ROSTER is a different fact and is kept:
    # the client builds its tool picker from it, and a fab that holds one tool
    # should say so rather than render as a fab that holds none.
    assert payload["fleet_today"]["matrix"]["tools"] == []
    assert payload["occupied_cells"] == []
    assert [tool["eqp_id"] for tool in payload["tools"]] != []


def test_mock_unknown_fab_is_available_false_not_an_error():
    if not _is_mock():
        # Mock-only: the fallback is "no tool of this family in that fab". The
        # office adapter is specified to answer the same shape for a fab with
        # no statistics, but reaching that branch requires the company network.
        pytest.skip("the unknown-fab fallback is an empty-roster branch")

    payload = data.get_tttm_check(TOOL_SLUG, UNKNOWN_FAB, None, None)
    assert_matches(payload, TttmCheckPayload)
    assert payload["available"] is False
    assert payload["tools"] == []
    assert payload["occupied_cells"] == []


def test_the_payload_echoes_the_parameter_it_was_asked_about():
    # Same law as the fab echo above, and for the same reason: the client files
    # the response under the (recipe, parameter) it asked for. The parameter is
    # what the grouping verdict is ABOUT — "these tools agree on this feature" —
    # so a payload echoing a different parameter labels one feature's group
    # with another feature's name, and nothing about it looks wrong.
    payload = data.get_tttm_check(TOOL_SLUG, FAB_NAME, RECIPE_ID, PARAMETER)
    assert payload["recipe_id"] == RECIPE_ID
    assert payload["parameter"] == PARAMETER
    # The unfiltered case says so explicitly rather than omitting the key.
    assert _payload()["parameter"] is None


def test_recipe_list_matches_contract():
    assert_matches(data.get_tttm_recipes(TOOL_SLUG, FAB_NAME), TttmRecipeList)


def test_every_offered_recipe_has_evidence_behind_it():
    # The whole point of sourcing this list from measurement history rather
    # than the recipe catalogue: a row that exists must have been measured, so
    # picking it cannot answer "no data". True of both providers.
    payload = data.get_tttm_recipes(TOOL_SLUG, FAB_NAME)
    for row in payload["rows"]:
        assert row["runs"] >= 1, f"{row['recipe_id']} is offered with no runs"
        assert row["tools"] >= 1, f"{row['recipe_id']} is offered with no tools"
        assert row["recipe_id"], "a recipe must name itself"


def test_recipe_list_is_ordered_by_evidence():
    # The picker keeps server order, so the recipes that can actually support a
    # comparison have to come first — a recipe only one tool ran can never
    # produce a direct pair however many runs it has.
    rows = data.get_tttm_recipes(TOOL_SLUG, FAB_NAME)["rows"]
    keys = [(-row["tools"], -row["runs"], row["recipe_id"]) for row in rows]
    assert keys == sorted(keys)


def test_recipe_list_names_each_recipe_once():
    rows = data.get_tttm_recipes(TOOL_SLUG, FAB_NAME)["rows"]
    ids = [row["recipe_id"] for row in rows]
    assert len(ids) == len(set(ids)), f"duplicate recipe_id: {ids}"


def test_an_unknown_fab_offers_no_recipes():
    payload = data.get_tttm_recipes(TOOL_SLUG, UNKNOWN_FAB)
    assert_matches(payload, TttmRecipeList)
    assert payload["rows"] == []
    assert payload["fab_name"] == UNKNOWN_FAB


def test_mock_recipe_list_is_exactly_what_meas_hist_measured():
    if not _is_mock():
        # Mock-only: the office reads the same fact from meas_hist_* directly.
        # At home the two must agree exactly, because a picker offering a
        # recipe the check has no rows for is the failure this endpoint exists
        # to remove.
        pytest.skip("the mock's measured set is meas_hist's, by construction")

    from back_dev_home.ebeam._tool_specs import SLUG_TO_TOOL_TYPE
    from back_dev_home.meas_hist.providers.mock import get_meas_hist

    measured = {
        row.get("full_name") or row["recipe_name"]
        for row in get_meas_hist(
            tool_type=SLUG_TO_TOOL_TYPE[TOOL_SLUG], fab_name=FAB_NAME
        )["rows"]
    }
    offered = {row["recipe_id"] for row in data.get_tttm_recipes(TOOL_SLUG, FAB_NAME)["rows"]}
    assert offered == measured


def test_mock_an_unmeasured_recipe_is_unavailable_but_keeps_the_roster():
    """A recipe this fab never ran cannot be compared — and must say so.

    The office reaches this through `recent_runs` coming back empty for the
    recipe filter. It is the branch a STALE STORED RECIPE lands on: the picker
    was re-sourced from meas_hist, so a recipe_id persisted while it still read
    recipe-search's catalogue names something nobody measured.

    The roster is asserted because losing it is what made this unrecoverable on
    screen — the tool picker and the recipe picker share one rail, so a payload
    with no tools left the user looking at an empty control panel with no way
    to pick a different recipe.
    """
    if not _is_mock():
        pytest.skip("reaching the office's empty-runs branch needs the network")

    payload = data.get_tttm_check(TOOL_SLUG, FAB_NAME, "CD_MONITOR/NEVER_MEASURED_XYZ", None)
    assert_matches(payload, TttmCheckPayload)
    assert payload["available"] is False
    assert payload["occupied_cells"] == []
    assert [tool["eqp_id"] for tool in payload["tools"]] != []
    # Echoed on this branch too, so the client can file the answer under the
    # recipe it asked about rather than under "no recipe".
    assert payload["recipe_id"] == "CD_MONITOR/NEVER_MEASURED_XYZ"


def test_mock_every_recipe_the_picker_offers_is_actually_comparable():
    """The picker's list and the check's answer must agree on "measured".

    Sourcing the picker from meas_hist only helps if the check accepts what the
    picker offers. If these two ever computed the measured set differently, the
    picker would hand the user recipes that answer unavailable — the failure
    the re-sourcing was done to remove, reintroduced from the other side.
    """
    if not _is_mock():
        pytest.skip("the mock derives both sides from the same meas_hist mock")

    rows = data.get_tttm_recipes(TOOL_SLUG, FAB_NAME)["rows"]
    assert rows, "the fab must offer some measured recipe for this to mean anything"
    for row in rows[:5]:
        payload = data.get_tttm_check(TOOL_SLUG, FAB_NAME, row["recipe_id"], None)
        assert payload["available"] is True, row["recipe_id"]


# ── parameters: the catalogue the payload carries ─────────────────────────


def _measured_recipe() -> str:
    """A recipe the fab actually measured — the only kind the picker offers."""
    rows = data.get_tttm_recipes(TOOL_SLUG, FAB_NAME)["rows"]
    assert rows, "the fab must have measured something for this test to mean anything"
    return rows[0]["recipe_id"]


def test_a_recipe_payload_lists_the_parameters_it_measured():
    # The parameter picker is fed from THIS list, not from recipe-open over
    # FTP: the names come out of the same measurement rows the skew does, so a
    # name offered here is one the filter can actually match.
    payload = data.get_tttm_check(TOOL_SLUG, FAB_NAME, _measured_recipe(), None)
    names = payload["parameters"]
    assert names, "a measured recipe carries at least one measured parameter"
    assert names == sorted(set(names)), "sorted and without duplicates"
    assert all(isinstance(name, str) and name for name in names)


def test_without_a_recipe_there_is_no_parameter_list():
    # A parameter name is recipe-local, so a list spanning every measured recipe
    # would offer names that mean different features in different recipes.
    assert _payload()["parameters"] == []


def test_the_parameter_list_does_not_move_with_the_parameter_filter():
    # The list is the catalogue the filter is picked FROM; a filter that
    # narrowed its own catalogue would leave the picker one entry long.
    recipe = _measured_recipe()
    unfiltered = data.get_tttm_check(TOOL_SLUG, FAB_NAME, recipe, None)["parameters"]
    filtered = data.get_tttm_check(TOOL_SLUG, FAB_NAME, recipe, unfiltered[0])["parameters"]
    assert filtered == unfiltered


@pytest.mark.skipif(not _is_mock(), reason="mock-only data assumption")
def test_mock_an_unavailable_answer_carries_no_parameter_list():
    payload = data.get_tttm_check(TOOL_SLUG, UNKNOWN_FAB, _measured_recipe(), None)
    assert payload["available"] is False
    assert payload["parameters"] == []
