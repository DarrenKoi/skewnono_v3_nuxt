"""Stable fail-issue data seam with mock/office adapters."""

from datetime import datetime

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.fail_issue.contracts import (
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    EquipmentComparePayload,
    EquipmentsPayload,
    FailRow,
    MeasRankingRow,
    SummaryPayload,
)
from back_dev_home.ebeam.fail_issue.providers import mock as mock_provider
from back_dev_home.ebeam.fail_issue.providers.mock import (
    ANCHOR_TIME,
    MEAS_FAIL_THRESHOLD,
    ToolType,
)


__all__ = [
    "ANCHOR_TIME",
    "MEAS_FAIL_THRESHOLD",
    "ToolType",
    "FailRow",
    "get_anchor_time",
    "get_summary",
    "get_daily_trend",
    "get_align_ranking",
    "get_meas_ranking",
    "get_devices",
    "get_equipments",
    "get_equipment_compare",
]


def _provider():
    if get_data_provider("fail_issue") == "office":
        from back_dev_home.ebeam.fail_issue.providers import office
        return office
    return mock_provider


def get_anchor_time() -> datetime:
    provider = _provider()
    if provider is mock_provider:
        return mock_provider.ANCHOR_TIME
    return provider.get_anchor_time()


def get_summary(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None,
) -> SummaryPayload:
    return _provider().get_summary(
        tool_type, fab_names, start_date, end_date, lot_cd
    )


def get_daily_trend(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    lot_cd: str | None = None,
) -> list[DailyTrendPoint]:
    return _provider().get_daily_trend(
        tool_type, fab_names, start_date, end_date, lot_cd
    )


def get_align_ranking(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None,
) -> list[AlignRankingRow]:
    return _provider().get_align_ranking(
        tool_type, fab_names, start_date, end_date, limit, lot_cd
    )


def get_meas_ranking(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    limit: int = 0,
    lot_cd: str | None = None,
) -> list[MeasRankingRow]:
    return _provider().get_meas_ranking(
        tool_type, fab_names, start_date, end_date, limit, lot_cd
    )


def get_devices(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> list[DeviceRow]:
    return _provider().get_devices(tool_type, fab_names, start_date, end_date)


def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> EquipmentsPayload:
    return _provider().get_equipments(tool_type, fab_names, start_date, end_date)


def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...],
) -> EquipmentComparePayload:
    return _provider().get_equipment_compare(
        tool_type, fab_names, start_date, end_date, eqp_ids
    )
