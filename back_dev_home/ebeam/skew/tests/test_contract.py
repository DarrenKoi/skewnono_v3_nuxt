"""Contract gate for skew. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/skew
Office: SKEWNONO_SKEW_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/skew

providers/office_example.py is still a stub, so the office command above fails
with its NotImplementedError rather than a contract violation — that is the
adapter being unwritten, not this gate being wrong.

The matrix laws below hold under both providers because contracts.py states
them as the payload's own meaning: `tools` indexes both axes of `values`,
`values` is symmetric with a zero diagonal, and a null cell means "this pair is
not TTTM-able" rather than zero skew. The client's N배화 (maximal-clique)
grouping reads the matrix under exactly those rules, so an adapter that breaks
them produces silently wrong groups.

What is NOT provider-independent is that a fab HAS data. The mock serves one
fixture per (tool_slug, fab_name) and falls back to an `available: false`
payload with every list empty — MIGRATION.md calls that the "unknown fab" case,
not an error, and the office adapter is specified to do the same. So the office
run must not be red merely because R3 has no skew statistics yet; the
availability assumptions are fenced behind get_data_provider("skew") == "mock".
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.skew import data
from back_dev_home.ebeam.skew.contracts import SkewCheckPayload


TOOL_SLUG = "cdsem"
# The fab the mock ships a fixture for (__fixtures__/skew_cdsem_r3.json).
FAB_NAME = "R3"
# Deliberately absent from __fixtures__: the documented "unknown fab" case.
UNKNOWN_FAB = "ZZZ-NOT-A-FAB"


def _is_mock() -> bool:
    return get_data_provider("skew") == "mock"


def _payload() -> SkewCheckPayload:
    return data.get_skew_check(TOOL_SLUG, FAB_NAME, None)


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


def test_skew_check_matches_contract():
    assert_matches(_payload(), SkewCheckPayload)


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


def test_mock_serves_a_populated_fixture_for_its_known_fab():
    if not _is_mock():
        # Mock-only below. `available` and the size of the fixture are
        # properties of __fixtures__/skew_cdsem_r3.json; at the office the same
        # fab legitimately answers `available: false` with every list empty
        # until real statistics exist for it.
        pytest.skip(f"a populated {FAB_NAME} fleet is a mock fixture")

    payload = _payload()
    assert payload["available"] is True
    assert payload["tools"], "the R3 fixture must advertise a fleet"
    assert payload["occupied_cells"], "the R3 fixture must advertise cells"
    # Deliberately no assertion on the fab_name echo: skew still has a pending
    # fab_name/fac_id cleanup, and pinning the echoed value here would cement
    # whichever key the mock happens to use today.


def test_mock_unknown_fab_is_available_false_not_an_error():
    if not _is_mock():
        # Mock-only: the fallback is "fixture file missing". The office adapter
        # is specified to answer the same shape for a fab with no statistics,
        # but reaching that branch requires the company network.
        pytest.skip("the unknown-fab fallback is a missing-fixture branch")

    payload = data.get_skew_check(TOOL_SLUG, UNKNOWN_FAB, None)
    assert_matches(payload, SkewCheckPayload)
    assert payload["available"] is False
    assert payload["tools"] == []
    assert payload["occupied_cells"] == []
