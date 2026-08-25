"""Route-level rules for GET /api/cdsem/pm-planning/fleet's query arguments.

The provider contract (back_dev_home/ebeam/pm_planning/tests/test_contract.py)
covers the payload. This covers what only the route can get wrong: that the
window argument is read the same way `/tttm/check` reads it — pm-tune joins
the two payloads, so they must default, accept and refuse identically.
"""

from __future__ import annotations

import unittest

from flask import Flask

from back_dev_home.ebeam._analysis_window import DEFAULT_WINDOW_WEEKS, WINDOW_WEEKS_CHOICES
from back_dev_home.ebeam.pm_planning.routes import bp


FAB = "R3"


class TestPmPlanningFleetArgs(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix="/api")
        self.client = app.test_client()

    def _get(self, query: str = ""):
        return self.client.get(f"/api/cdsem/pm-planning/fleet?fab_name={FAB}{query}")

    def test_fab_name_is_required(self):
        response = self.client.get("/api/cdsem/pm-planning/fleet")
        self.assertEqual(response.status_code, 400)

    def test_the_window_defaults_when_absent_or_blank(self):
        for query in ("", "&window_weeks="):
            response = self._get(query)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["window_weeks"], DEFAULT_WINDOW_WEEKS)

    def test_every_offered_window_is_echoed(self):
        for weeks in WINDOW_WEEKS_CHOICES:
            payload = self._get(f"&window_weeks={weeks}").get_json()
            self.assertEqual(payload["window_weeks"], weeks)
            self.assertEqual(payload["fab_name"], FAB)

    def test_a_window_outside_the_choices_is_refused_not_clamped(self):
        for bad in ("0", "4", "abc"):
            response = self._get(f"&window_weeks={bad}")
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn("window_weeks", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
