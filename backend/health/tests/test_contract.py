"""Contract gate for health. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest backend/health
Office: SKEWNONO_HEALTH_PROVIDER=office .venv/bin/pytest backend/health
"""

from backend._core.contract_check import assert_matches
from backend.health import data
from backend.health.contracts import ServicesHealthResponse


def test_get_services_health_matches_contract():
    assert_matches(data.get_services_health(), ServicesHealthResponse)
