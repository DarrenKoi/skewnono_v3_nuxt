"""Home-safe tests for the sem_list mock/office adapter seam.

Run only this file:
    .venv/bin/python -m unittest tests.test_sem_list_home

Run the complete backend suite:
    .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from flask import Flask

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.sem_list import data
from back_dev_home.sem_list.providers import mock as mock_provider
from back_dev_home.sem_list.providers import office as office_provider
from back_dev_home.sem_list.routes import bp
from tests._office_state import has_office_adapter, skip_reason


_PROVIDER_ENV_NAMES = (
    "SKEWNONO_DATA_PROVIDER",
    "SKEWNONO_SEM_LIST_PROVIDER",
)


class ProviderEnvironmentTestCase(unittest.TestCase):
    """Give each test a clean provider environment."""

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


class TestDataProviderSettings(ProviderEnvironmentTestCase):
    def test_home_default_is_mock(self):
        self.assertEqual(get_data_provider("sem_list"), "mock")

    def test_feature_override_wins_over_global_provider(self):
        os.environ["SKEWNONO_DATA_PROVIDER"] = "office"
        os.environ["SKEWNONO_SEM_LIST_PROVIDER"] = "mock"

        self.assertEqual(get_data_provider("sem_list"), "mock")

    def test_invalid_provider_has_a_clear_error(self):
        os.environ["SKEWNONO_SEM_LIST_PROVIDER"] = "unknown"

        with self.assertRaisesRegex(RuntimeError, "mock.*office"):
            get_data_provider("sem_list")


class TestSemListAdapters(ProviderEnvironmentTestCase):
    def test_mock_rows_are_deterministic_and_match_the_contract(self):
        first = mock_provider.get_sem_list()
        second = mock_provider.get_sem_list()

        self.assertEqual(first, second)
        self.assertEqual(len(first), 300)
        self.assertEqual(set(first[0]), {
            "fac_id",
            "eqp_id",
            "eqp_model_cd",
            "eqp_grp_id",
            "vendor_nm",
            "eqp_ip",
            "fab_name",
            "updt_dt",
            "available",
            "version",
        })

    def test_office_selection_delegates_to_the_office_adapter(self):
        expected = mock_provider.get_sem_list()[:1]
        os.environ["SKEWNONO_SEM_LIST_PROVIDER"] = "office"

        with patch.object(office_provider, "get_sem_list", return_value=expected) as load:
            self.assertEqual(data.get_sem_list(), expected)

        load.assert_called_once_with()

    @unittest.skipIf(has_office_adapter("sem_list"), skip_reason("sem_list"))
    def test_unconnected_office_adapter_fails_clearly(self):
        with self.assertRaisesRegex(NotImplementedError, "not been connected"):
            office_provider.get_sem_list()


class TestSemListRoute(ProviderEnvironmentTestCase):
    def test_route_keeps_returning_a_bare_json_array(self):
        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix="/api")

        response = app.test_client().get("/api/sem-list")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.get_json(), list)
        self.assertEqual(len(response.get_json()), 300)


if __name__ == "__main__":
    unittest.main()
