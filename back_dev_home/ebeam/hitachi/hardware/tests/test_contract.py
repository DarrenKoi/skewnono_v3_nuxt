"""Contract gate for hardware. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/hardware
Office: SKEWNONO_HARDWARE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/hardware
"""

from datetime import datetime, timedelta

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.hardware import data
from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload


def test_hardware_service_matches_contract():
    end = datetime(2026, 5, 20, 9, 0)
    start = end - timedelta(days=14)
    payload = data.get_hardware_service("cdsem", "bsm", None, None, start, end)
    assert_matches(payload, HardwarePayload)
