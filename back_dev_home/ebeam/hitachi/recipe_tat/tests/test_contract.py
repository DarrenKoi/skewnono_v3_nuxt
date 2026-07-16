"""Contract gate for recipe_tat. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
Office: SKEWNONO_RECIPE_TAT_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
"""

from datetime import timedelta

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.recipe_tat import data
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    DailyTrendPoint,
    DeviceRow,
    RankingRow,
    SummaryPayload,
)


# Mirrors resolve_analytics_scope's defaults (_analytics_routes.py):
# end_date = anchor, start_date = anchor - 30 days, no fab/lot filter.
DEFAULT_DAYS = 30


def _default_scope():
    anchor = data.get_anchor_time().date()
    end_date = anchor.isoformat()
    start_date = (anchor - timedelta(days=DEFAULT_DAYS)).isoformat()
    return "cd-sem", None, start_date, end_date


def test_get_ranking_matches_contract():
    tool_type, fab_id, start_date, end_date = _default_scope()
    rows = data.get_ranking(tool_type, fab_id, start_date, end_date, limit=1000, lot_cd=None)
    assert isinstance(rows, list)
    for row in rows:
        assert_matches(row, RankingRow)


def test_get_summary_matches_contract():
    tool_type, fab_id, start_date, end_date = _default_scope()
    assert_matches(
        data.get_summary(tool_type, fab_id, start_date, end_date, lot_cd=None),
        SummaryPayload,
    )


def test_get_daily_trend_matches_contract():
    tool_type, fab_id, start_date, end_date = _default_scope()
    points = data.get_daily_trend(tool_type, fab_id, start_date, end_date, lot_cd=None)
    assert isinstance(points, list)
    for point in points:
        assert_matches(point, DailyTrendPoint)


def test_get_devices_matches_contract():
    tool_type, fab_id, start_date, end_date = _default_scope()
    devices = data.get_devices(tool_type, fab_id, start_date, end_date)
    assert isinstance(devices, list)
    for device in devices:
        assert_matches(device, DeviceRow)
