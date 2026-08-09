"""Office-local 횡전개 consistency check against live OpenSearch and Redis.

Set the office connection variables plus:

    TEST_STAGE=local
    TEST_LATERAL_FAB=<fab shown in the page>
    TEST_LATERAL_RECIPE=RWEAXXX/RWEA_SELHMULTO2

Then run:

    .venv/bin/python -m unittest tests.test_lateral_recipe_local
"""

from __future__ import annotations

import os
import unittest


_READY = all((
    os.environ.get("TEST_STAGE") == "local",
    os.environ.get("TEST_LATERAL_FAB"),
    os.environ.get("TEST_LATERAL_RECIPE"),
    os.environ.get("OPENSEARCH_HOST"),
    os.environ.get("REDIS_HOST"),
))


@unittest.skipUnless(
    _READY,
    "office-local lateral recipe variables are not configured",
)
class TestLateralRecipeOfficeConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from back_dev_home.ebeam.lateral_recipe.providers import office

        cls.provider = office
        cls.fab = os.environ["TEST_LATERAL_FAB"]
        cls.recipe = os.environ["TEST_LATERAL_RECIPE"]

    def test_recently_measured_roster_tools_are_ready(self):
        docs = self.provider._version_docs("cd-sem", self.fab, self.recipe)
        self.assertTrue(docs, "expected at least one IDP version document")

        measured = self.provider._measured_eqp_ids(
            "cd-sem",
            self.fab,
            self.recipe,
        )
        response = self.provider.get_lateral_recipe(
            "cd-sem",
            self.fab,
            self.recipe,
        )
        roster = {row["eqp_id"].strip().upper() for row in response["rows"]}
        measured_roster = measured & roster
        self.assertTrue(
            measured_roster,
            "expected at least one measured tool in the current SEM roster",
        )

        ready = {
            row["eqp_id"].strip().upper()
            for row in response["rows"]
            if row["recipe_ready"]
        }
        self.assertLessEqual(measured_roster, ready)


if __name__ == "__main__":
    unittest.main()
