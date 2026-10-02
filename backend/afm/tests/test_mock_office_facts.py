"""The mock reproduces what the office confirmed about the raw AFM files.

Source: docs/datatables/afm/afm_raw_files.txt (office 확인 2026-10-02). These
are mock-only invariants, so they import the mock directly instead of going
through data.py — an office adapter is free to hold different rows.
"""

import re

from backend.afm.providers import mock

DATE_TIME = r"#\d{6}#\d{6}#"


def _rows(tool):
    rows = mock.list_afm_files(tool)
    assert rows, f"mock must fabricate rows for {tool}"
    return rows


def test_tools_and_fabs_follow_the_office_mapping():
    fabs = {tool["name"]: tool["fab"] for tool in mock.get_tools()}
    assert set(fabs) == {"MAP608", "MAPC01", "5EAP1501"}
    assert fabs["MAPC01"] == "R3"
    assert fabs["5EAP1501"] == "M15"


def test_filename_field_order_differs_per_tool():
    # '#'-separated, empty slots spelled NA; every tool orders its fields differently.
    patterns = {
        "MAP608": DATE_TIME + r"[^#]+#[^#]+#[^#]+#\d{6}#\.csv",
        "MAPC01": DATE_TIME + r"[^#]+#\d{2}#NA#NA#[^#]+_Info\.csv",
        "5EAP1501": DATE_TIME + r"[^#]+#[^#]+#[^#]+#NA#\.csv",
    }
    for tool, pattern in patterns.items():
        for row in _rows(tool):
            assert re.fullmatch(pattern, row["filename"]), row["filename"]


def test_measurement_columns_are_per_tool_and_all_carry_nm():
    prefixes = {"MAP608": r"Pad_\d+_H \(nm\)", "5EAP1501": r"\d+_Minimum \(nm\)"}
    for tool, pattern in prefixes.items():
        row = _rows(tool)[0]
        summary = mock.get_afm_file_detail(row["filename"], tool)["summary"]
        columns = [key for key in summary[0] if key not in ("Site", "ITEM")]
        assert columns
        assert all(re.fullmatch(pattern, column) for column in columns), columns


def test_summary_is_the_statistics_of_the_data_rows():
    row = _rows("MAP608")[0]
    detail = mock.get_afm_file_detail(row["filename"], "MAP608")
    site = detail["available_points"][0]
    column = next(key for key in detail["summary"][0] if key.endswith("(nm)"))
    values = [r[column] for r in detail["data"] if r["measurement_point"] == site]
    stats = {r["ITEM"]: r[column] for r in detail["summary"] if r["Site"] == site}
    assert stats["MIN"] == min(values)
    assert stats["MAX"] == max(values)
    assert stats["RANGE"] == round(max(values) - min(values), 2)


def test_mapc01_has_no_data_csv():
    for row in _rows("MAPC01"):
        assert row["has_data"] is False
        assert row["data_dir_list"] == ["no files"]
    detail = mock.get_afm_file_detail(_rows("MAPC01")[0]["filename"], "MAPC01")
    assert detail["summary"] == []
    assert detail["data"] == []
    assert detail["information"]


def test_5eap1501_has_no_profile():
    for row in _rows("5EAP1501"):
        assert row["has_profile"] is False
        assert row["profile_dir_list"] == ["no files"]
    row = _rows("5EAP1501")[0]
    point = mock.get_afm_file_detail(row["filename"], "5EAP1501")["available_points"][0]
    assert mock.get_profile_points(row["filename"], point, "5EAP1501") is None


def test_profile_grid_shape_follows_the_tool():
    def grid(tool):
        row = next(r for r in _rows(tool) if r["has_profile"])
        points = mock.get_profile_points(row["filename"], "any", tool)
        return len({p["x"] for p in points}), len({p["y"] for p in points})

    assert grid("MAP608") == (512, 64)
    # MAPC01 mixes 1D lines (N×1) with 2D grids, so its shapes are not all alike.
    shapes = {
        tuple(
            len({p[axis] for p in mock.get_profile_points(r["filename"], "any", "MAPC01")})
            for axis in ("x", "y")
        )
        for r in _rows("MAPC01")[:8] if r["has_profile"]
    }
    assert any(ny == 1 for _, ny in shapes)
    assert len(shapes) > 1
