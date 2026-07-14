"""Office-local OpenSearch checks for the Skewvoir fallback field.

The module skips cleanly at home. In the office, set:

    TEST_STAGE=local
    TEST_OPENSEARCH_INDEX=meas_hist_cdsem
    TEST_MEAS_HIST_Q=ECXDX

alongside the existing ``OPENSEARCH_*`` connection variables, then run:

    .venv/bin/python -m unittest tests.test_meas_hist_search_local
"""

from __future__ import annotations

import os
import unittest

from back_dev_home.meas_hist.opensearch_query import (
    SEARCH_ALL_FIELD,
    build_q_fallback_clause,
)


_READY = all((
    os.environ.get("TEST_STAGE") == "local",
    os.environ.get("TEST_OPENSEARCH_INDEX"),
    os.environ.get("TEST_MEAS_HIST_Q"),
    os.environ.get("OPENSEARCH_HOST"),
))


@unittest.skipUnless(
    _READY,
    "office-local OpenSearch variables are not configured",
)
class TestMeasHistOpenSearchFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from ops_store import OSSearch

        cls.index = os.environ["TEST_OPENSEARCH_INDEX"]
        cls.term = os.environ["TEST_MEAS_HIST_Q"]
        cls.search = OSSearch(index=cls.index)

    def test_search_all_is_mapped_as_wildcard(self):
        mappings = self.search.client.indices.get_mapping(index=self.index)
        field_types = {
            body.get("mappings", {})
            .get("properties", {})
            .get(SEARCH_ALL_FIELD, {})
            .get("type")
            for body in mappings.values()
        }

        self.assertEqual(field_types, {"wildcard"})

    def test_configured_fallback_term_returns_a_real_hit(self):
        result = self.search.search_raw({
            "query": build_q_fallback_clause([self.term]),
            "size": 1,
        })

        self.assertGreater(len(result.get("hits", {}).get("hits", [])), 0)


if __name__ == "__main__":
    unittest.main()
