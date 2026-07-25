"""Contract gate for pm_planning. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/pm_planning
Office: SKEWNONO_PM_PLANNING_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/pm_planning

providers/office_example.py is still a stub, so the office command above fails
with its NotImplementedError rather than a contract violation — that is the
adapter being unwritten, not this gate being wrong. Everything asserted here is
written to survive the day it becomes real.

The shape checks and the cell/axis-coverage laws hold under both providers:
MIGRATION.md requires the office adapter to ship RAW per-tool values with no
pre-ranking and no threshold filtering, keyed on the same beam/axis grid the
payload advertises. What is NOT provider-independent is the SIZE of the fleet
and the mock's frozen clock, so those are fenced behind
get_data_provider("pm_planning") == "mock".
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.pm_planning import data
from back_dev_home.ebeam.hitachi.pm_planning.contracts import FleetPayload


# fab_name copied from routes.py's own call shape (a plain query-string
# fab_name, upper/lower-cased by the mock — see pm_planning_fleet() in
# routes.py, which just forwards request.args["fab_name"] unchanged).
FAB_NAME = "M14"


def _is_mock() -> bool:
    return get_data_provider("pm_planning") == "mock"


def test_get_pm_planning_fleet_matches_contract():
    assert_matches(data.get_pm_planning_fleet(FAB_NAME), FleetPayload)


def test_every_cell_uses_an_advertised_beam_and_axis():
    # The client pivots `cells` against `beam_conditions` x `axes` to lay the
    # grid out; a cell keyed outside that grid silently disappears from the
    # screen. True of any adapter, so it stays unfenced.
    fleet = data.get_pm_planning_fleet(FAB_NAME)
    beams = set(fleet["beam_conditions"])
    axes = set(fleet["axes"])
    assert beams and axes, "the payload must advertise its own grid"

    for tool in fleet["tools"]:
        seen = set()
        for cell in tool["cells"]:
            assert cell["beam"] in beams, f"{tool['eqp_id']}: unknown beam {cell['beam']!r}"
            assert cell["axis"] in axes, f"{tool['eqp_id']}: unknown axis {cell['axis']!r}"
            key = (cell["beam"], cell["axis"])
            assert key not in seen, f"{tool['eqp_id']}: duplicate cell {key}"
            seen.add(key)

    for cell in fleet["consensus"]:
        assert cell["beam"] in beams
        assert cell["axis"] in axes


def test_gate_spec_window_is_ordered():
    # cd_in_spec is the verdict the Up-gate is read off, so a lower bound above
    # the upper bound would make every tool fail for a reason nobody can see.
    for tool in data.get_pm_planning_fleet(FAB_NAME)["tools"]:
        gate = tool["gate"]
        assert gate["cd_spec_lower"] <= gate["cd_spec_upper"]


def test_mock_derives_cd_in_spec_from_the_window():
    if not _is_mock():
        # Mock-only: providers/mock.py computes cd_in_spec as an INCLUSIVE
        # comparison against its own spec window. Neither contracts.py nor
        # MIGRATION.md says how office derives it — an ingested verdict with an
        # exclusive bound, a guard band, or its own rounding would be
        # legitimate and would fail this equality on a boundary tool.
        pytest.skip("cd_in_spec derivation is only specified for the mock")

    for tool in data.get_pm_planning_fleet(FAB_NAME)["tools"]:
        gate = tool["gate"]
        assert gate["cd_in_spec"] == (
            gate["cd_spec_lower"] <= gate["cd_monitoring_value"] <= gate["cd_spec_upper"]
        )


def test_mock_fleet_is_a_complete_frozen_snapshot():
    if not _is_mock():
        # Mock-only below: the fleet roster, the full beam x axis product per
        # tool, and the frozen FETCHED_AT are all fabricated in
        # providers/mock.py. A real fab can hold any number of tools, and a
        # tool missing a cell (no data for that beam/axis yet) is normal.
        pytest.skip("fleet size and the frozen clock are mock fixtures")

    fleet = data.get_pm_planning_fleet(FAB_NAME)
    assert fleet["fab_name"] == FAB_NAME.upper(), "the mock echoes fab_name upper-cased"
    assert fleet["tools"], "mock fleet must not be empty"

    expected_cells = len(fleet["beam_conditions"]) * len(fleet["axes"])
    for tool in fleet["tools"]:
        assert len(tool["cells"]) == expected_cells
        assert tool["epoch_history"], "mock tools carry a fabricated epoch history"

    # consensus is a fleet-wide median taken after every tool exists, so the
    # mock covers the whole grid exactly once.
    assert len(fleet["consensus"]) == expected_cells

    # Byte-identical per fab within a process (md5-seeded, frozen NOW).
    assert data.get_pm_planning_fleet(FAB_NAME) == fleet
