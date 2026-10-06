"""The office template against a fake Redis hash and a fake MinIO, at home.

Imports ``office_example`` directly (``office.py`` is gitignored and absent
here). The frames below are built the way docs/datatables/afm/afm_redis.txt
describes them — full object keys, null cells, ``NA`` times — which is exactly
what the mock never emits.
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


def _parquet(df: pd.DataFrame, metadata: dict[str, str] | None = None) -> bytes:
    table = pa.Table.from_pandas(df)
    if metadata:
        table = table.replace_schema_metadata({**(table.schema.metadata or {}), **{
            key.encode(): value.encode() for key, value in metadata.items()
        }})
    buffer = io.BytesIO()
    pq.write_table(table, buffer)
    return buffer.getvalue()


def _measurement(**cells) -> dict:
    row = {
        "unique_key": KEY, "filename": f"{NAME}.csv", "date": "261001",
        "formatted_date": "2026-10-01", "recipe_name": "NA_NECKING_SLIM",
        "lot_id": "5NNN0336", "slot_number": "01", "time": "0700",
        "tool_name": "5EAP1501", "fab": None, "point_count": 2.0,
        **{f"{kind}_dir_list": [] for kind in LISTS},
    }
    return {**row, **cells}


FULL = _measurement(
    data_dir_list=[f"{FOLDER}/detail_{part}.parquet" for part in ("information", "summary", "points")],
    profile_dir_list=[f"{FOLDER}/profile_{NAME}_0001_Height.parquet"],
    tiff_dir_list=[f"{FOLDER}/{NAME}_0001_Height.webp", f"{FOLDER}/{NAME}_0002_Height.webp"],
    raw_dir_list=[f"{FOLDER}/{NAME}.csv", f"{FOLDER}/{NAME}_0001_Height.tiff"],
)
# What the loader writes for a measurement it could not date or count.
BARE = _measurement(
    unique_key="NA#NA#OLD#02", filename="#NA#NA#OLD#02#NA#NA#x.csv", date="",
    formatted_date=None, time="NA", point_count=None, lot_id=None,
    profile_dir_list=[f"{FOLDER}/profile_x_0003_X000_Y-002_0001_Height.parquet"],
)

OBJECTS = {
    FULL["data_dir_list"][0]: _parquet(pd.DataFrame({"key": ["Lot ID", "Carrier ID"], "value": ["5NNN0336", None]})),
    FULL["data_dir_list"][1]: _parquet(pd.DataFrame({"Site": ["M1"], "ITEM": ["MEAN"], "H (nm)": [1.5]})),
    FULL["data_dir_list"][2]: _parquet(pd.DataFrame({
        "Point No": [1, 2], "Site ID": [None, None], "State": ["COMPLETED", "FAILED"], "H (nm)": [1.5, float("nan")],
    })),
    FULL["profile_dir_list"][0]: _parquet(
        pd.DataFrame({"X": [0.0, 1.0], "Y": [0.0, 0.0], "Z": [3.25, float("nan")]}),
        {"XUnit": "um", "YUnit": "um", "ZUnit": "nm", "DataSize": "2 x 1", "SurfaceSize": "1 x 0"},
    ),
    FULL["tiff_dir_list"][0]: b"RIFF....WEBP",
    FULL["raw_dir_list"][1]: b"II*\x00tiff",
}


class _Redis:
    def __init__(self, hashes):
        self.hashes = hashes

    def hget(self, key, field):
        return self.hashes.get((key, field))


@pytest.fixture(autouse=True)
def _stores(monkeypatch):
    hashes = {
        ("afm_d1_tools", "all"): _parquet(pd.DataFrame({
            "id": ["5eap1501"], "name": ["5EAP1501"], "fab": [None], "alias": [None],
        })),
        ("afm_d2_measurements", "5EAP1501"): _parquet(pd.DataFrame([FULL, BARE])),
    }
    office._hash_rows.cache_clear()
    monkeypatch.setattr(office, "_redis_client", lambda: _Redis(hashes))
    monkeypatch.setattr(office, "_object", lambda key: OBJECTS.get(key))
    yield
    office._hash_rows.cache_clear()


def test_tools_fall_back_to_the_name_and_an_empty_fab():
    assert office.get_tools() == [{"id": "5eap1501", "name": "5EAP1501", "label": "5EAP1501", "fab": ""}]
    assert_matches(office.get_tools()[0], AfmToolRow)


def test_rows_match_the_contract_with_nulls_and_basenames():
    full, bare = office.list_afm_files("5eap1501")
    for row in (full, bare):
        assert_matches(row, AfmMeasurementRow)
    # Keys are cut to names; flags follow the lists; a float count is an int.
    assert full["data_dir_list"] == ["detail_information.parquet", "detail_summary.parquet", "detail_points.parquet"]
    assert (full["has_data"], full["has_profile"], full["has_image"], full["has_align"]) == (True, True, True, False)
    assert full["point_count"] == 2 and full["fab"] == ""
    # Empty cells: null where the contract allows it, "" elsewhere — never "nan"/"None".
    assert (bare["formatted_date"], bare["time"], bare["point_count"], bare["lot_id"]) == (None, None, None, "")
    assert office.list_afm_files("MAP608") == []


def test_detail_reads_the_three_parquets_and_keys_points_by_position():
    detail = office.get_afm_file_detail(FULL["filename"], "5EAP1501")
    assert_matches(detail, AfmFileDetail)
    assert detail["information"] == {"Lot ID": "5NNN0336", "Carrier ID": ""}
    assert detail["available_points"] == ["0001", "0002"]
    assert detail["data"][1]["H (nm)"] is None  # NaN leaves as null
    # Looked up by measurement key too, and unknown is None.
    assert office.get_afm_file_detail(KEY, "5EAP1501")["filename"] == FULL["filename"]
    assert office.get_afm_file_detail("nope.csv", "5EAP1501") is None


def test_a_measurement_with_no_detail_takes_positions_from_its_file_names():
    detail = office.get_afm_file_detail(BARE["filename"], "5EAP1501")
    assert (detail["information"], detail["summary"], detail["data"]) == ({}, [], [])
    assert detail["available_points"] == ["0003_X000_Y-002_0001"]


def test_profile_points_and_declared_units():
    args = (FULL["filename"], "0001", "5EAP1501")
    assert office.get_profile_points(*args) == [{"x": 0.0, "y": 0.0, "z": 3.25}, {"x": 1.0, "y": 0.0, "z": None}]
    meta = office.get_profile_meta(*args)
    assert_matches(meta, AfmProfileMeta)
    assert meta == {"x_unit": "um", "y_unit": "um", "z_unit": "nm", "data_size": "2 x 1", "surface_size": "1 x 0"}
    assert office.get_profile_points(FULL["filename"], "0009", "5EAP1501") is None


def test_images_are_the_stored_bytes_and_only_a_listed_tiff_offers_an_original():
    name = "5EAP1501"
    first, second = office.list_analysis_images(FULL["filename"], "tiff", name)
    assert first["name"].endswith("_0001_Height.webp") and "original_url" in first
    assert "original_url" not in second
    assert office.get_analysis_image_svg(FULL["filename"], "tiff", first["name"], name) == b"RIFF....WEBP"
    assert office.get_profile_image_svg(FULL["filename"], "0001", name) == b"RIFF....WEBP"
    # Listed in Redis but gone from MinIO is a miss, not an error.
    assert office.get_analysis_image_svg(FULL["filename"], "tiff", second["name"], name) is None
    original = office.get_tiff_original(FULL["filename"], first["name"], name)
    assert original["filename"].endswith("_0001_Height.tiff") and original["data"].startswith(b"II*")
    assert office.get_tiff_original(FULL["filename"], second["name"], name) is None
    assert office.list_analysis_images(FULL["filename"], "bogus", name) == []
