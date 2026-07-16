"""Contract gate for sem_list. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/sem_list
Office: SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/pytest back_dev_home/sem_list
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.sem_list import data
from back_dev_home.sem_list.contracts import SemListRow


def test_sem_list_matches_contract():
    rows = data.get_sem_list()
    assert_matches(rows, list[SemListRow])
    # An empty fleet is a valid office response (see MIGRATION.md), so the
    # non-empty requirement is only a mock-mode sanity check.
    if get_data_provider("sem_list") == "mock":
        assert rows, "mock sem list must not be empty"
