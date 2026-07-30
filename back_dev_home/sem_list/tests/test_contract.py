"""Contract gate for sem_list. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/sem_list
Office: SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/pytest back_dev_home/sem_list
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.sem_list import data
from back_dev_home.sem_list.contracts import PendingToolRow, SemListRow


def test_sem_list_matches_contract():
    rows = data.get_sem_list()
    assert_matches(rows, list[SemListRow])
    # An empty fleet is a valid office response (see MIGRATION.md), so the
    # non-empty requirement is only a mock-mode sanity check.
    if get_data_provider("sem_list") == "mock":
        assert rows, "mock sem list must not be empty"


def test_pending_tools_matches_contract():
    rows = data.get_pending_tools()
    assert_matches(rows, list[PendingToolRow])
    if get_data_provider("sem_list") == "mock":
        assert rows, "mock pending tools must not be empty"


def test_pending_tools_are_disjoint_from_the_connected_fleet():
    # The whole feature is a set difference. If a tool could appear in both,
    # the screen would ask IT to open a firewall for a tool already reachable.
    connected = {row["eqp_id"] for row in data.get_sem_list()}
    pending = {row["eqp_id"] for row in data.get_pending_tools()}
    assert connected & pending == set()


def test_every_pending_tool_has_an_ip():
    # Every tool is assigned an IP when it is installed in the fab
    # (user-confirmed 2026-07-30). The IP is the payload of the IT request, so
    # a blank one makes the row useless rather than merely incomplete.
    for row in data.get_pending_tools():
        assert row["eqp_ip"], f"{row['eqp_id']} has no eqp_ip"


def test_connected_fleet_size_is_unchanged():
    if get_data_provider("sem_list") == "mock":
        assert len(data.get_sem_list()) == 300
