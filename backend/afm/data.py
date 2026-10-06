"""Stable AFM data seam with mock/office adapters."""

from typing import Any

from backend._runtime.data_provider import get_data_provider
from backend.afm.contracts import AfmMeasurementRow, AfmOriginalFile, AfmProfileMeta


__all__ = [
    "AfmMeasurementRow",
    "normalize_tool",
    "get_tools",
    "list_afm_files",
    "get_afm_file_detail",
    "get_profile_points",
    "get_profile_meta",
    "get_profile_image_svg",
    "list_analysis_images",
    "get_analysis_image_svg",
    "get_tiff_original",
]


def _provider():
    if get_data_provider("afm") == "office":
        from backend.afm.providers import office
        return office
    from backend.afm.providers import mock
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


def get_profile_meta(
    filename: str,
    point: str,
    tool_name: str | None = None,
) -> AfmProfileMeta | None:
    return _provider().get_profile_meta(filename, point, tool_name)


def get_profile_image_svg(
    filename: str,
    point: str,
    tool_name: str | None = None,
) -> str | bytes | None:
    # str is an SVG document (the mock's placeholder), bytes the stored webp.
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
) -> str | bytes | None:
    return _provider().get_analysis_image_svg(filename, image_type, name, tool_name)


def get_tiff_original(
    filename: str,
    name: str,
    tool_name: str | None = None,
) -> AfmOriginalFile | None:
    return _provider().get_tiff_original(filename, name, tool_name)
