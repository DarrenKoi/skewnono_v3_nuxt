"""Route-level rules for GET /api/<slug>/tttm/check's scope arguments.

The provider contract (back_dev_home/ebeam/tttm/tests/test_contract.py) covers
what the payload must look like. This file covers the part only the route can
get wrong: which query arguments are legal together, and whether they actually
reach the provider.
"""

from __future__ import annotations

import unittest

from flask import Flask

from back_dev_home.ebeam.tttm.routes import bp


FAB = "R3"
RECIPE = "CDSEM_R3_METAL1_CD"
PARAMETER = "Para_13"


class TestTttmCheckScopeArgs(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix="/api")
        self.client = app.test_client()

    def _get(self, query: str):
        return self.client.get(f"/api/cdsem/tttm/check?fab_name={FAB}&{query}")

    def test_a_parameter_without_a_recipe_is_refused(self):
        # A parameter name is a row of ONE recipe's idp_image_info; the same
        # name in another recipe measures a different feature. Answering
        # "Para_13 across every recipe" would fold unrelated features into one
        # skew number and label it with a name that looks specific.
        #
        # 400 rather than silently ignoring the argument: the client would
        # otherwise render a group verdict under a parameter heading the server
        # never applied, which is indistinguishable from a correct answer.
        response = self._get(f"parameter={PARAMETER}")
        self.assertEqual(response.status_code, 400)
        self.assertIn("recipe_id", response.get_json()["error"])

    def test_a_recipe_without_a_parameter_is_the_folded_view(self):
        # The pre-existing behaviour, and still the default the pages open on.
        response = self._get(f"recipe_id={RECIPE}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["recipe_id"], RECIPE)
        self.assertIsNone(payload["parameter"])

    def test_both_arguments_reach_the_provider(self):
        response = self._get(f"recipe_id={RECIPE}&parameter={PARAMETER}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["recipe_id"], RECIPE)
        self.assertEqual(payload["parameter"], PARAMETER)

    def test_picking_a_parameter_recomputes_rather_than_relabels(self):
        # The whole point of the axis: narrowing to one feature must be able to
        # change the pairwise numbers, because that is what can move a tool in
        # or out of the N배화 group. A route that accepted the argument and
        # passed it nowhere would return an identically-numbered payload with a
        # different heading — the exact failure this asserts against.
        folded = self._get(f"recipe_id={RECIPE}").get_json()
        narrowed = self._get(f"recipe_id={RECIPE}&parameter={PARAMETER}").get_json()

        self.assertNotEqual(
            folded["fleet_today"]["matrix"]["values"],
            narrowed["fleet_today"]["matrix"]["values"],
            "the parameter reached no computation — the payload only got a new label",
        )

    def test_a_blank_parameter_is_absent_not_a_parameter_named_empty(self):
        # `?parameter=` is what a client sends when it clears the picker, and
        # the route's _arg() already folds blanks to None. Asserted because the
        # rule above would otherwise 400 a legitimate "cleared" request that
        # also cleared the recipe.
        response = self._get("recipe_id=&parameter=")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["parameter"])


if __name__ == "__main__":
    unittest.main()
