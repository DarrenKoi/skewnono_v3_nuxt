"""The mock reproduces what the office confirmed about the raw AFM files.

Source: docs/datatables/afm/afm_raw_files.txt (office 확인 2026-10-02, three
replies). These are mock-only invariants, so they import the mock directly
instead of going through data.py — an office adapter is free to hold different
rows.
"""

import re

from backend.afm.providers import mock

DATE_TIME = r"#\d{6}#\d{6}#"
SITE_ID = r"\d{4}_X-?\d{3}_Y-?\d{3}"
SITE_ID_RECIPES = {"BSOXCMP_CORRELATION_36PT", "RL1A_LPCCMP_CMPWEAK2", "RX1A_M0A_COT_X_PDG"}
TOOLS = ("MAP608", "MAPC01", "5EAP1501")
ODD_RECIPE_NAMES = {"Fi-Tapping TEST", "RQQA_PFH_MONF (1)", "xy scanner opm", "zeroscan 5point pm"}


def _rows(tool):
    rows = mock.list_afm_files(tool)
    assert rows, f"mock must fabricate rows for {tool}"
    return rows


def _details(tool):
    return [(row, mock.get_afm_file_detail(row["filename"], tool)) for row in _rows(tool)]


def test_tools_and_fabs_follow_the_office_mapping():
    fabs = {tool["name"]: tool["fab"] for tool in mock.get_tools()}
    assert set(fabs) == set(TOOLS)
    assert fabs["MAPC01"] == "R3"
    assert fabs["5EAP1501"] == "M15"


def test_filename_field_order_differs_per_tool():
    # '#'-separated, empty slots spelled NA; every tool orders its fields differently.
    patterns = {
        "MAP608": DATE_TIME + r"[^#]+#[^#]+#[^#]+#(\d{6}|NA)#\.csv",
        "MAPC01": DATE_TIME + r"[^#]+#\d{2}#NA#NA#[^#]+_Info\.csv",
        "5EAP1501": DATE_TIME + r"[^#]+#[^#]+#[^#]+#NA#\.csv",
    }
    for tool, pattern in patterns.items():
        for row in _rows(tool):
            assert re.fullmatch(pattern, row["filename"]), row["filename"]


def test_old_map608_files_carry_na_where_the_start_time_goes():
    starts = {row["filename"].split("#")[6] for row in _rows("MAP608")}
    assert "NA" in starts
    assert any(start.isdigit() for start in starts)


def test_recipe_names_can_hold_spaces_and_parentheses():
    odd_rows = [
        (tool, row)
        for tool in TOOLS
        for row in _rows(tool)
        if row["recipe_name"] in ODD_RECIPE_NAMES
    ]
    assert {row["recipe_name"] for _, row in odd_rows} == ODD_RECIPE_NAMES
    # Every tool has such recipes, 5EAP1501 included.
    assert {tool for tool, _ in odd_rows} == set(TOOLS)
    # The file name is the lookup key, so such a name has to resolve as it is.
    for tool, row in odd_rows:
        assert mock.get_afm_file_detail(row["filename"], tool) is not None


def test_measurement_columns_follow_the_recipe_and_all_carry_nm():
    seen = set()
    for tool in TOOLS:
        for _, detail in _details(tool):
            for record in detail["summary"]:
                columns = [key for key in record if key not in ("Site", "ITEM")]
                assert columns and all("nm" in column for column in columns)
                seen.update(columns)
    confirmed = {
        "Left_H (nm)", "Right_H (nm)", "Ref_H (nm)", "Dishing_H (nm)",
        "Ref_Range (nm)", "Left_TRIM_H (nm)", "ROUGHNESS_RANGE (nm)", "Ra (nm)",
        "Rq (nm)", "Pad_1_H (nm)", "1_Minimum (nm)", "51_Minimum (nm)",
        "Bottom_H (nm)", "Top_H (nm)", "Line1_Residue_H (nm)", "RZ1_Minimum (nm)",
    }
    assert confirmed <= seen


def test_which_files_exist_is_decided_by_the_recipe():
    flag_keys = ("has_data", "has_profile", "has_image", "has_align", "has_tip")
    for tool in TOOLS:
        by_recipe = {}
        for row in _rows(tool):
            flags = tuple(row[key] for key in flag_keys)
            assert by_recipe.setdefault(row["recipe_name"], flags) == flags
    # MAPC01 writes a data CSV for some recipes and not for others.
    assert {row["has_data"] for row in _rows("MAPC01")} == {True, False}
    for row in _rows("MAPC01"):
        if not row["has_data"]:
            assert row["data_dir_list"] == ["no files"]
            detail = mock.get_afm_file_detail(row["filename"], "MAPC01")
            assert detail["summary"] == [] and detail["data"] == []
            assert detail["information"]


def test_5eap1501_has_no_profile():
    for row in _rows("5EAP1501"):
        assert row["has_profile"] is False
        assert row["profile_dir_list"] == ["no files"]
    row = _rows("5EAP1501")[0]
    point = mock.get_afm_file_detail(row["filename"], "5EAP1501")["available_points"][0]
    assert mock.get_profile_points(row["filename"], point, "5EAP1501") is None


def test_point_count_is_set_by_the_recipe_and_spans_1_to_36():
    by_recipe = {}
    for tool in TOOLS:
        for row in _rows(tool):
            assert by_recipe.setdefault(row["recipe_name"], row["point_count"]) == row["point_count"]
    assert min(by_recipe.values()) == 1
    assert max(by_recipe.values()) == 36
    assert by_recipe["BSOXCMP_CORRELATION_36PT"] == 36


def test_site_id_names_the_position_and_the_profile_file():
    saw_negative = False
    with_site_id = {tool: set() for tool in TOOLS}
    for tool in TOOLS:
        for row, detail in _details(tool):
            sites = detail["available_points"]
            assert len(sites) == row["point_count"]
            for name in row["profile_dir_list"]:
                assert name == "no files" or any(site in name for site in sites)
            for record in detail["data"]:
                with_site_id[tool].add("Site ID" in record)
                # Site X / Site Y come and go together with Site ID.
                assert ("Site X" in record) == ("Site Y" in record) == ("Site ID" in record)
                if "Site ID" not in record:
                    continue
                assert re.fullmatch(SITE_ID, record["Site ID"]), record["Site ID"]
                assert record["Site ID"] in sites
                position = f"_X{mock._signed(record['Site X'])}_Y{mock._signed(record['Site Y'])}"
                assert record["Site ID"].endswith(position)
                saw_negative = saw_negative or record["Site Y"] < 0
            if row["recipe_name"] in SITE_ID_RECIPES and detail["data"]:
                assert "Site ID" in detail["data"][0]
    assert saw_negative, "a Site ID such as 0002_X002_Y-001 must appear"
    # On all three tools some recipes record a Site ID and some do not.
    assert all(kinds == {True, False} for kinds in with_site_id.values()), with_site_id


def test_summary_blocks_are_named_by_method_and_a_file_can_hold_several():
    block_counts = set()
    blocks = set()
    for tool in TOOLS:
        for _, detail in _details(tool):
            names = {record["Site"] for record in detail["summary"]}
            block_counts.add(len(names))
            blocks |= names
    assert {1, 2} <= block_counts
    assert {"Profile_LEFT_UL", "Profile_RIGHT_UL"} <= blocks
    # A block is a method, never a Site ID.
    assert not any(re.fullmatch(SITE_ID, block) for block in blocks)


def test_a_file_can_lack_its_summary_or_its_data_table():
    shapes = {
        (bool(detail["summary"]), bool(detail["data"]))
        for tool in TOOLS
        for row, detail in _details(tool)
        if row["has_data"]
    }
    assert {(True, True), (False, True), (True, False)} <= shapes


def test_summary_is_the_statistics_of_its_block():
    detail = next(d for _, d in _details("MAP608") if d["summary"] and d["data"])
    block = detail["summary"][0]["Site"]
    column = next(key for key in detail["summary"][0] if key.endswith("(nm)"))
    values = [record[column] for record in detail["data"] if record["Method_ID"] == block]
    stats = {record["ITEM"]: record[column] for record in detail["summary"] if record["Site"] == block}
    assert stats["MIN"] == min(values)
    assert stats["MAX"] == max(values)
    assert stats["RANGE"] == round(max(values) - min(values), 2)


def test_state_and_method_id_take_the_observed_forms():
    states, method_types = set(), set()
    for tool in TOOLS:
        for _, detail in _details(tool):
            for record in detail["data"]:
                states.add(record["State"])
                method_types.add(type(record["Method_ID"]))
    assert states == {"COMPLETED", "FAILED", "STOPPED"}
    assert method_types == {str, int}


def test_pick_up_and_put_back_times_can_be_empty():
    for key in ("Last Pick Up Time", "Last Put Back Time"):
        values = {
            detail["information"][key]
            for tool in TOOLS
            for _, detail in _details(tool)
        }
        assert "" in values and len(values) > 1


def test_profile_grid_shape_follows_the_tool():
    def shape(tool, row):
        points = mock.get_profile_points(row["filename"], "any", tool)
        return len({p["x"] for p in points}), len({p["y"] for p in points})

    assert shape("MAP608", next(r for r in _rows("MAP608") if r["has_profile"])) == (512, 64)
    # MAPC01 mixes 1D lines (N×1) with 2D grids, so its shapes are not all alike.
    shapes = {shape("MAPC01", r) for r in [r for r in _rows("MAPC01") if r["has_profile"]][:8]}
    assert any(ny == 1 for _, ny in shapes)
    assert len(shapes) > 1
