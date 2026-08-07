"""Contract gate for recipe_tat. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
Office: SKEWNONO_RECIPE_TAT_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
"""

from datetime import timedelta

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.recipe_tat import data
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    DailyTrendPoint,
    DeviceRow,
    RankingRow,
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


def test_get_ranking_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_ranking(tool_type, fab_names, start_date, end_date, limit=0, lot_cd=None)
    assert isinstance(rows, list)
    for row in rows:
        assert_matches(row, RankingRow)


def test_get_ranking_limit_zero_is_uncapped():
    # limit=0 (the route default) must return EVERY recipe in the range —
    # a positive limit trims the same, fully-sorted ranking from the top.
    tool_type, fab_names, start_date, end_date = _default_scope()
    everything = data.get_ranking(tool_type, fab_names, start_date, end_date, limit=0, lot_cd=None)
    top = data.get_ranking(tool_type, fab_names, start_date, end_date, limit=5, lot_cd=None)
    assert len(top) <= 5
    assert len(everything) >= len(top)
    if get_data_provider("recipe_tat") == "mock":
        # Deterministic only for the mock — office data may move between calls.
        assert everything[: len(top)] == top


def test_office_get_meas_hist_is_intentionally_disconnected():
    # Raw-row export is not part of the office wiring (routes only use the
    # aggregation endpoints). Pin that as a loud NotImplementedError so a
    # future office.py copy can't silently return wrong-shaped rows.
    import pytest

    office_example = pytest.importorskip(
        "back_dev_home.ebeam.hitachi.recipe_tat.providers.office_example"
    )
    with pytest.raises(NotImplementedError):
        office_example.get_meas_hist()


def test_get_summary_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    assert_matches(
        data.get_summary(tool_type, fab_names, start_date, end_date, lot_cd=None),
        SummaryPayload,
    )


def test_get_daily_trend_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    points = data.get_daily_trend(tool_type, fab_names, start_date, end_date, lot_cd=None)
    assert isinstance(points, list)
    for point in points:
        assert_matches(point, DailyTrendPoint)


def test_get_devices_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    devices = data.get_devices(tool_type, fab_names, start_date, end_date)
    assert isinstance(devices, list)
    for device in devices:
        assert_matches(device, DeviceRow)


def test_ranking_rows_carry_contributing_fabs():
    rows = data.get_ranking("cd-sem", ("R3", "M16B"), None, None, limit=20)
    assert rows
    for row in rows:
        assert row["fab_names"] == sorted(row["fab_names"])
        assert row["fab_names"]
        assert set(row["fab_names"]) <= {"R3", "M16B"}


def test_single_fab_ranking_tags_that_fab_only():
    rows = data.get_ranking("cd-sem", ("R3",), None, None, limit=5)
    assert all(row["fab_names"] == ["R3"] for row in rows)
