"""Home-safe tests for the sem_list mock/office adapter seam.

Run only this file:
    .venv/bin/python -m pytest tests/test_sem_list_home.py -q

Run the complete backend suite:
    .venv/bin/python -m pytest tests back_dev_home -q

`unittest discover tests` also runs this file, but it is NOT the suite: it
sees nothing under `back_dev_home/**/tests/`, where most of the backend tests
now live as pytest functions.

Nothing here imports `providers.office`: that module is gitignored, so a
module-level import fails collection on every clean checkout. The office
dispatch branch goes through `_office_state`'s fakes instead, which assert
the same thing on a wired machine and an unwired one.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

from flask import Flask

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.sem_list import data
from back_dev_home.sem_list.providers import mock as mock_provider
from back_dev_home.sem_list.routes import bp
from tests._office_state import (
    MISSING_ADAPTER_MESSAGE,
    fake_office_adapter,
    without_office_adapter,
)


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
        load = MagicMock(return_value=expected)
        os.environ["SKEWNONO_SEM_LIST_PROVIDER"] = "office"

        with fake_office_adapter("sem_list", get_sem_list=load):
            self.assertEqual(data.get_sem_list(), expected)

        load.assert_called_once_with()

    def test_office_without_an_adapter_refuses_instead_of_serving_mock(self):
        # The one thing that must never happen at the office: an explicit
        # request for real fab data answered with fabricated numbers.
        os.environ["SKEWNONO_SEM_LIST_PROVIDER"] = "office"

        with without_office_adapter("sem_list"):
            with self.assertRaisesRegex(RuntimeError, MISSING_ADAPTER_MESSAGE):
                data.get_sem_list()


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
