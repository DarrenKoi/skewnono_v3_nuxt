"""Contract gate for the selected demo or OpenSearch admin-log provider.

Home:   .venv/bin/pytest back_dev_home/admin_logs
Office: SKEWNONO_ADMIN_LOGS_PROVIDER=office .venv/bin/pytest back_dev_home/admin_logs

Mock always serves its deterministic in-memory rows. The tracked office
template always queries the alias selected by ``SKEWNONO_LOG_ENV``. An empty
window is valid in either provider, so this gate asserts the stable response
shape without requiring live rows.
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.admin_logs import data
from back_dev_home.admin_logs.contracts import LogQueryResponse


def test_query_logs_matches_contract():
    assert_matches(data.query_logs({}), LogQueryResponse)
