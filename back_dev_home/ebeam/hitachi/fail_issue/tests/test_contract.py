"""Contract gate for fail_issue. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/fail_issue
Office: SKEWNONO_FAIL_ISSUE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/fail_issue

The shape checks and the aggregation laws below are meaningful under both
providers: MIGRATION.md specifies the office adapter to drop zero-fail groups,
sort each ranking by fail count desc, rank from 1, and zero-fill + date-sort
the daily trend — the same laws providers/mock.py implements. What is NOT
provider-independent is that the window CONTAINS anything: the mock fabricates
a fixed row set around its own ANCHOR_TIME, while a live meas_hist index can
legitimately hold nothing for a fab/window. Those assumptions are fenced
behind get_data_provider("fail_issue") == "mock" so the office run cannot go
green on a mock-only invariant — nor red on an empty-but-valid index.

Deliberately NOT asserted: distinct_equipment / distinct_recipes / distinct_lots
against the row set. Office computes them with an OpenSearch `cardinality` agg,
which is approximate above ~3000 distinct values (see office_example.py), so
any exact-count law here would be a mock-only invariant wearing a disguise.
"""

from datetime import timedelta

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.fail_issue import data
from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    MeasRankingRow,
    SummaryPayload,
)


# Mirrors resolve_analytics_scope's defaults (_analytics_routes.py):
# end_date = anchor, start_date = anchor - 14 days, no fab/lot filter.
DEFAULT_DAYS = 14


def _default_scope():
    anchor = data.get_anchor_time().date()
    end_date = anchor.isoformat()
    start_date = (anchor - timedelta(days=DEFAULT_DAYS)).isoformat()
    return "cd-sem", None, start_date, end_date


def _is_mock() -> bool:
    return get_data_provider("fail_issue") == "mock"


def _assert_triage_table(rows, count_key: str, rate_key: str) -> None:
    """Laws every ranking obeys under BOTH providers (MIGRATION.md §ranking).

    Zero-fail groups are dropped so the table stays a triage list, the sort is
    by (fail count, fail rate) descending, and rank is a 1-based dense index of
    that order. A ranking that violates any of these is wrong wherever the rows
    came from — which is exactly what should stay unfenced.
    """
    assert [row["rank"] for row in rows] == list(range(1, len(rows) + 1))
    for row in rows:
        assert row[count_key] > 0, "zero-fail groups must be dropped"
        assert row[count_key] <= row["exec_count"]
        assert 0.0 < row[rate_key] <= 1.0
        assert len(row["sample_eqp_ids"]) <= 5
    counts = [row[count_key] for row in rows]
    assert counts == sorted(counts, reverse=True), "ranking must be fail-count desc"


def test_get_summary_matches_contract():
    tool_type, fab_name, start_date, end_date = _default_scope()
    summary = data.get_summary(tool_type, fab_name, start_date, end_date, lot_cd=None)
    assert_matches(summary, SummaryPayload)

    # Counting laws, true of any correct aggregator: a fail is one of the
    # executions counted, and both rates are FRACTIONS (mock's `fails / total`,
    # office's `_rate()`) — not percentages.
    total = summary["total_executions"]
    assert total >= 0
    for key in ("align_fail_count", "align_na_count", "meas_fail_count"):
        assert 0 <= summary[key] <= total, f"{key} exceeds total_executions"
    for key in ("align_fail_rate", "meas_fail_rate"):
        assert 0.0 <= summary[key] <= 1.0, f"{key} is not a 0..1 fraction"

    if _is_mock():
        # The mock generates a fixed row set spanning its own ANCHOR_TIME, so an
        # empty default window means the generator broke. A live index may
        # genuinely hold nothing for these 14 days.
        assert total > 0, "mock fail_issue summary must cover some executions"


def test_get_daily_trend_matches_contract():
    tool_type, fab_name, start_date, end_date = _default_scope()
    points = data.get_daily_trend(tool_type, fab_name, start_date, end_date, lot_cd=None)
    assert isinstance(points, list)
    for point in points:
        assert_matches(point, DailyTrendPoint)

    # Both adapters zero-fill the range and return it date-ascending — the
    # chart plots the list in order and would render time backwards otherwise.
    dates = [point["date"] for point in points]
    assert dates == sorted(dates), "daily trend must be date-ascending"
    for point in points:
        assert point["align_fail_count"] <= point["exec_count"]
        assert point["meas_fail_count"] <= point["exec_count"]

    # Zero-fill is a BOTH-provider guarantee, so the point count is pinned by
    # the requested range rather than by what data happens to exist: the mock
    # backfills, and office sets date_histogram extended_bounds over the same
    # window (MIGRATION.md /daily-trend). Left unfenced deliberately — this is
    # the check that catches an office adapter dropping empty days.
    assert len(points) == DEFAULT_DAYS + 1, "daily trend must zero-fill the window"


def test_get_align_ranking_matches_contract():
    tool_type, fab_name, start_date, end_date = _default_scope()
    rows = data.get_align_ranking(tool_type, fab_name, start_date, end_date, limit=1000, lot_cd=None)
    assert isinstance(rows, list)
    for row in rows:
        assert_matches(row, AlignRankingRow)

    _assert_triage_table(rows, "align_fail_count", "align_fail_rate")

    if _is_mock():
        # The mock's fabricated rows always contain align fails, so an empty
        # triage table means the generator or the filter broke. Office may
        # legitimately have had no align failure in the window.
        assert rows, "mock align ranking must not be empty"


def test_get_meas_ranking_matches_contract():
    tool_type, fab_name, start_date, end_date = _default_scope()
    rows = data.get_meas_ranking(tool_type, fab_name, start_date, end_date, limit=1000, lot_cd=None)
    assert isinstance(rows, list)
    for row in rows:
        assert_matches(row, MeasRankingRow)

    _assert_triage_table(rows, "meas_fail_count", "meas_fail_rate")
    for row in rows:
        # Contract-fixed scales that differ between the two fields: the rate is
        # a fraction, avg_fail_ratio is the mean of per-row PERCENT fail_ratio.
        assert 0.0 <= row["avg_fail_ratio"] <= 100.0

    if _is_mock():
        # Same rationale as align above.
        assert rows, "mock meas ranking must not be empty"


def test_get_devices_matches_contract():
    tool_type, fab_name, start_date, end_date = _default_scope()
    devices = data.get_devices(tool_type, fab_name, start_date, end_date)
    assert isinstance(devices, list)
    for device in devices:
        assert_matches(device, DeviceRow)
        assert device["align_fail_count"] <= device["exec_count"]
        assert device["meas_fail_count"] <= device["exec_count"]

    if _is_mock():
        # MIGRATION.md calls an empty office /devices result valid (no chips
        # matched); the mock's lot_cd bridge is fabricated and always resolves.
        assert devices, "mock device list must not be empty"
