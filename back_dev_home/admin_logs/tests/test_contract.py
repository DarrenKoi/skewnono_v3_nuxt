"""Contract gate for admin_logs. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/admin_logs
Office: SKEWNONO_ADMIN_LOGS_PROVIDER=office .venv/bin/pytest back_dev_home/admin_logs
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.admin_logs import data
from back_dev_home.admin_logs.contracts import LogQueryResponse


def test_query_logs_matches_contract():
    assert_matches(data.query_logs({}), LogQueryResponse)
