"""Contract gate for meas_hist. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/meas_hist
Office: SKEWNONO_MEAS_HIST_PROVIDER=office .venv/bin/pytest back_dev_home/meas_hist
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.meas_hist import data
from back_dev_home.meas_hist.contracts import (
    MeasHistFacetsResponse,
    MeasHistResponse,
    MeasHistRow,
    MeasHistSearchResponse,
)


def test_get_meas_hist_matches_contract():
    assert_matches(data.get_meas_hist(), MeasHistResponse)


def test_search_meas_hist_matches_contract():
    assert_matches(data.search_meas_hist(), MeasHistSearchResponse)


def test_get_meas_hist_facets_matches_contract():
    assert_matches(data.get_meas_hist_facets(), MeasHistFacetsResponse)


def test_find_meas_hist_by_msr_matches_contract():
    search_result = data.search_meas_hist()
    rows = search_result["rows"]
    if not rows:
        rows = data.get_meas_hist()["rows"]
    assert rows, "expected at least one row to derive an msr from"
    msr = rows[0]["msr"]

    row = data.find_meas_hist_by_msr(msr)
    if row is not None:
        assert_matches(row, MeasHistRow)
