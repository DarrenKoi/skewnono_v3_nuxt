"""Contract gate for afm. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/afm
Office: SKEWNONO_AFM_PROVIDER=office .venv/bin/pytest back_dev_home/afm

The shape checks below are meaningful under both providers. What is NOT
provider-independent is that data EXISTS: the mock generates a fixed row set
per tool from a static TOOL_CONFIGS table, while a live AFM index can
legitimately hold nothing for the default tool. Those assumptions are fenced
behind get_data_provider("afm") == "mock" so the office run cannot go green on
a mock-only invariant — nor red on an empty-but-valid office listing.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.afm import data
from back_dev_home.afm.contracts import (
    AfmFileDetail,
    AfmMeasurementRow,
    AfmProfilePoint,
    AfmToolRow,
    AfmUserActivity,
    AfmUserAnalytics,
)


def _first_file() -> AfmMeasurementRow:
    """A measurement row for the detail/profile/image lookups to key off.

    The mock always fabricates rows for the default tool; an office listing may
    be empty, and there is then no filename to look anything up by.
    """
    rows = data.list_afm_files(None)
    if not rows:
        pytest.skip("active provider returned no AFM files")
    return rows[0]


def _first_point(detail: AfmFileDetail) -> str:
    """A site code valid for the /profile and /image arguments, or a skip."""
    points = detail["available_points"]
    if get_data_provider("afm") == "mock":
        # No other test covers this list, so assert it mock-side rather than let
        # a broken generator silently turn the profile/image gates into skips.
        assert points, "mock file detail must advertise available_points"
    if not points:
        pytest.skip("active provider reported no available_points for this file")
    return points[0]


def _detail_of(row: AfmMeasurementRow) -> AfmFileDetail:
    detail = data.get_afm_file_detail(row["filename"], row["tool_name"])
    # The filename came out of the listing, so the lookup MUST resolve it under
    # either provider — a None here is a real bug, not an empty index.
    assert detail is not None, f"a listed file ({row['filename']}) must have detail"
    return detail


def test_get_tools_matches_contract():
    tools = data.get_tools()
    assert isinstance(tools, list)
    for tool in tools:
        assert_matches(tool, AfmToolRow)


def test_list_afm_files_matches_contract():
    rows = data.list_afm_files(None)
    assert isinstance(rows, list)
    for row in rows:
        assert_matches(row, AfmMeasurementRow)
    if get_data_provider("afm") == "mock":
        # The mock's generator emits a fixed number of rows per tool, so an
        # empty listing means it broke. Office may genuinely index nothing.
        assert rows, "mock AFM file listing must not be empty"


def test_get_afm_file_detail_matches_contract():
    assert_matches(_detail_of(_first_file()), AfmFileDetail)


def test_get_profile_points_returns_xyz_points():
    row = _first_file()
    point = _first_point(_detail_of(row))
    points = data.get_profile_points(row["filename"], point, row["tool_name"])
    assert isinstance(points, list)
    # A point advertised by available_points must have a height map behind it —
    # the profile view has nothing to plot otherwise. The mock's fixed 20x20
    # (400-point) grid size is deliberately NOT asserted; office grids differ.
    assert points, f"point {point!r} must resolve to profile samples"
    for entry in points:
        assert_matches(entry, AfmProfilePoint)


def test_get_profile_image_svg_returns_string():
    row = _first_file()
    point = _first_point(_detail_of(row))
    svg = data.get_profile_image_svg(row["filename"], point, row["tool_name"])
    assert isinstance(svg, str)
    assert svg


def test_list_user_activities_matches_contract():
    activities = data.list_user_activities(None, 5)
    assert isinstance(activities, list)
    for activity in activities:
        assert_matches(activity, AfmUserActivity)
    if get_data_provider("afm") == "mock":
        # The mock derives activities from its own fabricated MAP608 listing, so
        # they always exist; an office usage log can be empty for a user.
        assert activities, "mock AFM activity log must not be empty"


def test_get_user_analytics_matches_contract():
    analytics = data.get_user_analytics(7)
    assert_matches(analytics, AfmUserAnalytics)
