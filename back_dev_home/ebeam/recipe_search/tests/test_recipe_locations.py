"""measurement-locations: the mock contract, and the office mapping at home.

The office path is one OpenSearch query and a pure mapping. The query is
unreachable from home; the mapping (`_to_locations_response`) takes a version
document's `_source` and is what would be wrong if the ingested blob shape
differs from what idp_ver.txt records — so it is fed hand-built documents
here, the way test_idp_mapping.py feeds `_to_detail_response`.
"""

import json

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.recipe_search import data
from back_dev_home.ebeam.recipe_search.contracts import RecipeLocationsResponse
from back_dev_home.ebeam.recipe_search.providers import office_example


RECIPE = "RACE/DEAE_ABC123_PROD_00001"

_ROW = {
    "Parameter": "WAFER", "img_add1": "IMMP0001", "img_add2": "non",
    "img_meas1": "IMMS0001", "img_meas2": "PRMS0001", "SEQ": 1, "Last_SEQ": 1,
    "Region": 1, "image_add3": "non", "Addressing": True, "Mother_Para": True,
    "Double_Addressing": False, "Meas_Counting": 3, "dnumber_removed": False,
}
_POINT = {
    "ChipNo_X": 1, "ChipNo_Y": 2, "Coordinate_X": 1.5, "Coordinate_Y": -1.5,
    "P_No": 1, "D_No": 7, "Diff": False, "Rel": True, "Rel_MoveX": 0.1,
    "Rel_MoveY": 0.2, "Coordinate_X_r": 1.6, "Coordinate_Y_r": -1.3,
    "Parameter": "WAFER", "img_meas2": 1,
}


def test_mock_matches_contract_and_agrees_with_recipe_open():
    body = data.get_recipe_locations("cd-sem", RECIPE, "R3")
    assert body is not None
    assert_matches(body, RecipeLocationsResponse)
    detail = data.get_recipe_open_data(RECIPE, "R3", "cd-sem")
    assert body["parameter_rows"] == detail["idp_image_info"]
    assert body["points"] == detail["wafer_mp_info"]


def test_mock_answers_none_for_a_recipe_it_cannot_place():
    assert data.get_recipe_locations("cd-sem", "RCP_001", "R3") is None


def test_office_mapping_from_record_lists():
    """The confirmed raw_data shape: a list of row dicts."""
    doc = {
        "version": 12, "modified": "2026-08-10T09:30:00",
        "raw_data": [_ROW, {**_ROW, "Parameter": "LEVEL", "SEQ": 2, "Mother_Para": False}],
        "wafer_para_loc_info": [_POINT, {**_POINT, "Parameter": "LEVEL", "P_No": 2}],
    }
    body = office_example._to_locations_response(doc, RECIPE, "R3", "cd-sem")
    assert_matches(body, RecipeLocationsResponse)
    assert body["version"] == 12
    assert body["modified"] == "2026-08-10T09:30:00"
    assert len(body["parameter_rows"]) == 2
    assert body["parameter_rows"][1]["Parameter"] == "LEVEL"
    assert body["points"][1]["P_No"] == 2
    json.dumps(body)  # JSON-safe end to end


def test_office_mapping_accepts_a_column_oriented_blob():
    """`DataFrame.to_dict()` (the project's default) is column -> {index: value};
    the ingest job may have written either orientation."""
    doc = {
        "version": "3",
        "raw_data": {key: {"0": value} for key, value in _ROW.items()},
        "wafer_para_loc_info": {key: {"0": value} for key, value in _POINT.items()},
    }
    body = office_example._to_locations_response(doc, RECIPE, None, "cd-sem")
    assert body["version"] == 3
    assert body["modified"] is None
    assert body["parameter_rows"] == [_ROW]
    assert body["points"] == [_POINT]


def test_office_mapping_serves_a_documents_missing_table_as_empty():
    """A version ingested before wafer_para_loc_info existed has no field —
    that is "no locations", not a 502."""
    body = office_example._to_locations_response(
        {"version": 1, "raw_data": [_ROW]}, RECIPE, "R3", "cd-sem"
    )
    assert body["points"] == []
    assert body["parameter_rows"] == [_ROW]


def test_office_mapping_unwraps_a_table_keyed_blob():
    """The `{table: rows}` wrapper device_statistics' reader also accepts."""
    doc = {
        "version": 2,
        "raw_data": {"idp_image_info": [_ROW]},
        "wafer_para_loc_info": {"wafer_mp_info": [_POINT]},
    }
    body = office_example._to_locations_response(doc, RECIPE, "R3", "cd-sem")
    assert body["parameter_rows"] == [_ROW]
    assert body["points"] == [_POINT]


def test_office_mapping_serves_an_unreadable_blob_as_empty():
    body = office_example._to_locations_response(
        {"version": 1, "raw_data": "garbage", "wafer_para_loc_info": 42},
        RECIPE, "R3", "cd-sem",
    )
    assert body["parameter_rows"] == []
    assert body["points"] == []
