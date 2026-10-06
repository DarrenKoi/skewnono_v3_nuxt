"""The office template against a fake Redis hash and a fake MinIO, at home.

Imports ``office_example`` directly (``office.py`` is gitignored and absent
here). The frames below are built the way docs/datatables/afm/afm_redis.txt
describes them — full object keys, null cells, ``NA`` times, and detail values
that are all text — which is exactly what the mock never emits.
"""

import io

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from backend._core.contract_check import assert_matches
from backend.afm.contracts import AfmFileDetail, AfmMeasurementRow, AfmProfileMeta, AfmToolRow
from backend.afm.providers import office_example as office

KEY = "261001#070028#NA_NECKING_SLIM#5NNN0336.01#5NNN0336#NA"
FOLDER = f"2067928/afm/5EAP1501/{KEY}"
NAME = f"#{KEY}#NA_NECKING_SLIM5NNN03365NNN0336.01"
LISTS = ("data", "profile", "tiff", "align", "tip", "capture", "raw")


def _parquet(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    pq.write_table(pa.Table.from_pandas(df), buffer)
    return buffer.getvalue()


def _measurement(**cells) -> dict:
    row = {
        "unique_key": KEY, "filename": f"{NAME}.csv", "date": "261001",
        "formatted_date": "2026-10-01", "recipe_name": "NA_NECKING_SLIM",
        "lot_id": "5NNN0336", "slot_number": "01", "time": "070028",
        "measured_info": None, "tool_name": "5EAP1501", "fab": None, "point_count": 2.0,
        **{f"{kind}_dir_list": [] for kind in LISTS},
    }
    return {**row, **cells}


FULL = _measurement(
    data_dir_list=[f"{FOLDER}/detail_{part}.parquet" for part in ("information", "summary", "points")],
    profile_dir_list=[f"{FOLDER}/profile_{NAME}_0001_Height.parquet"],
    # Each webp, and beside the first the original it was converted from.
    tiff_dir_list=[
        f"{FOLDER}/{NAME}_0001_Height.webp", f"{FOLDER}/{NAME}_0002_Height.webp",
        f"{FOLDER}/{NAME}_0001_Height.tiff",
    ],
    raw_dir_list=[f"{FOLDER}/{NAME}.csv"],
)
# What the loader writes for a measurement it could not date or count, and one
# that has an info CSV only: its data list still holds the information object.
BARE = _measurement(
    unique_key="NA#NA#OLD#02", filename="#NA#NA#OLD#02#NA#NA#x_Info.csv", date="",
    formatted_date=None, time="NA", point_count=None, lot_id=None,
    data_dir_list=[f"{FOLDER}/bare/detail_information.parquet"],
    profile_dir_list=[f"{FOLDER}/profile_x_0003_X000_Y-002_0001_Height.parquet"],
)
# Summary-less: the object is there, with no rows and no columns.
NO_SUMMARY = _measurement(
    unique_key="261002#080000#R#03", filename="#261002#080000#R#03#NA#NA#y.csv", date="261002",
    data_dir_list=[f"{FOLDER}/ns/detail_summary.parquet", f"{FOLDER}/ns/detail_points.parquet"],
)

# Every detail value is text: numbers, the point number, an unmeasured cell
# (one space) and an unset _Valid (empty).
POINTS = pd.DataFrame({
    "Site": ["M1", "M1", "M2"],
    "Point No": ["1", "2", "1"],
    "Site ID": ["0001_X000_Y000", "0002_X-001_Y002", "0001_X000_Y000"],
    "Site X": ["0", "-1", "0"],
    "Site Y": ["0", "2", "0"],
    "State": ["COMPLETED", "FAILED", "STOPPED"],
    "Valid": ["TRUE", "FALSE", ""],
    "Method ID": ["2", "2", "2"],
    "H (nm)": ["79.24", "80", " "],
    "H_Valid": ["TRUE", "TRUE", ""],
})

OBJECTS = {
    FULL["data_dir_list"][0]: _parquet(pd.DataFrame({"name": ["Lot ID", "Carrier ID"], "value": ["5NNN0336", ""]})),
    FULL["data_dir_list"][1]: _parquet(pd.DataFrame({"Site": ["M1"], "ITEM": ["MEAN"], "H (nm)": ["79.62"]})),
    FULL["data_dir_list"][2]: _parquet(POINTS),
    FULL["profile_dir_list"][0]: _parquet(pd.DataFrame({"X": [0.0, 1.0], "Y": [0.0, 0.0], "Z": [3.25, float("nan")]})),
    FULL["tiff_dir_list"][0]: b"RIFF....WEBP",
    FULL["tiff_dir_list"][2]: b"II*\x00tiff",
    BARE["data_dir_list"][0]: _parquet(pd.DataFrame({"name": ["Lot ID"], "value": ["OLD1"]})),
    NO_SUMMARY["data_dir_list"][0]: _parquet(pd.DataFrame()),
    NO_SUMMARY["data_dir_list"][1]: _parquet(POINTS.drop(columns=["Site ID", "Site X", "Site Y"]).head(1)),
}
# The units ride on the MinIO object, lower-cased, not in the parquet file.
METADATA = {
    FULL["profile_dir_list"][0]: {
        "x-amz-meta-xunit": "um", "x-amz-meta-yunit": "um", "x-amz-meta-zunit": "nm",
        "x-amz-meta-datasize": "2 x 1", "x-amz-meta-surfacesize": "1 x 0", "content-type": "x",
    },
}


class _Gone(Exception):
    code = "NoSuchKey"


class _Store:
    def stat(self, key):
        if key not in METADATA:
            raise _Gone(key)
        return type("Stat", (), {"metadata": METADATA[key]})()


class _Redis:
    def __init__(self, hashes):
        self.hashes = hashes

    def hget(self, key, field):
        return self.hashes.get((key, field))


@pytest.fixture(autouse=True)
def _stores(monkeypatch):
    hashes = {
        ("afm_d1_tools", "all"): _parquet(pd.DataFrame({
            "id": ["MAP608", "5EAP1501"], "name": ["MAP608", "5EAP1501"],
            "fab": ["", ""], "alias": [None, "M15"],
        })),
        ("afm_d2_measurements", "5EAP1501"): _parquet(pd.DataFrame([FULL, BARE, NO_SUMMARY])),
    }
    office._hash_rows.cache_clear()
    monkeypatch.setattr(office, "_redis_client", lambda: _Redis(hashes))
    monkeypatch.setattr(office, "_object", lambda key: OBJECTS.get(key))
    monkeypatch.setattr(office, "_store", lambda: _Store())
    yield
    office._hash_rows.cache_clear()


def _row(key):
    return next(row for row in office.list_afm_files("5eap1501") if row["unique_key"] == key)


def test_tools_take_the_fab_from_alias_and_a_lower_case_slug():
    tools = office.get_tools()
    assert tools == [
        {"id": "map608", "name": "MAP608", "label": "MAP608", "fab": ""},
        {"id": "5eap1501", "name": "5EAP1501", "label": "5EAP1501", "fab": "M15"},
    ]
    for tool in tools:
        assert_matches(tool, AfmToolRow)


def test_rows_match_the_contract_with_nulls_and_basenames():
    rows = office.list_afm_files("5eap1501")
    assert [row["unique_key"] for row in rows] == [NO_SUMMARY["unique_key"], KEY, BARE["unique_key"]]  # newest first
    for row in rows:
        assert_matches(row, AfmMeasurementRow)
    full, bare = _row(KEY), _row(BARE["unique_key"])
    # Keys are cut to names; a float count is an int; the always-null column is "".
    assert full["data_dir_list"] == ["detail_information.parquet", "detail_summary.parquet", "detail_points.parquet"]
    assert (full["has_data"], full["has_profile"], full["has_image"], full["has_align"]) == (True, True, True, False)
    assert (full["point_count"], full["fab"], full["measured_info"], full["time"]) == (2, "", "", "070028")
    # Empty cells: null where the contract allows it, "" elsewhere — never "nan"/"None".
    assert (bare["formatted_date"], bare["time"], bare["point_count"], bare["lot_id"]) == (None, None, None, "")
    # An info-only measurement lists its information object and still has no data.
    assert bare["data_dir_list"] == ["detail_information.parquet"] and bare["has_data"] is False
    assert office.list_afm_files("MAP608") == []


def test_detail_turns_the_loaded_text_into_typed_cells():
    detail = office.get_afm_file_detail(FULL["filename"], "5EAP1501")
    assert_matches(detail, AfmFileDetail)
    assert detail["information"] == {"Lot ID": "5NNN0336", "Carrier ID": None}
    assert detail["summary"] == [{"Site": "M1", "ITEM": "MEAN", "H (nm)": 79.62}]
    first, second, stopped = detail["data"]
    assert first == {
        "measurement_point": "0001_X000_Y000_0001", "Site": "M1", "Point No": 1,
        "Site ID": "0001_X000_Y000", "Site X": 0, "Site Y": 0, "State": "COMPLETED",
        "Valid": True, "Method ID": "2", "H (nm)": 79.24, "H_Valid": True,
    }
    assert (second["Site X"], second["Site Y"], second["Valid"], second["H (nm)"]) == (-1, 2, False, 80.0)
    # An unmeasured cell (" ") and an unset _Valid ("") are None — not 0, not False.
    assert (stopped["Site"], stopped["H (nm)"], stopped["H_Valid"], stopped["Valid"]) == ("M2", None, None, None)
    assert detail["available_points"] == ["0001_X000_Y000_0001", "0002_X-001_Y002_0002"]
    # Looked up by measurement key too, and unknown is None.
    assert office.get_afm_file_detail(KEY, "5EAP1501")["filename"] == FULL["filename"]
    assert office.get_afm_file_detail("nope.csv", "5EAP1501") is None


def test_detail_without_a_summary_or_without_a_data_csv():
    detail = office.get_afm_file_detail(NO_SUMMARY["filename"], "5EAP1501")
    assert detail["summary"] == [] and detail["available_points"] == ["0001"]
    bare = office.get_afm_file_detail(BARE["filename"], "5EAP1501")
    assert (bare["information"], bare["summary"], bare["data"]) == ({"Lot ID": "OLD1"}, [], [])
    # No points to read positions from: they come off the profile names.
    assert bare["available_points"] == ["0003_X000_Y-002_0001"]


def test_profile_points_and_units_from_the_object_metadata():
    args = (FULL["filename"], "0001", "5EAP1501")
    assert office.get_profile_points(*args) == [{"x": 0.0, "y": 0.0, "z": 3.25}, {"x": 1.0, "y": 0.0, "z": None}]
    meta = office.get_profile_meta(*args)
    assert_matches(meta, AfmProfileMeta)
    assert meta == {"x_unit": "um", "y_unit": "um", "z_unit": "nm", "data_size": "2 x 1", "surface_size": "1 x 0"}
    assert office.get_profile_points(FULL["filename"], "0009", "5EAP1501") is None
    # Listed in Redis, gone from MinIO (retention deletes MinIO first): a miss.
    assert office.get_profile_meta(BARE["filename"], "0003_X000_Y-002_0001", "5EAP1501") is None


def test_the_result_list_shows_webps_and_offers_the_tiff_beside_one():
    name = "5EAP1501"
    assert _row(KEY)["tiff_dir_list"][2].endswith("_0001_Height.tiff")
    first, second = office.list_analysis_images(FULL["filename"], "tiff", name)
    assert first["name"].endswith("_0001_Height.webp") and "original_url" in first
    assert second["name"].endswith("_0002_Height.webp") and "original_url" not in second
    assert office.get_analysis_image_svg(FULL["filename"], "tiff", first["name"], name) == b"RIFF....WEBP"
    assert office.get_profile_image_svg(FULL["filename"], "0001", name) == b"RIFF....WEBP"
    # Listed but not in MinIO is a miss; a TIFF is never served as a gallery image.
    assert office.get_analysis_image_svg(FULL["filename"], "tiff", second["name"], name) is None
    tiff_name = first["name"].replace(".webp", ".tiff")
    assert office.get_analysis_image_svg(FULL["filename"], "tiff", tiff_name, name) is None
    original = office.get_tiff_original(FULL["filename"], first["name"], name)
    assert original["filename"] == tiff_name and original["data"].startswith(b"II*")
    assert office.get_tiff_original(FULL["filename"], second["name"], name) is None
    assert office.list_analysis_images(FULL["filename"], "bogus", name) == []
