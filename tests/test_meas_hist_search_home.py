"""Home-safe contract tests for robust Skewvoir measurement search.

Run only this file:
    .venv/bin/python -m unittest tests.test_meas_hist_search_home

No OpenSearch connection is used. The tests exercise deterministic Phase 1
rows and the Flask route contract that the office adapter must preserve.
"""

from __future__ import annotations

import os
import unittest

from flask import Flask

from back_dev_home.meas_hist.data import MOCK_SEARCH_FIXTURES, search_meas_hist
from back_dev_home.meas_hist.opensearch_query import (
    SEARCH_ALL_MAPPING,
    build_q_fallback_clause,
    build_search_all_value,
)
from back_dev_home.meas_hist.routes import bp
from tests._office_state import MISSING_ADAPTER_MESSAGE, has_office_adapter, skip_reason


class TestMeasHistFallbackSearch(unittest.TestCase):
    def setUp(self):
        self._provider = os.environ.pop("SKEWNONO_MEAS_HIST_PROVIDER", None)

    def tearDown(self):
        if self._provider is None:
            os.environ.pop("SKEWNONO_MEAS_HIST_PROVIDER", None)
        else:
            os.environ["SKEWNONO_MEAS_HIST_PROVIDER"] = self._provider

    def test_mock_has_stable_search_fixtures_for_both_tool_types(self):
        self.assertEqual(
            {row["tool_type"] for row in MOCK_SEARCH_FIXTURES},
            {"cd-sem", "hv-sem"},
        )
        self.assertEqual(MOCK_SEARCH_FIXTURES[0]["eqp_id"], "ECXDX925")

    def test_q_searches_equipment_prefix_across_all_fields(self):
        result = search_meas_hist(tool_type="cd-sem", q=["ECXDX"])

        self.assertGreater(result["total"], 0)
        self.assertTrue(any("ECXDX" in row["eqp_id"] for row in result["rows"]))

    def test_q_searches_lot_recipe_model_and_msr_substrings(self):
        for term, field in (
            ("257421", "lot_id"),
            ("CD_BIAS", "recipe_name"),
            ("CG6300", "eqp_model_cd"),
            ("20260509", "msr"),
        ):
            with self.subTest(term=term):
                result = search_meas_hist(tool_type="cd-sem", q=[term])
                self.assertGreater(result["total"], 0)
                self.assertTrue(
                    any(term.lower() in row[field].lower() for row in result["rows"])
                )

    def test_q_is_anded_with_structured_filters(self):
        result = search_meas_hist(
            tool_type="cd-sem",
            eq=["ECXDX925"],
            q=["CD_BIAS"],
        )

        self.assertGreater(result["total"], 0)
        self.assertTrue(all(row["eqp_id"] == "ECXDX925" for row in result["rows"]))

    def test_recipe_names_are_complete_even_when_raw_rows_use_a_small_limit(self):
        result = search_meas_hist(recipe=["CD_BIAS"], limit=1)

        self.assertIn("recipe_names", result)
        self.assertIn("recipe_names_complete", result)
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(
            result["recipe_names"],
            [
                "ADI/ADI_CD_BIAS_001",
                "ADI/ADI_CD_BIAS_ABC123_PROD_00006",
                "ADI/ADI_CD_BIAS_ABC123_STD_00001",
            ],
        )
        self.assertTrue(result["recipe_names_complete"])

    def test_recipe_names_keep_the_broad_or_candidate_set_for_multiple_terms(self):
        result = search_meas_hist(recipe=["CD_BIAS", "GATE_PITCH"], limit=1)

        self.assertEqual(
            result["recipe_names"],
            [
                "ADI/ADI_CD_BIAS_001",
                "ADI/ADI_CD_BIAS_ABC123_PROD_00006",
                "ADI/ADI_CD_BIAS_ABC123_STD_00001",
                "GATE/GATE_PITCH_001",
                "GATE/GATE_PITCH_MON_ABC123_ENG_00009",
            ],
        )
        self.assertTrue(result["recipe_names_complete"])

    def test_recipe_names_are_not_requested_without_a_recipe_filter(self):
        result = search_meas_hist(limit=1)

        self.assertEqual(result["recipe_names"], [])
        self.assertFalse(result["recipe_names_complete"])

    def test_recipe_names_are_incomplete_for_rejected_date_ranges(self):
        cases = (
            {"date_from": "not-a-date"},
            {"date_to": "2020-01-01"},
            {"date_from": "2099-01-01"},
        )
        for params in cases:
            with self.subTest(params=params):
                result = search_meas_hist(recipe=["CD_BIAS"], **params)

                self.assertTrue(result["out_of_retention"])
                self.assertEqual(result["recipe_names"], [])
                self.assertFalse(result["recipe_names_complete"])

    def test_route_accepts_repeated_q_parameters(self):
        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix="/api")

        response = app.test_client().get(
            "/api/meas-hist/search?tool_type=cd-sem&q=ECXDX"
        )
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertGreater(payload["total"], 0)
        self.assertTrue(any("ECXDX" in row["eqp_id"] for row in payload["rows"]))

    def test_office_query_contract_uses_one_dedicated_wildcard_field(self):
        clause = build_q_fallback_clause(["ECXDX", "A*B?"])

        self.assertEqual(SEARCH_ALL_MAPPING, {"type": "wildcard"})
        self.assertEqual(clause["bool"]["minimum_should_match"], 1)
        wildcard_values = [
            item["wildcard"]["search_all"]["value"]
            for item in clause["bool"]["should"]
        ]
        self.assertEqual(wildcard_values, ["*ECXDX*", "*A\\*B\\?*"])

    def test_office_ingest_value_contains_the_same_home_search_fields(self):
        value = build_search_all_value(MOCK_SEARCH_FIXTURES[0])

        self.assertIn("ECXDX925", value)
        self.assertIn("6LD257421", value)
        self.assertIn("ADI_CD_BIAS_001", value)
        self.assertNotIn("120 0 0.0", value)

    @unittest.skipIf(has_office_adapter("meas_hist"), skip_reason("meas_hist"))
    def test_unconnected_office_adapter_fails_explicitly(self):
        os.environ["SKEWNONO_MEAS_HIST_PROVIDER"] = "office"

        with self.assertRaisesRegex(RuntimeError, MISSING_ADAPTER_MESSAGE):
            search_meas_hist(tool_type="cd-sem")


if __name__ == "__main__":
    unittest.main()
