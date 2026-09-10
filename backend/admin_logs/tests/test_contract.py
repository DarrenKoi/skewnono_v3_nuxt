"""Contract gate for the selected demo or OpenSearch admin-log provider.

Home:   .venv/bin/pytest backend/admin_logs
Office: SKEWNONO_ADMIN_LOGS_PROVIDER=office .venv/bin/pytest backend/admin_logs

Mock always serves its deterministic in-memory rows. The tracked office
template always queries the alias selected by ``SKEWNONO_LOG_ENV``. An empty
window is valid in either provider, so this gate asserts the stable response
shape without requiring live rows.
"""

from backend._core.contract_check import assert_matches
from backend.admin_logs import data
from backend.admin_logs.contracts import LogQueryResponse


def test_query_logs_matches_contract():
    assert_matches(data.query_logs({}), LogQueryResponse)
