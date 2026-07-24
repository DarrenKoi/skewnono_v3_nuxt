"""Home-safe contract coverage for Recipe TAT and Fail Issue analytics."""

from __future__ import annotations

import os
import unittest

from flask import Flask

from back_dev_home.ebeam.hitachi.fail_issue.data import (
    get_anchor_time as get_fail_issue_anchor_time,
)
from back_dev_home.ebeam.hitachi.fail_issue.routes import bp as fail_issue_bp
from back_dev_home.ebeam.hitachi.recipe_tat.data import (
    get_anchor_time as get_recipe_tat_anchor_time,
)
from back_dev_home.ebeam.hitachi.recipe_tat.routes import bp as recipe_tat_bp
from tests._office_state import MISSING_ADAPTER_MESSAGE, has_office_adapter, skip_reason


class TestRecipeAnalyticsRoutes(unittest.TestCase):
    def setUp(self):
        self._providers = {
            key: os.environ.pop(key, None)
            for key in (
                "SKEWNONO_RECIPE_TAT_PROVIDER",
                "SKEWNONO_FAIL_ISSUE_PROVIDER",
            )
        }
        app = Flask(__name__)
        app.register_blueprint(recipe_tat_bp, url_prefix="/api")
        app.register_blueprint(fail_issue_bp, url_prefix="/api")
        self.client = app.test_client()

    def tearDown(self):
        for key, value in self._providers.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_recipe_tat_routes_keep_their_wire_shapes(self):
        summary = self.client.get("/api/cdsem/recipe-tat/summary").get_json()
        ranking = self.client.get(
            "/api/cdsem/recipe-tat/ranking?limit=3"
        ).get_json()
        trend = self.client.get("/api/cdsem/recipe-tat/daily-trend").get_json()
        devices = self.client.get("/api/cdsem/recipe-tat/devices").get_json()

        self.assertEqual(summary["tool_type"], "cd-sem")
        self.assertGreater(summary["total_executions"], 0)
        self.assertEqual(ranking["limit"], 3)
        self.assertLessEqual(len(ranking["rows"]), 3)
        self.assertEqual(set(trend), {
            "tool_type", "fab_name", "start_date", "end_date", "lot_cd", "points"
        })
        self.assertEqual(set(devices), {
            "tool_type", "fab_name", "start_date", "end_date", "devices"
        })

    def test_fail_issue_routes_keep_their_wire_shapes(self):
        summary = self.client.get("/api/hvsem/fail-issue/summary").get_json()
        align = self.client.get(
            "/api/hvsem/fail-issue/align-ranking?limit=2"
        ).get_json()
        meas = self.client.get(
            "/api/hvsem/fail-issue/meas-ranking?limit=2"
        ).get_json()

        self.assertEqual(summary["tool_type"], "hv-sem")
        self.assertIn("meas_fail_threshold", summary)
        self.assertEqual(align["limit"], 2)
        self.assertEqual(meas["limit"], 2)
        self.assertLessEqual(len(align["rows"]), 2)
        self.assertLessEqual(len(meas["rows"]), 2)

    def test_shared_scope_rules_remain_stable(self):
        invalid_limit = self.client.get(
            "/api/cdsem/recipe-tat/ranking?limit=not-a-number"
        ).get_json()
        capped_limit = self.client.get(
            "/api/cdsem/fail-issue/align-ranking?limit=999999"
        ).get_json()
        bad_slug = self.client.get("/api/unknown/recipe-tat/summary")

        # limit is no longer capped at 1000. DEFAULT_LIMIT is 0, which means
        # "no cap" (_analytics_routes.py:16-18) so a fleet-wide range never
        # silently drops the tail of the ranking. An unparseable limit falls
        # back to that default; a large one is honoured rather than clamped.
        self.assertEqual(invalid_limit["limit"], 0)
        self.assertEqual(capped_limit["limit"], 999999)
        self.assertEqual(bad_slug.status_code, 400)
        self.assertEqual(
            bad_slug.get_json(),
            {"error": "tool_slug must be 'cdsem' or 'hvsem'"},
        )

    def test_lot_scope_is_applied_consistently(self):
        devices = self.client.get("/api/cdsem/recipe-tat/devices").get_json()[
            "devices"
        ]
        self.assertGreater(len(devices), 0)
        lot_cd = devices[0]["lot_cd"]

        summary = self.client.get(
            f"/api/cdsem/recipe-tat/summary?lot_cd={lot_cd}"
        ).get_json()
        fail_summary = self.client.get(
            f"/api/cdsem/fail-issue/summary?lot_cd={lot_cd}"
        ).get_json()

        self.assertGreater(summary["total_executions"], 0)
        self.assertGreater(fail_summary["total_executions"], 0)

    # Split in two: recipe_tat has a real adapter on some checkouts and
    # fail_issue does not, so they assert different halves of the contract and
    # cannot share a skip guard.
    @unittest.skipIf(
        has_office_adapter("ebeam/hitachi/recipe_tat"),
        skip_reason("ebeam/hitachi/recipe_tat"),
    )
    def test_unconnected_recipe_tat_adapter_fails_explicitly(self):
        os.environ["SKEWNONO_RECIPE_TAT_PROVIDER"] = "office"
        with self.assertRaisesRegex(RuntimeError, MISSING_ADAPTER_MESSAGE):
            get_recipe_tat_anchor_time()

    def test_unconnected_fail_issue_adapter_fails_explicitly(self):
        os.environ["SKEWNONO_FAIL_ISSUE_PROVIDER"] = "office"
        with self.assertRaisesRegex(RuntimeError, MISSING_ADAPTER_MESSAGE):
            get_fail_issue_anchor_time()


if __name__ == "__main__":
    unittest.main()
