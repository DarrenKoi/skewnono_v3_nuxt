"""Template pin for the msr_file OFFICE adapter (providers/office_example.py).

``build_response`` is pure (no OpenSearch/MinIO — the fetchers are thin and
separate), so the pickle->contract normalization is pinned AT HOME: the
spaced-column renames ("mp_image_name 01" -> mp_image_name_01, "object" ->
object_type), the "None"-string coercions, and the office-gated metadata
derivations all run against a synthetic payload shaped exactly like
docs/datatables/msr_file_pickle.txt. The office copies office.py from this
template, so what passes here is what runs there.

Run from repo root:  .venv/bin/python -m pytest back_dev_home/msr_file
"""

import logging

import pandas as pd
import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.msr_file.contracts import MsrFileResponse
from back_dev_home.msr_file.providers import office_example


_MSR = "20260701_ADI_CD_BIAS_001_RAEA240031_ECXDX123"


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _result_rows() -> list[dict]:
    # Column spellings COPIED from docs/datatables/msr_file_pickle.txt —
    # spaces and all. Sequence 2 is the degenerate "no point data" case.
    base = {
        "chip_number": "1,1",
        "stage_coordinate": "161395915,169086859",
        "dnum_group": "2,-1",
        "mp_number": 1,
        "no_of_mp_image": 1,
        "mp_image_name 01": f"{_MSR}_001_CD_TOP_1234.tif",
        "meas_condition mag": 250030,
        "meas_condition vac": 500,
        "meas_condition pixel": "512,512",
        "addressing1_score": "868",
        "addressing2_score": "646",
        "measurement_score": "165",
        "meas_method": "Score",
        "object": "MP",
        "meas_kind": "Multi Point",
    }
    return [
        {**base, "sequence": 1, "parameter": "CD_TOP", "cd_value": 43.14},
        {
            **base,
            "sequence": 2,
            "parameter": "CD_TOP",
            "cd_value": None,
            "chip_number": "-5,0",
            "dnum_group": "-1,-1",
            "mp_number": -1,
            "no_of_mp_image": 0,
            # An imageless row's name cell arrives as the string "None"
            # (docs §값 타입) — it must fold to "" / an empty list, not "None".
            "mp_image_name 01": "None",
            "addressing1_score": "None",
            "addressing2_score": "None",
            "measurement_score": "None",
            "meas_kind": "None",
        },
        # Sequence 3 is the HV-SEM shape: several images per targeting point,
        # numbered "mp_image_name 01..NN", stem-suffixed -U/-M/-L, one of them
        # tif-only (user-confirmed 2026-08-08). The other rows' frames get NaN
        # in the extra columns — text() must fold NaN to "" (dropped), which is
        # exactly what a real mixed CD/HV pickle produces.
        {
            **base,
            "sequence": 3,
            "parameter": "CD_BOTTOM",
            "cd_value": 41.02,
            "chip_number": "0,-5",
            "no_of_mp_image": 3,
            "mp_image_name 01": "S04_M0004-01MP-U.jpeg",
            "mp_image_name 02": "S04_M0004-01MP-M.jpeg",
            "mp_image_name 03": "S04_M0004-01MP-L.tif",
        },
    ]


def _payload(result_rows: list[dict] | None = None) -> dict:
    return {
        "df_result_data": _df(result_rows or _result_rows()),
        "exe_detail_info": {
            "class": "ADI",
            "recipe_name": "ADI_CD_BIAS_001",
            "idp_name": "/Recipe/ADI/ADI_CD_BIAS_001.idp",
            "lot_id": "RAEA240031",
            "process": "PHOTO",
            "wafer_id": "RAEA240031_07",
            "idw_name": "/Recipe/ADI/ADI_CD_BIAS_001.idw",
            # Office-confirmed formats (2026-07-24): all strings; wafer_size in
            # nm; map_origin is the array index of the origin die.
            "chip_array": "26,33",
            "chip_pitch": "12520000,10340000",
            "wafer_size": "300000000",
            "map_offset": "0,4610000",
            "map_origin": "12,15",
        },
        "alignment": {
            "image_file": {"1": "align_1.tif", "2": "align_2.tif"},
            "offset": {"1": ["OM", "365", "3525"], "2": ["SEM", "3535", "3535"]},
            "score": {"1": "896", "2": "899"},
        },
        # Mixed catalog-known and unknown params; values arrive as float OR str.
        # One entry per row, INCLUDING sequence 2 (the degenerate "no point
        # data" row): the tool still went there and recorded its state, so it
        # IS a measurement -- len(dynamic_fdc) must equal len(rows)
        # (office-confirmed 2026-07-27, docs/datatables/msr_file_pickle.txt).
        # A golden fixture that itself violated this would make build_response
        # warn on every test run instead of only the one that means to.
        "fixed_fdc": {"SEMCondVsup": 1502.0, "ESCD": "23.44", "MysteryFixed": "7.5"},
        "dynamic_fdc": {
            "1": {"Brightness": 130.0, "StigmaX": 0.1, "MysteryDyn": 3.3},
            "2": {"Brightness": 130.8, "StigmaX": 0.15, "MysteryDyn": 3.35},
            "3": {"Brightness": 131.5, "StigmaX": "0.2", "MysteryDyn": 3.4},
        },
        "spm_dict": {"vave": [1.2], "Vol": [1.55, -0.43], "wf_len": [-148.0, 144.19]},
    }


def _parent() -> dict:
    return {
        "msr": _MSR,
        "class_name": "ADI",
        "recipe_name": "ADI_CD_BIAS_001",
        "idp_name": "/Recipe/ADI/ADI_CD_BIAS_001.idp",
        "idw_name": "/Recipe/ADI/ADI_CD_BIAS_001.idw",
        "lot_id": "RAEA240031",
        "total_images": 40.0,
        "start_time": "2026-07-01T09:00:00",
        "timestamp": "2026-07-01T09:03:20",
        "minio_pkl": "user/msr_pkl/20260701/x.pkl",
    }


@pytest.fixture(scope="module")
def response() -> MsrFileResponse:
    return office_example.build_response(_MSR, _parent(), _payload())


def test_matches_contract(response):
    assert_matches(response, MsrFileResponse)


def test_row_key_renames(response):
    row = response["rows"][0]
    assert row["object_type"] == "MP"
    assert row["mp_image_name_01"].endswith(".tif")
    assert row["meas_condition_mag"] == 250030
    assert row["meas_condition_vac"] == 500
    assert row["msr"] == _MSR
    # No chip_coordinate column office-side -> "" (documented contract gap).
    assert row["chip_coordinate"] == ""


def test_all_mp_image_columns_are_collected(response):
    """mp_image_names carries every "mp_image_name NN" column, in NN order.

    Until 2026-08-08 the row builder normalized all the columns and then read
    only _01, so HV-SEM rows (several images per targeting point) reached the
    screen with one image. The 01 column stays as the representative."""
    single, empty, multi = response["rows"][0], response["rows"][1], response["rows"][2]

    assert multi["mp_image_names"] == [
        "S04_M0004-01MP-U.jpeg",
        "S04_M0004-01MP-M.jpeg",
        "S04_M0004-01MP-L.tif",
    ]
    assert multi["mp_image_name_01"] == multi["mp_image_names"][0]
    assert multi["no_of_mp_image"] == 3

    # The single-image (CD-SEM shape) row still carries exactly its one name...
    assert single["mp_image_names"] == [single["mp_image_name_01"]]
    # ...and the imageless row folds the NaN cells to an empty list, not ["nan"].
    assert empty["mp_image_names"] == []


def test_mp_image_columns_sort_numerically_not_lexically():
    """"mp_image_name 10" must follow 09, not land between 01 and 02."""
    rec = {f"mp_image_name_{i:02d}": f"IMG-{i:02d}.jpeg" for i in (10, 2, 1, 9)}
    assert office_example._mp_image_names(rec) == [
        "IMG-01.jpeg", "IMG-02.jpeg", "IMG-09.jpeg", "IMG-10.jpeg",
    ]


def test_none_string_coercions(response):
    empty = response["rows"][1]
    assert empty["mp_number"] == -1
    assert empty["cd_value"] is None
    assert empty["addressing1_score"] is None
    assert empty["measurement_score"] is None
    assert empty["meas_kind"] is None
    measured = response["rows"][0]
    assert measured["addressing1_score"] == 868
    assert measured["meas_kind"] == "Multi Point"


def test_office_gated_metadata_is_emitted_and_real(response):
    exe = response["exe_detail_info"]
    for key in ("site_layout_hash", "recipe_revision",
                "coordinate_transform_version", "sequence_timestamp"):
        assert exe.get(key), f"office template must emit {key}"
    # start_time (real acquisition start), never a wall-clock fabrication.
    assert exe["sequence_timestamp"] == "2026-07-01T09:00:00"
    assert exe["coordinate_transform_version"] == "minio-pkl-v1"
    assert exe["class_name"] == "ADI"


def test_site_layout_hash_is_stable_identity():
    """Equal across MSRs sharing one layout; different when the site set moves."""
    a = office_example.build_response("MSR-A", _parent(), _payload())
    b = office_example.build_response("MSR-B", _parent(), _payload())
    assert a["exe_detail_info"]["site_layout_hash"] == b["exe_detail_info"]["site_layout_hash"]

    moved_rows = _result_rows()
    moved_rows[0]["chip_number"] = "2,2"
    c = office_example.build_response("MSR-C", _parent(), _payload(moved_rows))
    assert c["exe_detail_info"]["site_layout_hash"] != a["exe_detail_info"]["site_layout_hash"]


def test_fdc_raw_passthrough_but_catalog_only_summaries(response):
    # Every numeric value survives into the raw dicts (str values coerced) ...
    assert response["fixed_fdc"]["MysteryFixed"] == 7.5
    assert response["fixed_fdc"]["ESCD"] == 23.44
    assert response["dynamic_fdc"]["3"]["StigmaX"] == 0.2
    assert response["dynamic_fdc"]["1"]["MysteryDyn"] == 3.3
    # ... but summary verdicts exist only for cataloged params: no baseline,
    # no fabricated nominal.
    names = {s["name"] for s in response["fdc_params"]}
    assert "Brightness" in names and "StigmaX" in names
    assert "MysteryDyn" not in names


def test_zero_sigma_param_summarizes_without_dividing_by_zero():
    """VT and ESCdV are constant set-point channels (sigma 0.0 in the catalog).

    The golden fixture never mentions them, so this is the one place the
    zero-sigma branch is exercised. A real office pickle DOES carry them --
    without the guard, build_response raises ZeroDivisionError for the whole
    MSR, not just that one summary row.
    """
    payload = _payload()
    payload["dynamic_fdc"] = {
        "1": {"VT": 1200.0, "ESCdV": 2500.0},
        "2": {"VT": 1200.0, "ESCdV": 2499.0},
        "3": {"VT": 1201.0, "ESCdV": 2500.0},
    }
    response = office_example.build_response(_MSR, _parent(), payload)

    by_name = {s["name"]: s for s in response["fdc_params"]}
    assert by_name["VT"]["drift_sigma"] == 0.0
    assert by_name["ESCdV"]["drift_sigma"] == 0.0
    assert by_name["VT"]["status"] == "ok"
    # The raw values still pass through untouched -- charts lose nothing.
    assert response["dynamic_fdc"]["3"]["VT"] == 1201.0


def test_health_is_derived_from_worst_drift(response):
    assert 0.0 <= response["health"] <= 1.0
    worst = max(s["drift_sigma"] for s in response["fdc_params"])
    assert response["health"] == round(min(1.0, worst / 3.5), 3)


def test_parameter_summaries_use_measured_rows_only(response):
    by_param = {s["parameter"]: s for s in response["parameters"]}
    assert by_param["CD_TOP"]["count"] == 1  # the mp_number -1 row is excluded
    assert by_param["CD_TOP"]["unit"] == "nm"


def test_golden_payload_satisfies_row_fdc_invariant(caplog):
    """The golden fixture itself must honor len(rows) == len(dynamic_fdc)
    (office-confirmed 2026-07-27, docs/datatables/msr_file_pickle.txt) -- a
    fixture that violated the rule it exists to demonstrate would fire the
    mismatch warning on every test run, not just the one below that means to,
    turning a diagnosable-fault signal into routine noise."""
    with caplog.at_level(logging.WARNING):
        result = office_example.build_response(_MSR, _parent(), _payload())
    assert len(result["rows"]) == len(result["dynamic_fdc"])
    assert not any("dynamic_fdc entries" in r.message for r in caplog.records)


def test_mismatched_row_and_fdc_counts_warn_without_raising(caplog):
    """The office guarantees the SET of row sequences equals the SET of
    dynamic_fdc keys (not just their counts — see
    test_disjoint_keys_same_count_still_warn below). A mismatch is a data
    fault worth naming in the log — but serving flagged data beats serving
    nothing, so it must not raise."""
    payload = {
        "df_result_data": [
            {"sequence": 1, "parameter": "CD_TOP", "cd_value": 10.0},
            {"sequence": 2, "parameter": "SPACE", "cd_value": 20.0},
        ],
        "dynamic_fdc": {"1": {"StigmaX": 0.1}},
        "exe_detail_info": {},
    }
    with caplog.at_level(logging.WARNING):
        response = office_example.build_response("MSR-X", {}, payload)
    assert response["total"] == 2
    assert len(response["dynamic_fdc"]) == 1
    assert any("2 rows" in r.message and "1 dynamic_fdc" in r.message for r in caplog.records)


def test_disjoint_keys_same_count_still_warn(caplog):
    """The case a COUNT-only check misses: rows {1, 2} and dynamic_fdc keys
    {"1", "3"} have the SAME COUNT (2 each) but a DIFFERENT SET — e.g. an
    off-by-one keying or a re-indexed pipeline that still emits one entry per
    row, just under the wrong sequence. The frontend's scoped FDC axis
    (utils/skewvoirAnalysis/sequence.ts) is KEYED, not counted, so a
    same-count/disjoint-keys payload must still warn, and build_response must
    still return normally rather than raising."""
    payload = {
        "df_result_data": [
            {"sequence": 1, "parameter": "CD_TOP", "cd_value": 10.0},
            {"sequence": 2, "parameter": "SPACE", "cd_value": 20.0},
        ],
        "dynamic_fdc": {"1": {"StigmaX": 0.1}, "3": {"StigmaX": 0.2}},
        "exe_detail_info": {},
    }
    with caplog.at_level(logging.WARNING):
        response = office_example.build_response("MSR-Y", {}, payload)
    assert response["total"] == 2
    assert len(response["dynamic_fdc"]) == 2
    assert any("do not match the row sequences" in r.message for r in caplog.records)


def test_office_copy_stays_in_sync_with_template():
    """office.py exists only at the office (cp office_example.py office.py).

    There it must expose the same entry points as this template; at home the
    module is absent and this check skips instead of failing the suite.
    """
    office = pytest.importorskip(
        "back_dev_home.msr_file.providers.office",
        reason="office.py is created at the office from office_example.py",
    )
    assert callable(office.get_msr_file)
