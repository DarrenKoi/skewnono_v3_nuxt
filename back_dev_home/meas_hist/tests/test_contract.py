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

    # The msr came from a real row, so the lookup MUST resolve it — a silent
    # skip on None would let a lookup that never finds anything pass the gate.
    row = data.find_meas_hist_by_msr(msr)
    assert row is not None, f"a known msr ({msr}) must resolve to a row"
    assert_matches(row, MeasHistRow)


def test_find_meas_hist_by_unknown_msr_returns_none():
    assert data.find_meas_hist_by_msr("MSR-DOES-NOT-EXIST-000000") is None
