"""Stable measurement-history data seam with mock/office adapters."""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.meas_hist.contracts import (
    MeasHistFacetsResponse,
    MeasHistResponse,
    MeasHistRow,
    MeasHistSearchResponse,
)
from back_dev_home.meas_hist.providers.mock import (
    DEFAULT_LIMIT,
    MAX_RESULT_WINDOW,
    MOCK_SEARCH_FIXTURES,
    RETENTION_DAYS,
    ToolType,
)


__all__ = [
    "MeasHistRow",
    "MeasHistResponse",
    "MeasHistSearchResponse",
    "MeasHistFacetsResponse",
    "ToolType",
    "get_meas_hist",
    "find_meas_hist_by_msr",
    "search_meas_hist",
    "get_meas_hist_facets",
    "RETENTION_DAYS",
    "MAX_RESULT_WINDOW",
    "DEFAULT_LIMIT",
    "MOCK_SEARCH_FIXTURES",
]


def _provider():
    if get_data_provider("meas_hist") == "office":
        from back_dev_home.meas_hist.providers import office
        return office
    from back_dev_home.meas_hist.providers import mock
    return mock


def _normalize_row(row: MeasHistRow) -> MeasHistRow:
    total_images = row["total_images"]
    fail_images = row["fail_images"]
    ratio = fail_images / total_images if total_images > 0 else 0.0

    normalized = row.copy()
    normalized["fail_ratio"] = round(max(0.0, min(1.0, ratio)), 4)
    return normalized


def get_meas_hist(
    tool_type: ToolType | None = None,
    fab_name: str | None = None,
    recipe_name: str | None = None,
) -> MeasHistResponse:
    response = _provider().get_meas_hist(tool_type, fab_name, recipe_name)
    normalized = response.copy()
    normalized["rows"] = [_normalize_row(row) for row in response["rows"]]
    return normalized


def find_meas_hist_by_msr(msr: str) -> MeasHistRow | None:
    row = _provider().find_meas_hist_by_msr(msr)
    return _normalize_row(row) if row is not None else None


def search_meas_hist(
    tool_type: ToolType | None = None,
    fab: list[str] | None = None,
    model: list[str] | None = None,
    eq: list[str] | None = None,
    recipe: list[str] | None = None,
    lot: list[str] | None = None,
    msr: list[str] | None = None,
    q: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
) -> MeasHistSearchResponse:
    response = _provider().search_meas_hist(
        tool_type,
        fab,
        model,
        eq,
        recipe,
        lot,
        msr,
        q,
        date_from,
        date_to,
        offset,
        limit,
    )
    normalized = response.copy()
    normalized["rows"] = [_normalize_row(row) for row in response["rows"]]
    return normalized


def get_meas_hist_facets(
    tool_type: ToolType | None = None,
) -> MeasHistFacetsResponse:
    return _provider().get_meas_hist_facets(tool_type)
