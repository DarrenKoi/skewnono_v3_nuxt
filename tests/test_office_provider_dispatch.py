"""Tests for provider-backed features that follow the sem_list dispatch seam.

Requires `hardware` and `tttm` office adapters. Both `providers/office.py`
files are gitignored (created at the office with
`cp office_example.py office.py`), so on a checkout without them this module
SKIPS rather than failing collection — a missing adapter is the documented
default state, not a broken test.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests._office_state import has_office_adapter

_REQUIRED = ("ebeam/hardware", "ebeam/tttm")
_missing = [feature for feature in _REQUIRED if not has_office_adapter(feature)]
if _missing:
    pytest.skip(
        "no providers/office.py for: "
        + ", ".join(_missing)
        + " (gitignored; created at the office)",
        allow_module_level=True,
    )

from back_dev_home.ebeam.hardware import data as hardware_data
from back_dev_home.ebeam.hardware.providers import mock as hardware_mock
from back_dev_home.ebeam.hardware.providers import office as hardware_office
from back_dev_home.ebeam.tttm import data as tttm_data
from back_dev_home.ebeam.tttm.providers import mock as tttm_mock
from back_dev_home.ebeam.tttm.providers import office as tttm_office


_PROVIDER_ENV_NAMES = (
    "SKEWNONO_DATA_PROVIDER",
    "SKEWNONO_HARDWARE_PROVIDER",
    "SKEWNONO_TTTM_PROVIDER",
)


class ProviderEnvironmentTestCase(unittest.TestCase):
    def setUp(self):
        self._original_env = {
            name: os.environ.get(name)
            for name in _PROVIDER_ENV_NAMES
        }
        for name in _PROVIDER_ENV_NAMES:
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self._original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class TestCommonProviderDispatch(ProviderEnvironmentTestCase):
    def test_global_office_provider_selects_hardware_and_tttm_adapters(self):
        os.environ["SKEWNONO_DATA_PROVIDER"] = "office"
        now = datetime(2026, 7, 15, tzinfo=timezone.utc)
        hardware_payload = {"source": "hardware-office"}
        tttm_payload = {"source": "tttm-office"}

        with (
            patch.object(
                hardware_office,
                "get_hardware_service",
                return_value=hardware_payload,
            ) as load_hardware,
            patch.object(
                tttm_office,
                "get_tttm_check",
                return_value=tttm_payload,
            ) as load_tttm,
        ):
            self.assertIs(
                hardware_data.get_hardware_service(
                    "cdsem", "bsm", "ECDX123", "M16A", now, now
                ),
                hardware_payload,
            )
            self.assertIs(
                tttm_data.get_tttm_check("cdsem", "R3", "RECIPE-1"),
                tttm_payload,
            )

        load_hardware.assert_called_once_with(
            "cdsem", "bsm", "ECDX123", "M16A", now, now
        )
        load_tttm.assert_called_once_with("cdsem", "R3", "RECIPE-1")

    def test_feature_mock_override_wins_over_global_office_provider(self):
        os.environ["SKEWNONO_DATA_PROVIDER"] = "office"
        os.environ["SKEWNONO_HARDWARE_PROVIDER"] = "mock"
        os.environ["SKEWNONO_TTTM_PROVIDER"] = "mock"
        now = datetime(2026, 7, 15, tzinfo=timezone.utc)
        hardware_payload = {"source": "hardware-mock"}
        tttm_payload = {"source": "tttm-mock"}

        with (
            patch.object(
                hardware_mock,
                "get_hardware_service",
                return_value=hardware_payload,
            ),
            patch.object(
                tttm_mock,
                "get_tttm_check",
                return_value=tttm_payload,
            ),
        ):
            self.assertIs(
                hardware_data.get_hardware_service(
                    "cdsem", "bsm", "ECDX123", "M16A", now, now
                ),
                hardware_payload,
            )
            self.assertIs(
                tttm_data.get_tttm_check("cdsem", "R3", None),
                tttm_payload,
            )


if __name__ == "__main__":
    unittest.main()
