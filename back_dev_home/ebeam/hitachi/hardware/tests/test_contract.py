"""Contract gate for hardware. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/hardware
Office: SKEWNONO_HARDWARE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/hardware
"""

from datetime import datetime, timedelta

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.hardware import data
from back_dev_home.ebeam.hitachi.hardware.contracts import (
    VALID_SERVICES,
    HardwarePayload,
)


@pytest.mark.parametrize("service", sorted(VALID_SERVICES))
def test_hardware_service_matches_contract(service):
    # Exercise every service (bsm/reso-center/fdc/mdc/sce/bm-pm/sharpness) with
    # a concrete equipment id, not just the empty bsm path — each service has
    # its own docs/settings/availability shape that must satisfy the contract.
    end = datetime(2026, 5, 20, 9, 0)
    start = end - timedelta(days=14)
    payload = data.get_hardware_service("cdsem", service, "CDX001", "R3", start, end)
    assert_matches(payload, HardwarePayload)
