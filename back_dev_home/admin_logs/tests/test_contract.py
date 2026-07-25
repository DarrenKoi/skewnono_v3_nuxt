"""Contract gate for admin_logs. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/admin_logs
Office: SKEWNONO_ADMIN_LOGS_PROVIDER=office .venv/bin/pytest back_dev_home/admin_logs

Nothing here is fenced behind the provider, and deliberately so: an empty log
window is a valid response in both phases (MIGRATION.md), so the contract shape
is the whole of what this gate can honestly assert. Note also that "mock" is
not a synonym for "fabricated" in this feature — providers/mock.py serves its
5-row demo dataset only while OPENSEARCH_PASSWORD is unset, and queries the
real skewnono_logging index once it is set. A fence keyed on
get_data_provider("admin_logs") would therefore not separate fabricated data
from real data here.
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.admin_logs import data
from back_dev_home.admin_logs.contracts import LogQueryResponse


def test_query_logs_matches_contract():
    assert_matches(data.query_logs({}), LogQueryResponse)
