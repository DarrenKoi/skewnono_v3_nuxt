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
PARAMETER = "Para_13"


class TestTttmCheckScopeArgs(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix="/api")
        self.client = app.test_client()

    def _get(self, query: str):
        return self.client.get(f"/api/cdsem/tttm/check?fab_name={FAB}&{query}")

    def _measured_recipe(self) -> str:
        """A recipe THIS FAB HAS MEASURED, taken from the picker's own endpoint.

        Not a constant. This file used to name `CDSEM_R3_METAL1_CD`, which no
        fab has ever run — harmless while the provider seeded a payload from
        any string it was handed, and wrong the moment it stopped. An
        unmeasured recipe now answers `available: false` with empty matrices,
        so a hardcoded one would have made `test_picking_a_parameter_recomputes`
        compare [] against [] and pass forever without exercising the axis.

        Reading it back from /tttm/recipes also keeps the two endpoints honest
        against each other at the ROUTE level: the picker cannot start offering
        recipes the check refuses without failing here.
        """
        response = self.client.get(f"/api/cdsem/tttm/recipes?fab_name={FAB}")
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()["rows"]
        self.assertTrue(rows, f"{FAB} offers no measured recipe to scope by")
        return rows[0]["recipe_id"]

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
        recipe = self._measured_recipe()
        response = self._get(f"recipe_id={recipe}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["recipe_id"], recipe)
        self.assertIsNone(payload["parameter"])

    def test_both_arguments_reach_the_provider(self):
        recipe = self._measured_recipe()
        response = self._get(f"recipe_id={recipe}&parameter={PARAMETER}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["recipe_id"], recipe)
        self.assertEqual(payload["parameter"], PARAMETER)

    def test_picking_a_parameter_recomputes_rather_than_relabels(self):
        # The whole point of the axis: narrowing to one feature must be able to
        # change the pairwise numbers, because that is what can move a tool in
        # or out of the N배화 group. A route that accepted the argument and
        # passed it nowhere would return an identically-numbered payload with a
        # different heading — the exact failure this asserts against.
        recipe = self._measured_recipe()
        folded = self._get(f"recipe_id={recipe}").get_json()
        narrowed = self._get(f"recipe_id={recipe}&parameter={PARAMETER}").get_json()

        # Guard the guard: both payloads must actually carry a comparison, or
        # the inequality below would be satisfied by two different flavours of
        # nothing rather than by the parameter reaching the computation.
        self.assertTrue(folded["available"], folded["summary"])
        self.assertTrue(folded["fleet_today"]["matrix"]["values"])

        self.assertNotEqual(
            folded["fleet_today"]["matrix"]["values"],
            narrowed["fleet_today"]["matrix"]["values"],
            "the parameter reached no computation — the payload only got a new label",
        )

    def test_an_unmeasured_recipe_answers_200_not_an_error(self):
        # What a STALE STORED RECIPE sends. The pages persist the scope, and a
        # recipe_id saved while the picker still read recipe-search's catalogue
        # names something this fab never ran. That is a legitimate question with
        # an empty answer, not a fault: the payload says so, echoes the recipe,
        # and still carries the roster the tool picker is drawn from — which is
        # what lets the user pick a different recipe instead of reloading.
        response = self._get("recipe_id=CD_MONITOR/CD_MONITORING_HR_800V_X_FULL_NEW5")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["available"])
        self.assertEqual(
            payload["recipe_id"], "CD_MONITOR/CD_MONITORING_HR_800V_X_FULL_NEW5"
        )
        self.assertTrue(payload["tools"], "the roster is what the picker rebuilds from")

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


class TestTttmRecipesRoute(unittest.TestCase):
    """GET /api/<slug>/tttm/recipes — the shared pm-tune / TTTM picker source."""

    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix="/api")
        self.client = app.test_client()

    def test_it_answers_the_fab_it_was_asked_about(self):
        response = self.client.get(f"/api/cdsem/tttm/recipes?fab_name={FAB}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["fab_name"], FAB)
        self.assertEqual(payload["tool_slug"], "cdsem")

    def test_fab_name_is_required(self):
        # Same rule as /tttm/check, and for the same reason: a fab-less recipe
        # list would be the union across every fab, and picking one of those
        # recipes gives the check nothing to find in the fab actually on screen.
        response = self.client.get("/api/cdsem/tttm/recipes")
        self.assertEqual(response.status_code, 400)

    def test_an_unknown_tool_slug_is_refused(self):
        response = self.client.get(f"/api/nope/tttm/recipes?fab_name={FAB}")
        self.assertEqual(response.status_code, 400)
