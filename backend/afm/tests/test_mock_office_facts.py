"""The mock reproduces what the office confirmed about the raw AFM files.

Source: docs/datatables/afm/afm_raw_files.txt (office 확인 2026-10-02, four
replies). These are mock-only invariants, so they import the mock directly
instead of going through data.py — an office adapter is free to hold different
rows.
"""

import re
from collections import Counter

from backend.afm.providers import mock

DATE_TIME = r"#\d{6}#\d{6}#"
SITE_ID = r"\d{4}_X-?\d{3}_Y-?\d{3}"
SITE_ID_RECIPES = {"BSOXCMP_CORRELATION_36PT", "RL1A_LPCCMP_CMPWEAK2", "RX1A_M0A_COT_X_PDG"}
TOOLS = ("MAP608", "MAPC01", "5EAP1501")
ODD_RECIPE_NAMES = {"Fi-Tapping TEST", "RQQA_PFH_MONF (1)", "xy scanner opm", "zeroscan 5point pm"}
PROFILE_UNITS = {"um", "nm", "pm", "Pixel"}


def _rows(tool):
    rows = mock.list_afm_files(tool)
    assert rows, f"mock must fabricate rows for {tool}"
    return rows


def _details(tool):
    return [(row, mock.get_afm_file_detail(row["filename"], tool)) for row in _rows(tool)]


def _all_details():
    return [(tool, row, detail) for tool in TOOLS for row, detail in _details(tool)]


def _has_measurement(record):
    return any(key.endswith("(nm)") for key in record)


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
        "5EAP1501": DATE_TIME + r"[^#]+#[^#]+#[^#]+#NA#[^#]+\.csv",
    }
    for tool, pattern in patterns.items():
        for row in _rows(tool):
            assert re.fullmatch(pattern, row["filename"]), row["filename"]


def test_5eap1501_name_ends_with_the_original_file_name():
    # RECIPE + LOT + SAMPLE run together with no separator, then an optional suffix.
    suffixes = set()
    for row in _rows("5EAP1501"):
        _, _, _, recipe, sample, lot, _, tail = row["filename"].split("#")
        assert sample == f"{row['lot_id']}.{row['slot_number']}"
        original = recipe + lot + sample
        assert tail.startswith(original) and tail.endswith(".csv"), tail
        suffixes.add(tail[len(original):-len(".csv")])
    assert "" in suffixes and len(suffixes) > 1


def test_map608_measurements_of_one_session_share_the_leading_time():
    rows = _rows("MAP608")
    assert len({row["filename"] for row in rows}) == len(rows)
    sessions = Counter((row["date"], row["time"]) for row in rows)
    assert max(sessions.values()) > 1
    for row in rows:
        start = row["filename"].split("#")[6]
        start_time = mock.get_afm_file_detail(row["filename"], "MAP608")["information"]["Start Time"]
        # The trailing field is the measurement start; an old file has NA there and
        # its Info Start Time then equals the leading (session) time.
        clock = start if start.isdigit() else row["time"]
        assert start_time == f"{row['formatted_date']} {clock[:2]}:{clock[2:4]}:{clock[4:]}"
    starts = [row["filename"].split("#")[6] for row in rows]
    assert "NA" in starts
    # Within a session the starts differ, which is what tells its measurements apart.
    known = [(row["date"], row["time"], start) for row, start in zip(rows, starts, strict=True) if start.isdigit()]
    assert len(set(known)) == len(known)


def test_mapc01_lot_comes_from_info_and_a_sample_is_remeasured_within_a_day():
    rows = _rows("MAPC01")
    for row in rows:
        assert row["lot_id"] != "NA"
        info = mock.get_afm_file_detail(row["filename"], "MAPC01")["information"]
        assert info["Lot ID"] == row["lot_id"]
        # Every MAPC01 measurement has an Info CSV; the data CSV is the same name without _Info.
        assert row["filename"].endswith("_Info.csv")
        if row["has_data"]:
            assert row["data_dir_list"] == [row["filename"].replace("_Info.csv", ".csv")]
    # A measurement is its first four fields: date#time#recipe#slot.
    groups = [tuple(row["filename"].split("#")[1:5]) for row in rows]
    assert len(set(groups)) == len(groups)
    samples = Counter((date, recipe, slot) for date, _, recipe, slot in groups)
    assert max(samples.values()) > 1


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
    for _, _, detail in _all_details():
        for record in detail["summary"]:
            columns = [key for key in record if key not in ("Site", "ITEM")]
            assert columns and all("nm" in column for column in columns)
            seen.update(columns)
    confirmed = {
        "Left_H (nm)", "Right_H (nm)", "Ref_H (nm)", "Dishing_H (nm)",
        "Ref_Range (nm)", "Left_TRIM_H (nm)", "ROUGHNESS_RANGE (nm)", "Ra (nm)",
        "Rq (nm)", "Pad_1_H (nm)", "1_Minimum (nm)", "51_Minimum (nm)",
        "Bottom_H (nm)", "Top_H (nm)", "Line1_Residue_H (nm)", "RZ1_Minimum (nm)",
        "SITE19_21_H (nm)",
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
    assert mock.get_profile_meta(row["filename"], point, "5EAP1501") is None


def test_point_count_is_set_by_the_recipe_and_spans_1_to_36():
    by_recipe = {}
    for tool in TOOLS:
        for row in _rows(tool):
            assert by_recipe.setdefault(row["recipe_name"], row["point_count"]) == row["point_count"]
    assert min(by_recipe.values()) == 1
    assert max(by_recipe.values()) == 36
    assert by_recipe["BSOXCMP_CORRELATION_36PT"] == 36


def test_a_position_is_keyed_by_its_point_number_and_by_site_id_where_recorded():
    saw_negative = False
    saw_several_points_on_one_site = False
    with_site_id = {tool: set() for tool in TOOLS}
    for tool, row, detail in _all_details():
        keys = detail["available_points"]
        assert len(keys) == len(set(keys)) == row["point_count"]
        for name in row["profile_dir_list"]:
            # _0001_Height.txt, or _0004_X000_Y-002_0002_Height.txt on a Site ID recipe.
            assert name == "no files" or any(name.endswith(f"_{key}_Height.txt") for key in keys), name
        site_points = Counter()
        for record in detail["data"][:row["point_count"]]:
            with_site_id[tool].add("Site ID" in record)
            point = f"{record['Point No']:04d}"
            # Site X / Site Y come and go together with Site ID.
            assert ("Site X" in record) == ("Site Y" in record) == ("Site ID" in record)
            if "Site ID" not in record:
                assert record["measurement_point"] == point
                continue
            assert re.fullmatch(SITE_ID, record["Site ID"]), record["Site ID"]
            assert record["measurement_point"] == f"{record['Site ID']}_{point}"
            position = f"_X{mock._signed(record['Site X'])}_Y{mock._signed(record['Site Y'])}"
            assert record["Site ID"].endswith(position)
            saw_negative = saw_negative or record["Site Y"] < 0
            site_points[record["Site ID"]] += 1
        assert all(record["measurement_point"] in keys for record in detail["data"])
        saw_several_points_on_one_site |= any(count > 1 for count in site_points.values())
        if row["recipe_name"] in SITE_ID_RECIPES and detail["data"]:
            assert "Site ID" in detail["data"][0]
    assert saw_negative, "a Site ID such as 0002_X002_Y-001 must appear"
    assert saw_several_points_on_one_site, "a key such as 0004_X000_Y-002_0002 must appear"
    # On all three tools some recipes record a Site ID and some do not.
    assert all(kinds == {True, False} for kinds in with_site_id.values()), with_site_id


def test_summary_blocks_are_named_by_method_and_a_file_can_hold_several():
    block_counts = set()
    blocks = set()
    for _, _, detail in _all_details():
        names = {record["Site"] for record in detail["summary"]}
        block_counts.add(len(names))
        blocks |= names
    assert {1, 2} <= block_counts
    assert {"Profile_LEFT_UL", "Profile_RIGHT_UL"} <= blocks
    # A block is a method, never a Site ID.
    assert not any(re.fullmatch(SITE_ID, block) for block in blocks)


def test_a_block_can_stop_and_then_has_no_measurement_columns():
    stopped_files = 0
    for _, row, detail in _all_details():
        bare = [record for record in detail["data"] if not _has_measurement(record)]
        if not bare:
            continue
        stopped_files += 1
        assert all(record["State"] == "STOPPED" for record in bare)
        # The stopped block is the later one, still one row per point, with no Summary.
        assert bare == detail["data"][row["point_count"]:]
        assert len(bare) == row["point_count"]
        assert len({record["Site"] for record in detail["summary"]}) <= 1
    assert stopped_files


def test_blocks_cannot_be_told_apart_by_method_id():
    method_ids = set()
    for _, row, detail in _all_details():
        ids = {record["Method_ID"] for record in detail["data"]}
        # One value across every block of a file: blocks match by position only.
        assert len(ids) <= 1
        method_ids |= ids
        if row["recipe_name"] == "RL1C_L1_XDEC_5MM_LINE" and ids:
            assert ids == {"L1_XDEC_5MM_LINE"}
    assert {type(value) for value in method_ids} == {str, int}


def test_a_file_can_lack_its_summary_or_its_data_table():
    shapes = {
        (bool(detail["summary"]), bool(detail["data"]))
        for _, row, detail in _all_details()
        if row["has_data"]
    }
    assert {(True, True), (False, True), (True, False)} <= shapes


def test_each_summary_block_is_the_statistics_of_the_data_block_at_its_position():
    checked = 0
    for _, row, detail in _all_details():
        blocks = list(dict.fromkeys(record["Site"] for record in detail["summary"]))
        points = row["point_count"]
        # Two populated blocks: with one, position could not be told from identity.
        if len(blocks) != 2 or len(detail["data"]) != 2 * points:
            continue
        checked += 1
        column = next(key for key in detail["summary"][0] if key.endswith("(nm)"))
        for position, block in enumerate(blocks):
            values = [r[column] for r in detail["data"][position * points:(position + 1) * points]]
            stats = {r["ITEM"]: r[column] for r in detail["summary"] if r["Site"] == block}
            assert stats["MIN"] == min(values)
            assert stats["MAX"] == max(values)
            assert stats["RANGE"] == round(max(values) - min(values), 2)
    assert checked


def test_a_single_point_summary_reports_zero_spread():
    singles = [
        detail for _, row, detail in _all_details()
        if row["point_count"] == 1 and detail["summary"]
    ]
    assert singles
    for detail in singles:
        for record in detail["summary"]:
            if record["ITEM"] in ("STDEV", "RANGE"):
                assert all(value == 0.0 for key, value in record.items() if key.endswith("(nm)"))


def test_states_are_the_three_observed():
    states = {record["State"] for _, _, detail in _all_details() for record in detail["data"]}
    assert states == {"COMPLETED", "FAILED", "STOPPED"}


def test_info_values_can_be_empty_strings():
    for key in ("Carrier ID", "Last Pick Up Time", "Last Put Back Time"):
        values = {detail["information"][key] for _, _, detail in _all_details()}
        assert "" in values and len(values) > 1


def test_profile_grid_shape_and_units_follow_the_file():
    def shape(points):
        return len({p["x"] for p in points}), len({p["y"] for p in points})

    def profile(tool, row):
        points = mock.get_profile_points(row["filename"], "any", tool)
        meta = mock.get_profile_meta(row["filename"], "any", tool)
        nx, ny = shape(points)
        # DataSize is what separates a 1D line from a 2D grid; a line sits on Y = 0.
        assert meta["data_size"] == f"{nx} x {ny}"
        if ny == 1:
            assert {p["y"] for p in points} == {0}
        units = (meta["x_unit"], meta["y_unit"], meta["z_unit"])
        assert set(units) <= PROFILE_UNITS
        assert meta["surface_size"]
        return (nx, ny), units

    grid, units = profile("MAP608", next(r for r in _rows("MAP608") if r["has_profile"]))
    assert grid == (512, 64)
    assert units == ("um", "um", "nm")
    # MAPC01 mixes 1D lines (N×1) with 2D grids, and the units differ from file to file.
    seen = [profile("MAPC01", r) for r in _rows("MAPC01") if r["has_profile"]]
    assert any(ny == 1 for (_, ny), _ in seen)
    assert len({grid for grid, _ in seen}) > 1
    # Every unit the office listed turns up, Pixel included.
    assert {unit for _, units in seen for unit in units} == PROFILE_UNITS
