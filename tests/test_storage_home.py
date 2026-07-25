"""Home-safe tests for the storage mock/office adapter seam.

Run only this file:
    .venv/bin/python -m pytest tests/test_storage_home.py -q

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
from back_dev_home.ebeam.hitachi.storage import data
from back_dev_home.ebeam.hitachi.storage.providers import mock as mock_provider
from back_dev_home.ebeam.hitachi.storage.routes import bp
from tests._office_state import (
    MISSING_ADAPTER_MESSAGE,
    fake_office_adapter,
    without_office_adapter,
)


_PROVIDER_ENV_NAMES = (
    "SKEWNONO_DATA_PROVIDER",
    "SKEWNONO_STORAGE_PROVIDER",
    "SKEWNONO_SEM_LIST_PROVIDER",
)

_STORAGE_FIELDS = {
    "eqp_id",
    "eqp_ip",
    "fac_id",
    "total",
    "used",
    "avail",
    "percent",
    "storage_mt",
    "rcp_counts",
    "rcp_counts_mt",
    "storage_mt_date",
    "fab_name",
    "eqp_model_cd",
}

_PPID_FIELDS = {
    "eqp_id",
    "eqp_ip",
    "fac_id",
    "fab_name",
    "eqp_model_cd",
    "missing_days_streak",
}


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


class TestStorageProviderSettings(ProviderEnvironmentTestCase):
    def test_home_default_is_mock(self):
        self.assertEqual(get_data_provider("storage"), "mock")

    def test_feature_override_wins_over_global_provider(self):
        os.environ["SKEWNONO_DATA_PROVIDER"] = "office"
        os.environ["SKEWNONO_STORAGE_PROVIDER"] = "mock"

        self.assertEqual(get_data_provider("storage"), "mock")

    def test_invalid_provider_has_a_clear_error(self):
        os.environ["SKEWNONO_STORAGE_PROVIDER"] = "unknown"

        with self.assertRaisesRegex(RuntimeError, "mock.*office"):
            get_data_provider("storage")


class TestStorageAdapters(ProviderEnvironmentTestCase):
    def test_mock_storage_rows_are_deterministic_and_match_the_contract(self):
        first = mock_provider.get_storage("cdsem")
        second = mock_provider.get_storage("cdsem")

        self.assertEqual(first, second)
        self.assertGreater(len(first), 0)
        self.assertEqual(set(first[0]), _STORAGE_FIELDS)

    def test_mock_storage_keeps_fab_name_filtering(self):
        # fab_name is the canonical filter key and is GRANULAR ("M14A"), not
        # the coarse fac_id ("M14") this test used to pass. Filtering by the
        # coarse value matches nothing.
        rows = mock_provider.get_storage("cdsem", [" m14a "])

        self.assertGreater(len(rows), 0)
        self.assertEqual({row["fab_name"] for row in rows}, {"M14A"})
        self.assertEqual({row["fac_id"] for row in rows}, {"M14"})

    def test_mock_ppid_snapshot_is_deterministic_and_matches_the_contract(self):
        first = mock_provider.get_ppid_unavailable("cdsem")
        second = mock_provider.get_ppid_unavailable("cdsem")

        self.assertEqual(first, second)
        self.assertEqual(first["latest_date"], "2026-05-26")
        self.assertGreater(len(first["rows"]), 0)
        self.assertEqual(set(first["rows"][0]), _PPID_FIELDS)

    def test_office_selection_delegates_to_the_office_adapter(self):
        storage_rows = mock_provider.get_storage("cdsem")[:1]
        ppid_snapshot = mock_provider.get_ppid_unavailable("cdsem")
        fab_names = ["M14A"]
        load_storage = MagicMock(return_value=storage_rows)
        load_ppid = MagicMock(return_value=ppid_snapshot)
        os.environ["SKEWNONO_STORAGE_PROVIDER"] = "office"

        with fake_office_adapter(
            "storage",
            get_storage=load_storage,
            get_ppid_unavailable=load_ppid,
        ):
            self.assertEqual(data.get_storage("cdsem", fab_names), storage_rows)
            self.assertEqual(
                data.get_ppid_unavailable("cdsem", fab_names),
                ppid_snapshot,
            )

        load_storage.assert_called_once_with("cdsem", fab_names)
        load_ppid.assert_called_once_with("cdsem", fab_names)

    def test_office_without_an_adapter_refuses_instead_of_serving_mock(self):
        # The one thing that must never happen at the office: an explicit
        # request for real fab data answered with fabricated numbers.
        os.environ["SKEWNONO_STORAGE_PROVIDER"] = "office"

        with without_office_adapter("storage"):
            with self.assertRaisesRegex(RuntimeError, MISSING_ADAPTER_MESSAGE):
                data.get_storage("cdsem")

            with self.assertRaisesRegex(RuntimeError, MISSING_ADAPTER_MESSAGE):
                data.get_ppid_unavailable("cdsem")


class TestStorageRoutes(ProviderEnvironmentTestCase):
    def setUp(self):
        super().setUp()
        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix="/api")
        self.client = app.test_client()

    def test_storage_route_keeps_returning_a_bare_filtered_array(self):
        # The query param is fab_name, not fac_id — routes._parse_fab_names
        # reads request.args["fab_name"], so ?fac_id=... is silently unfiltered.
        response = self.client.get("/api/cdsem/storage?fab_name=M14A")

        rows = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)
        self.assertEqual({row["fab_name"] for row in rows}, {"M14A"})

    def test_ppid_route_keeps_returning_a_snapshot(self):
        response = self.client.get("/api/cdsem/ppid-unavailable?fab_name=M14A")

        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(payload), {"latest_date", "rows"})
        self.assertTrue(all(row["fab_name"] == "M14A" for row in payload["rows"]))


if __name__ == "__main__":
    unittest.main()
