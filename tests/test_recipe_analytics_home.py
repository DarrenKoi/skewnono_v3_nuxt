"""Home-safe contract coverage for Recipe TAT and Fail Issue analytics."""

from __future__ import annotations

import os
import unittest

from flask import Flask

from back_dev_home.ebeam._office_meas_hist import FAB_NAME_KW, filter_clauses
from back_dev_home.ebeam.fail_issue.data import (
    get_anchor_time as get_fail_issue_anchor_time,
)
from back_dev_home.ebeam.fail_issue.routes import bp as fail_issue_bp
from back_dev_home.ebeam.recipe_tat.data import (
    get_anchor_time as get_recipe_tat_anchor_time,
)
from back_dev_home.ebeam.recipe_tat.routes import bp as recipe_tat_bp
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
            "tool_type", "fab_names", "start_date", "end_date", "lot_cd", "points"
        })
        self.assertEqual(set(devices), {
            "tool_type", "fab_names", "start_date", "end_date", "devices"
        })

    def test_equipment_compare_route_forwards_the_requested_eqp_ids(self):
        # 라우트가 scope.eqp_ids 를 잊거나 순서를 바꿔 넘기면, 위치로 읽히는
        # cells 가 다른 장비 열 아래에 그려집니다. 표에서 고른 순서와 **반대로**
        # 요청해, 라우트가 목록을 실제로 실어 나르는지 확인합니다.
        table = self.client.get("/api/cdsem/recipe-tat/equipments").get_json()
        picked = [row["eqp_id"] for row in table["equipments"][:2]]
        self.assertEqual(len(picked), 2)
        requested = list(reversed(picked))

        payload = self.client.get(
            "/api/cdsem/recipe-tat/equipment-compare?eqp_id=" + ",".join(requested)
        ).get_json()

        self.assertEqual(payload["eqp_ids"], requested)
        self.assertEqual([s["eqp_id"] for s in payload["trends"]], requested)
        self.assertTrue(payload["recipes"])
        for row in payload["recipes"]:
            self.assertEqual([c["eqp_id"] for c in row["cells"]], requested)

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

    def test_every_analytics_endpoint_rejects_an_unknown_tool_slug(self):
        """Scope resolution is shared, so this is cheap — but the contract
        tests are the mock->office swap guard, and the office adapter has to
        reproduce the same 400 on every route. An endpoint with no assertion
        here is where the two adapters are free to diverge quietly.

        The equipment routes are the ones this covers that /summary did not;
        fail-issue's twins are included because they resolve scope through the
        very same helper and cost nothing to pin.
        """
        paths = (
            "/api/unknown/recipe-tat/equipments",
            "/api/unknown/recipe-tat/equipment-compare",
            "/api/unknown/fail-issue/equipments",
            "/api/unknown/fail-issue/equipment-compare",
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.get_json(),
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

    def test_comma_fab_names_filter_as_a_union(self):
        r3 = self.client.get(
            "/api/cdsem/recipe-tat/ranking?fab_name=R3"
        ).get_json()
        both = self.client.get(
            "/api/cdsem/recipe-tat/ranking?fab_name=R3,M16B"
        ).get_json()
        self.assertEqual(both["fab_names"], ["R3", "M16B"])
        # Union: the combined pool covers at least the single-fab pool.
        self.assertGreaterEqual(len(both["rows"]), len(r3["rows"]))

    def test_fail_issue_summary_echoes_fab_names_list(self):
        summary = self.client.get(
            "/api/cdsem/fail-issue/summary?fab_name=r3,m16b"
        ).get_json()
        self.assertEqual(summary["fab_names"], ["R3", "M16B"])

    # Split in two, each guarded on its own feature: a checkout can have
    # recipe_tat wired and fail_issue not, so the two cannot share one skipIf.
    @unittest.skipIf(
        has_office_adapter("ebeam/recipe_tat"),
        skip_reason("ebeam/recipe_tat"),
    )
    def test_unconnected_recipe_tat_adapter_fails_explicitly(self):
        os.environ["SKEWNONO_RECIPE_TAT_PROVIDER"] = "office"
        with self.assertRaisesRegex(RuntimeError, MISSING_ADAPTER_MESSAGE):
            get_recipe_tat_anchor_time()

    @unittest.skipIf(
        has_office_adapter("ebeam/fail_issue"),
        skip_reason("ebeam/fail_issue"),
    )
    def test_unconnected_fail_issue_adapter_fails_explicitly(self):
        os.environ["SKEWNONO_FAIL_ISSUE_PROVIDER"] = "office"
        with self.assertRaisesRegex(RuntimeError, MISSING_ADAPTER_MESSAGE):
            get_fail_issue_anchor_time()


class TestFilterClauses(unittest.TestCase):
    def test_single_fab_keeps_the_term_clause_shape(self):
        clauses = filter_clauses(("r3",), "2026-01-01", "2026-01-31")
        self.assertIn({"term": {FAB_NAME_KW: "R3"}}, clauses)

    def test_multiple_fabs_become_one_terms_clause(self):
        clauses = filter_clauses(("r3", "M16B"), "2026-01-01", "2026-01-31")
        self.assertIn({"terms": {FAB_NAME_KW: ["R3", "M16B"]}}, clauses)

    def test_no_fabs_add_no_fab_clause(self):
        clauses = filter_clauses(None, "2026-01-01", "2026-01-31")
        self.assertFalse(any("term" in c and FAB_NAME_KW in c.get("term", {}) for c in clauses))
        self.assertFalse(any(FAB_NAME_KW in c.get("terms", {}) for c in clauses))


if __name__ == "__main__":
    unittest.main()
