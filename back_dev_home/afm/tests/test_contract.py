"""Contract gate for afm. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/afm
Office: SKEWNONO_AFM_PROVIDER=office .venv/bin/pytest back_dev_home/afm
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.afm import data
from back_dev_home.afm.contracts import (
    AfmFileDetail,
    AfmMeasurementRow,
    AfmProfilePoint,
    AfmToolRow,
    AfmUserActivity,
    AfmUserAnalytics,
)


def test_get_tools_matches_contract():
    tools = data.get_tools()
    assert isinstance(tools, list)
    for tool in tools:
        assert_matches(tool, AfmToolRow)


def test_list_afm_files_matches_contract():
    rows = data.list_afm_files(None)
    assert isinstance(rows, list)
    assert rows
    for row in rows:
        assert_matches(row, AfmMeasurementRow)


def test_get_afm_file_detail_matches_contract():
    row = data.list_afm_files(None)[0]
    detail = data.get_afm_file_detail(row["filename"], row["tool_name"])
    assert detail is not None
    assert_matches(detail, AfmFileDetail)


def test_get_profile_points_returns_xyz_points():
    row = data.list_afm_files(None)[0]
    detail = data.get_afm_file_detail(row["filename"], row["tool_name"])
    point = detail["available_points"][0]
    points = data.get_profile_points(row["filename"], point, row["tool_name"])
    assert isinstance(points, list)
    assert points
    for entry in points:
        assert_matches(entry, AfmProfilePoint)


def test_get_profile_image_svg_returns_string():
    row = data.list_afm_files(None)[0]
    detail = data.get_afm_file_detail(row["filename"], row["tool_name"])
    point = detail["available_points"][0]
    svg = data.get_profile_image_svg(row["filename"], point, row["tool_name"])
    assert isinstance(svg, str)
    assert svg


def test_list_user_activities_matches_contract():
    activities = data.list_user_activities(None, 5)
    assert isinstance(activities, list)
    assert activities
    for activity in activities:
        assert_matches(activity, AfmUserActivity)


def test_get_user_analytics_matches_contract():
    analytics = data.get_user_analytics(7)
    assert_matches(analytics, AfmUserAnalytics)
