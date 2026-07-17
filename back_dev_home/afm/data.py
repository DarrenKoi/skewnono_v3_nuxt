"""Stable AFM data seam with mock/office adapters."""

from typing import Any

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.afm.contracts import AfmMeasurementRow


__all__ = [
    "AfmMeasurementRow",
    "normalize_tool",
    "get_tools",
    "list_afm_files",
    "get_afm_file_detail",
    "get_profile_points",
    "get_profile_image_svg",
    "list_analysis_images",
    "get_analysis_image_svg",
    "list_user_activities",
    "get_user_analytics",
]


def _provider():
    if get_data_provider("afm") == "office":
        from back_dev_home.afm.providers import office
        return office
    from back_dev_home.afm.providers import mock
    return mock


def normalize_tool(tool_name: str | None) -> str:
    return _provider().normalize_tool(tool_name)


def get_tools() -> list[dict[str, str]]:
    return _provider().get_tools()


def list_afm_files(tool_name: str | None = None) -> list[AfmMeasurementRow]:
    return _provider().list_afm_files(tool_name)


def get_afm_file_detail(
    filename: str,
    tool_name: str | None = None,
) -> dict[str, Any] | None:
    return _provider().get_afm_file_detail(filename, tool_name)


def get_profile_points(
    filename: str,
    point: str,
    tool_name: str | None = None,
    site_info: dict[str, str | int | None] | None = None,
) -> list[dict[str, float]] | None:
    return _provider().get_profile_points(filename, point, tool_name, site_info)


def get_profile_image_svg(
    filename: str,
    point: str,
    tool_name: str | None = None,
) -> str | None:
    return _provider().get_profile_image_svg(filename, point, tool_name)


def list_analysis_images(
    filename: str,
    image_type: str,
    tool_name: str | None = None,
) -> list[dict[str, str]]:
    return _provider().list_analysis_images(filename, image_type, tool_name)


def get_analysis_image_svg(
    filename: str,
    image_type: str,
    name: str,
    tool_name: str | None = None,
) -> str | None:
    return _provider().get_analysis_image_svg(filename, image_type, name, tool_name)


def list_user_activities(
    user: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return _provider().list_user_activities(user, limit)


def get_user_analytics(days: int = 7) -> dict[str, Any]:
    return _provider().get_user_analytics(days)
