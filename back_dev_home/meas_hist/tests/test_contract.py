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


def test_meas_hist_fleet_excludes_amat_tools_deliberately():
    """AMAT 은 measurement 소스가 없으므로 mock 도 지어내지 않는다.

    분류기가 AMAT 을 해석하기 시작한 뒤에도 이 제외가 유지되어야 한다.
    """
    from back_dev_home.ebeam._tool_specs import model_to_tool_type
    from back_dev_home.meas_hist.providers.mock import _eligible_sem_rows

    tool_types = {model_to_tool_type(row["eqp_model_cd"]) for row in _eligible_sem_rows()}
    assert tool_types <= {"cd-sem", "hv-sem"}
    assert tool_types  # 비어 있으면 필터가 전부를 지운 것


# ---------------------------------------------------------------------------
# 공백뿐인 검색어 — office 의 _wildcard_or 는 strip 후 버리는데 mock 은
# 그대로 들고 있었습니다. 같은 `?recipe=%20` 이 집에서는 0건, 사무실에서는
# 보존 기간 전체를 돌려줬습니다.


@pytest.mark.parametrize("blank", [" ", "   ", "\t", "\n"])
def test_whitespace_only_search_term_is_dropped_not_matched(blank):
    baseline = data.search_meas_hist()["rows"]
    assert data.search_meas_hist(recipe=[blank])["rows"] == baseline
    assert data.search_meas_hist(q=[blank])["rows"] == baseline


def test_search_terms_are_stripped_before_matching():
    """office 는 "  abc  " 로 "abc" 를 찾습니다 — mock 도 그래야 합니다."""
    rows = data.search_meas_hist()["rows"]
    if not rows:
        pytest.skip("mock returned no rows to derive a term from")
    term = rows[0]["recipe_name"]

    exact = data.search_meas_hist(recipe=[term])["rows"]
    padded = data.search_meas_hist(recipe=[f"  {term}  "])["rows"]
    assert padded == exact
    assert padded
