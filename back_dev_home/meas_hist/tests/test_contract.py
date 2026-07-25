"""Contract gate for meas_hist. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/meas_hist
Office: SKEWNONO_MEAS_HIST_PROVIDER=office .venv/bin/pytest back_dev_home/meas_hist

The office adapter is implemented (OpenSearch), not a stub, so the only
mock-only assumption in this file is that rows EXIST: the mock always
fabricates a row set, while the office index can legitimately answer with
nothing (an ingestion pause, or a window with no measurements). Everything else
is required of both providers and stays unfenced so it runs office-side: the
contract shapes, "a known msr must resolve" and "an unknown msr returns None"
(MIGRATION.md), and eqp_ip being a real dotted quad — msr_image's routes.py
feeds that field straight into validate_tool_ip() before any FTP fetch, so a
row carrying anything else cannot serve images in any phase.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.meas_hist import data
from back_dev_home.meas_hist.contracts import (
    MeasHistFacetsResponse,
    MeasHistResponse,
    MeasHistRow,
    MeasHistSearchResponse,
)


def _first_row() -> MeasHistRow:
    """One real row for the msr / eqp_ip checks to key off, or a skip.

    /search is tried first (the wider 60-day retention window), falling back to
    the 30-day default view.
    """
    rows = data.search_meas_hist()["rows"]
    if not rows:
        rows = data.get_meas_hist()["rows"]
    if get_data_provider("meas_hist") == "mock":
        # The mock's row set is fabricated at import time, so an empty result
        # means the generator broke. An empty office index is valid data.
        assert rows, "mock meas hist must not be empty"
    if not rows:
        pytest.skip("active provider returned no meas_hist rows")
    return rows[0]


def test_get_meas_hist_matches_contract():
    assert_matches(data.get_meas_hist(), MeasHistResponse)


def test_search_meas_hist_matches_contract():
    assert_matches(data.search_meas_hist(), MeasHistSearchResponse)


def test_get_meas_hist_facets_matches_contract():
    assert_matches(data.get_meas_hist_facets(), MeasHistFacetsResponse)


def test_find_meas_hist_by_msr_matches_contract():
    msr = _first_row()["msr"]

    # The msr came from a real row, so the lookup MUST resolve it — a silent
    # skip on None would let a lookup that never finds anything pass the gate.
    row = data.find_meas_hist_by_msr(msr)
    assert row is not None, f"a known msr ({msr}) must resolve to a row"
    assert_matches(row, MeasHistRow)


def test_find_meas_hist_by_unknown_msr_returns_none():
    assert data.find_meas_hist_by_msr("MSR-DOES-NOT-EXIST-000000") is None


def test_row_eqp_ip_is_dotted_quad():
    """msr_image needs eqp_ip to fetch a tool's images; every row must carry
    a well-formed IPv4 address, not just a truthy string."""
    row = _first_row()
    parts = row["eqp_ip"].split(".")
    assert len(parts) == 4 and all(p.isdigit() for p in parts), (
        f"eqp_ip {row['eqp_ip']!r} is not a dotted-quad IPv4 address"
    )
