"""Gate for the IDP parser -> RecipeDetailResponse mapping (office adapter).

This is the half of `get_recipe_open_data` that can be tested ANYWHERE. The
office path is locate (OpenSearch) -> download (FTP) -> parse (`office_utils`)
-> map, and the first three are unreachable from home and from CI. The mapping
is both the most likely to be wrong and the only one that needs no
infrastructure, so `_to_detail_response` is a pure function and this file feeds
it hand-built DataFrames.

It therefore imports `providers/office_example.py` — the tracked template —
never `providers/office.py`, which is gitignored and absent on a clean
checkout. `office_utils` is not imported at all: these frames stand in for its
output directly.

The column lists below are TRANSCRIBED FROM `docs/datatables/recipe_idp.txt`
rather than derived from `contracts.py`, deliberately. If they were derived,
this file would agree with any edit to the contract; transcribed, an edit that
drifts from the office schema fails here and has to be reconciled against the
doc — which is what "column names are the office contract" has to mean in
practice.
"""

import json

import numpy as np
import pandas as pd
import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.recipe_search.contracts import RecipeDetailResponse
from back_dev_home.ebeam.hitachi.recipe_search.providers import office_example


RECIPE_ID = "ADI/ADI_CD_BIAS_001"
FAC_ID = "R3"
TOOL_CATEGORY = "cd-sem"

MP_COLUMNS = [
    "ChipNo_X", "ChipNo_Y", "Coordinate_X", "Coordinate_Y", "P_No", "D_No",
    "Diff", "Rel", "Rel_MoveX", "Rel_MoveY", "Coordinate_X_r",
    "Coordinate_Y_r", "Parameter", "img_meas2",
]
ALIGN_COLUMNS = [
    "Align_No", "Chip.X", "Chip.Y", "Coordinate.X", "Coordinate.Y", "P.No",
]
IMAGE_COLUMNS = [
    "Parameter", "img_add1", "img_add2", "img_meas1", "img_meas2", "SEQ",
    "Last_SEQ", "Region", "image_add3", "Addressing", "Mother_Para",
    "Double_Addressing", "Meas_Counting", "dnumber_removed",
]


def _mp_frame(rows: int = 3) -> pd.DataFrame:
    """wafer_mp_info as the parser returns it: numpy dtypes, img_meas2 == P_No."""
    return pd.DataFrame({
        "ChipNo_X": np.arange(1, rows + 1, dtype="int64"),
        "ChipNo_Y": np.arange(2, rows + 2, dtype="int64"),
        "Coordinate_X": np.linspace(-1.5, 1.5, rows, dtype="float64"),
        "Coordinate_Y": np.linspace(1.5, -1.5, rows, dtype="float64"),
        "P_No": np.arange(1, rows + 1, dtype="int64"),
        "D_No": np.arange(10, 10 + rows, dtype="int64"),
        "Diff": np.array([True, False] * rows, dtype="bool")[:rows],
        "Rel": np.array([False, True] * rows, dtype="bool")[:rows],
        "Rel_MoveX": np.zeros(rows, dtype="float64"),
        "Rel_MoveY": np.zeros(rows, dtype="float64"),
        "Coordinate_X_r": np.linspace(-1.0, 1.0, rows, dtype="float64"),
        "Coordinate_Y_r": np.linspace(1.0, -1.0, rows, dtype="float64"),
        "Parameter": [f"Para_{i + 1}" for i in range(rows)],
        # NOT a filename — the parser puts P_No's value here.
        "img_meas2": np.arange(1, rows + 1, dtype="int64"),
    })


def _align_frame(rows: int = 2) -> pd.DataFrame:
    """wafer_align_info — the table whose column names contain dots."""
    return pd.DataFrame({
        "Align_No": np.arange(1, rows + 1, dtype="int64"),
        "Chip.X": np.arange(3, 3 + rows, dtype="int64"),
        "Chip.Y": np.arange(4, 4 + rows, dtype="int64"),
        "Coordinate.X": np.linspace(-9.0, 9.0, rows, dtype="float64"),
        "Coordinate.Y": np.linspace(9.0, -9.0, rows, dtype="float64"),
        "P.No": np.arange(1, rows + 1, dtype="int64"),
    })


def _image_frame(rows: int = 3) -> pd.DataFrame:
    """idp_image_info — here img_meas2 IS a filename, unlike wafer_mp_info."""
    return pd.DataFrame({
        "Parameter": [f"Para_{i + 1}" for i in range(rows)],
        "img_add1": [f"IMG_ADD1_{i:04d}.jpg" for i in range(rows)],
        "img_add2": [f"IMG_ADD2_{i:04d}.jpg" for i in range(rows)],
        "img_meas1": [f"IMG_MEAS1_{i:04d}.jpg" for i in range(rows)],
        "img_meas2": [f"IMG_MEAS2_{i:04d}.jpg" for i in range(rows)],
        "SEQ": np.arange(1, rows + 1, dtype="int64"),
        "Last_SEQ": np.arange(2, rows + 2, dtype="int64"),
        "Region": np.arange(1, rows + 1, dtype="int64"),
        "image_add3": [f"IMG_ADD3_{i:04d}.jpg" for i in range(rows)],
        "Addressing": (["Yes", "No"] * rows)[:rows],
        "Mother_Para": ["Para_1"] * rows,
        "Double_Addressing": np.array([True, False] * rows, dtype="bool")[:rows],
        "Meas_Counting": np.arange(1, rows + 1, dtype="int64"),
        "dnumber_removed": np.zeros(rows, dtype="int64"),
    })


def _frames(**overrides: pd.DataFrame) -> dict[str, pd.DataFrame]:
    frames = {
        "wafer_mp_info": _mp_frame(),
        "wafer_align_info": _align_frame(),
        "idp_image_info": _image_frame(),
    }
    frames.update(overrides)
    return frames


def _map(**overrides: pd.DataFrame) -> RecipeDetailResponse:
    return office_example._to_detail_response(
        _frames(**overrides), RECIPE_ID, FAC_ID, TOOL_CATEGORY
    )


def test_parsed_frames_map_to_the_detail_contract():
    detail = _map()
    assert_matches(detail, RecipeDetailResponse)
    assert detail["recipe_id"] == RECIPE_ID
    assert detail["fac_id"] == FAC_ID
    assert detail["tool_category"] == TOOL_CATEGORY


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("wafer_mp_info", MP_COLUMNS),
        ("wafer_align_info", ALIGN_COLUMNS),
        ("idp_image_info", IMAGE_COLUMNS),
    ],
)
def test_rows_carry_exactly_the_documented_columns(table, columns):
    """Names AND order, per docs/datatables/recipe_idp.txt.

    Order matters because the MP table renders its columns in key order, so a
    reshuffle here is a visible reshuffle on screen.
    """
    rows = _map()[table]
    assert rows, f"{table} produced no rows"
    for row in rows:
        assert list(row) == columns


def test_dot_columns_survive_the_mapping():
    """`Chip.X` / `P.No` are IDP-native spellings and must not be normalized.

    They also force key access over attribute access all the way to the
    frontend — a rename here would break a screen that reads `row['P.No']`.
    """
    row = _map()["wafer_align_info"][0]
    assert row["Chip.X"] == 3
    assert row["P.No"] == 1


def test_img_meas2_keeps_its_two_unrelated_meanings():
    """Same column name, different tables, different types — on purpose.

    The old mock fabricated a filename in wafer_mp_info and taught the
    frontend to expect a string the office never produces.
    """
    detail = _map()
    for row in detail["wafer_mp_info"]:
        assert row["img_meas2"] == row["P_No"]
        assert isinstance(row["img_meas2"], int)
    for row in detail["idp_image_info"]:
        assert isinstance(row["img_meas2"], str)


def test_missing_values_become_null_rather_than_nan():
    """A NaN reaching the client makes an HTTP 200 unparseable.

    `json.dumps` emits a bare `NaN` literal by default, which is not valid
    JSON and throws in the browser's `JSON.parse` — the response looks fine
    in the server log and the page dies. `allow_nan=False` is the assertion
    that this cannot happen.
    """
    frame = _mp_frame()
    frame.loc[0, "Coordinate_X"] = np.nan
    frame["Parameter"] = frame["Parameter"].astype("string")
    frame.loc[1, "Parameter"] = pd.NA

    detail = _map(wafer_mp_info=frame)
    assert detail["wafer_mp_info"][0]["Coordinate_X"] is None
    assert detail["wafer_mp_info"][1]["Parameter"] is None
    json.dumps(detail, allow_nan=False)


def test_every_scalar_is_a_native_python_type():
    """numpy scalars are rejected by Flask's JSON encoder.

    pandas 3 boxes them on `.to_dict()`, but the office may run an older
    pandas, and this mapping is not allowed to depend on which.
    """
    detail = _map()
    for table in ("wafer_mp_info", "wafer_align_info", "idp_image_info"):
        for row in detail[table]:
            for key, value in row.items():
                assert type(value) in (int, float, bool, str, type(None)), (
                    f"{table}.{key} is {type(value).__name__}, not a native scalar"
                )


def test_absent_column_is_nulled_not_dropped():
    """A parser that stops emitting a column must not change the row's shape.

    Dropping the key would make the frontend render `undefined`; nulling it
    keeps the table aligned and leaves the WARNING in the log as the record.
    """
    detail = _map(wafer_mp_info=_mp_frame().drop(columns=["Rel_MoveY"]))
    for row in detail["wafer_mp_info"]:
        assert "Rel_MoveY" in row
        assert row["Rel_MoveY"] is None
    assert list(detail["wafer_mp_info"][0]) == MP_COLUMNS


def test_undocumented_column_does_not_reach_the_response():
    """New parser columns are logged, not forwarded.

    The response shape is a contract the frontend types against; widening it
    silently because upstream widened is how a table gains a column nobody
    designed.
    """
    frame = _mp_frame()
    frame["Undocumented_New_Column"] = 1
    detail = _map(wafer_mp_info=frame)
    assert "Undocumented_New_Column" not in detail["wafer_mp_info"][0]


def test_empty_parser_table_maps_to_an_empty_list():
    """A recipe with no align points is data, not an error."""
    detail = _map(wafer_align_info=_align_frame().iloc[0:0])
    assert detail["wafer_align_info"] == []
    assert_matches(detail, RecipeDetailResponse)


def test_sourceless_extras_key_off_the_real_parameters():
    """align_images and amp_info are fabricated even at the office.

    They are not among the parser's three keys. What this pins is that AMP is
    at least keyed on the PARSED parameter names, so the per-parameter panel
    joins — a fabricated AMP row for a parameter the recipe does not declare
    would be dropped on the floor by the frontend.
    """
    detail = _map()
    declared = {row["Parameter"] for row in detail["idp_image_info"]}
    assert declared
    assert {amp["parameter"] for amp in detail["amp_info"]} <= declared
    assert [image["label"] for image in detail["align_images"]] == [
        "Global Align", "Fine Align",
    ]


def test_idp_remote_path_matches_the_documented_tree():
    """Path derivation: meas_hist stores paths, the FTP tree wants stems.

    Proven against the real server by `scripts/probe_recipe_ftp.py`
    (office 확인 2026-07-27); pinned here so a refactor cannot quietly
    reintroduce the raw values.
    """
    location = office_example._IdpLocation(
        eqp_id="MCD719",
        eqp_ip="10.1.2.3",
        class_name="ADI",
        idw_stem=office_example._stem("/Recipe/ADI/ADI_CD_BIAS_001.idw"),
        idp_stem=office_example._stem("/Recipe/ADI/ADI_CD_BIAS_001.idp"),
    )
    assert office_example._idp_remote_path(location) == (
        "/HITACHI/DEVICE/HD/ADI/data/ADI_CD_BIAS_001/ADI_CD_BIAS_001.idp"
    )


def test_stem_tolerates_a_bare_name():
    """The office may store either form; both must derive the same key."""
    assert office_example._stem("ADI_CD_BIAS_001") == "ADI_CD_BIAS_001"
    assert office_example._stem("/Recipe/ADI/ADI_CD_BIAS_001.idp") == "ADI_CD_BIAS_001"
    assert office_example._stem(None) == ""
