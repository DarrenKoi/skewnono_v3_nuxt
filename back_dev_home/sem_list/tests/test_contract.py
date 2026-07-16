"""Contract gate for sem_list. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/sem_list
Office: SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/pytest back_dev_home/sem_list
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.sem_list import data
from back_dev_home.sem_list.contracts import SemListRow


def test_sem_list_matches_contract():
    rows = data.get_sem_list()
    assert rows, "sem list must not be empty"
    assert_matches(rows, list[SemListRow])
