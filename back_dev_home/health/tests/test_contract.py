"""Contract gate for health. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/health
Office: SKEWNONO_HEALTH_PROVIDER=office .venv/bin/pytest back_dev_home/health
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.health import data
from back_dev_home.health.contracts import ServicesHealthResponse


def test_get_services_health_matches_contract():
    assert_matches(data.get_services_health(), ServicesHealthResponse)
