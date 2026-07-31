"""Home-safe tests for the activity fab-page-usage aggregation.

Run only this file:
    .venv/bin/python -m unittest tests.test_activity_home
"""

from __future__ import annotations

import unittest

from back_dev_home.activity import data
from back_dev_home.activity.providers import mock as activity_mock


class FabPageUsageTestCase(unittest.TestCase):
    def setUp(self):
        # Isolate from any live record_request traffic and other tests.
        activity_mock._users.clear()
        data.seed_demo_users()

    def tearDown(self):
        activity_mock._users.clear()

    def test_response_shape(self):
        payload = data.get_fab_page_usage()
        self.assertIn("generated_at", payload)
        self.assertIn("fabs_7d", payload)
        self.assertIn("fabs_30d", payload)
        for window in ("fabs_7d", "fabs_30d"):
            self.assertTrue(payload[window], f"{window} should not be empty")
            for row in payload[window]:
                self.assertEqual(set(row), {"fab", "total", "pages"})
                self.assertGreater(row["total"], 0)
                for page in row["pages"]:
                    self.assertEqual(set(page), {"feature", "count"})

    def test_rows_sorted_by_total_desc(self):
        rows = data.get_fab_page_usage()["fabs_30d"]
        totals = [row["total"] for row in rows]
        self.assertEqual(totals, sorted(totals, reverse=True))

    def test_seeded_fabs_present(self):
        fabs = {row["fab"] for row in data.get_fab_page_usage()["fabs_30d"]}
        # Home fabs assigned in seed_demo_users.
        self.assertLessEqual({"M14", "M16B", "M11", "R3", "M15"}, fabs)

    def test_unaffiliated_traffic_buckets_under_mijijeong(self):
        activity_mock._users.clear()
        data.record_request("live-dev", "sem_list", "entry", [])
        fabs = {row["fab"] for row in data.get_fab_page_usage()["fabs_30d"]}
        self.assertIn("미지정", fabs)

    def test_entry_counts_activity_but_never_top_features(self):
        activity_mock._users.clear()
        data.record_request("u1", "sem_list", "entry", ["M14"])
        me = data.get_me("u1")
        self.assertEqual(me["this_month"]["requests"], 1)
        self.assertEqual(me["top_features"], [])

    def test_fab_total_is_distinct_users_not_requests(self):
        activity_mock._users.clear()
        for _ in range(3):
            data.record_request("u1", "storage", "feature", ["M14"])
        data.record_request("u2", "sem_list", "entry", ["M14"])
        row = data.get_fab_page_usage()["fabs_7d"][0]
        self.assertEqual(row["fab"], "M14")
        self.assertEqual(row["total"], 2)
        self.assertEqual(row["pages"], [{"feature": "storage", "count": 3}])

    def test_multi_fab_request_contributes_to_each_bucket_once(self):
        activity_mock._users.clear()
        data.record_request("u1", "storage", "feature", ["M14", "M16"])
        rows = data.get_fab_page_usage()["fabs_7d"]
        self.assertEqual(
            {row["fab"]: row["total"] for row in rows},
            {"M14": 1, "M16": 1},
        )


if __name__ == "__main__":
    unittest.main()
