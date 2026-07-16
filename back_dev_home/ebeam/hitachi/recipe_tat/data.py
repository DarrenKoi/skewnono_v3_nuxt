"""Stable Recipe-TAT data seam with mock/office adapters."""

from datetime import datetime

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    DailyTrendPoint,
    DeviceRow,
    MeasHistRow,
    RankingRow,
    SummaryPayload,
    ToolType,
)
from back_dev_home.ebeam.hitachi.recipe_tat.providers import mock as mock_provider
from back_dev_home.ebeam.hitachi.recipe_tat.providers.mock import ANCHOR_TIME


__all__ = [
    "ANCHOR_TIME",
    "ToolType",
    "MeasHistRow",
    "get_anchor_time",
    "get_meas_hist",
    "get_ranking",
    "get_summary",
    "get_daily_trend",
    "get_devices",
]


def _provider():
    if get_data_provider("recipe_tat") == "office":
        from back_dev_home.ebeam.hitachi.recipe_tat.providers import office
        return office
    return mock_provider


def get_anchor_time() -> datetime:
    provider = _provider()
    if provider is mock_provider:
        return mock_provider.ANCHOR_TIME
    return provider.get_anchor_time()


def get_meas_hist() -> list[MeasHistRow]:
    return _provider().get_meas_hist()


def get_ranking(
    tool_type: ToolType,
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 1000,
    lot_cd: str | None = None,
) -> list[RankingRow]:
    return _provider().get_ranking(
        tool_type, fab_id, start_date, end_date, limit, lot_cd
    )


def get_summary(
    tool_type: ToolType,
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None,
) -> SummaryPayload:
    return _provider().get_summary(
        tool_type, fab_id, start_date, end_date, lot_cd
    )


def get_daily_trend(
    tool_type: ToolType,
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None,
) -> list[DailyTrendPoint]:
    return _provider().get_daily_trend(
        tool_type, fab_id, start_date, end_date, lot_cd
    )


def get_devices(
    tool_type: ToolType,
    fab_id: str | None,
    start_date: str | None,
    end_date: str | None,
) -> list[DeviceRow]:
    return _provider().get_devices(tool_type, fab_id, start_date, end_date)
