import math
import os

import pytest

from back_dev_home.msr_file.data import _summaries, get_msr_file
from back_dev_home.msr_file.providers import mock
from back_dev_home.meas_hist.data import get_meas_hist
from tests._office_state import MISSING_ADAPTER_MESSAGE, has_office_adapter, skip_reason


@pytest.fixture(scope="module")
def sample_msr() -> str:
    """A real MSR id from the meas_hist fixture — never hardcode one."""
    rows = get_meas_hist()["rows"]
    return rows[0]["msr"]


def _row(**over):
    row = {
        "msr": "M1", "sequence": 1, "chip_number": "0, 0", "chip_coordinate": "",
        "stage_coordinate": "", "dnum_group": "0, -1", "mp_number": 1,
        "parameter": "CD_TOP", "cd_value": 10.0, "no_of_mp_image": 1,
        "mp_image_name_01": "", "meas_condition_mag": 250030,
        "meas_condition_vac": 500, "meas_condition_pixel": "512,512",
        "addressing1_score": 868, "addressing2_score": 646,
        "measurement_score": 165, "meas_method": "Score", "object_type": "MP",
        "meas_kind": "Multi Point",
    }
    row.update(over)
    return row


# ── cd_value nullability ─────────────────────────────────────────────────────

def test_invalid_rows_have_null_cd_value(sample_msr):
    payload = get_msr_file(sample_msr)
    invalid = [r for r in payload["rows"] if r["mp_number"] < 0]
    assert invalid, "fixture has no mp_number=-1 rows — test is not exercising the rule"
    for row in invalid:
        assert row["cd_value"] is None
        assert row["no_of_mp_image"] == 0
        assert row["measurement_score"] is None


def test_valid_rows_always_have_a_cd_value(sample_msr):
    payload = get_msr_file(sample_msr)
    valid = [r for r in payload["rows"] if r["mp_number"] >= 0]
    assert valid
    for row in valid:
        assert isinstance(row["cd_value"], float)
        assert math.isfinite(row["cd_value"])


# ── summaries ────────────────────────────────────────────────────────────────

def test_summaries_exclude_null_cd_values():
    rows = [_row(cd_value=10.0), _row(cd_value=20.0), _row(cd_value=None, mp_number=-1)]
    summary = _summaries(rows)[0]
    assert summary["count"] == 2
    assert summary["mean"] == 15.0
    assert summary["max"] == 20.0


def test_summaries_use_sample_stdev_not_population():
    rows = [_row(cd_value=v) for v in (2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0)]
    # population stdev = 2.0; sample stdev = 2.138. The frontend uses sample (n-1).
    assert _summaries(rows)[0]["std"] == 2.138


def test_parameter_with_no_valid_rows_is_omitted():
    rows = [_row(parameter="CD_TOP", cd_value=10.0),
            _row(parameter="CD_BOTTOM", cd_value=None, mp_number=-1)]
    assert [s["parameter"] for s in _summaries(rows)] == ["CD_TOP"]


def test_summary_count_matches_valid_row_count(sample_msr):
    """EVERY summary counts exactly its parameter's measured rows.

    Checked across all parameters rather than `parameters[0]`: summaries sort by
    name, so the first entry is the UNNAMED dummy MP whenever the measurement
    opens with settling shots — and those are all measured, which used to trip
    the "fixture has no invalid rows" precondition. That precondition belongs to
    the fixture as a whole, not to whichever parameter happens to sort first.
    """
    payload = get_msr_file(sample_msr)
    saw_invalid = False
    for summary in payload["parameters"]:
        raw = [r for r in payload["rows"] if r["parameter"] == summary["parameter"]]
        valid = [r for r in raw if r["cd_value"] is not None]
        assert summary["count"] == len(valid)
        saw_invalid = saw_invalid or len(valid) < len(raw)
    assert saw_invalid, "fixture has no invalid rows"


# ── new row columns ──────────────────────────────────────────────────────────

def test_new_measurement_condition_columns_present(sample_msr):
    payload = get_msr_file(sample_msr)
    valid = next(r for r in payload["rows"] if r["mp_number"] >= 0)
    assert valid["meas_condition_mag"] > 0
    assert valid["meas_condition_vac"] > 0
    assert valid["meas_condition_pixel"] != "0,0"
    assert valid["meas_kind"] in ("Multi Point", "Single Point", None)
    assert valid["object_type"] in ("MP", "Line", "Space")
    assert valid["meas_method"] in ("Score", "Width", "Edge")


def test_invalid_rows_report_zeroed_measurement_conditions(sample_msr):
    payload = get_msr_file(sample_msr)
    invalid = next(r for r in payload["rows"] if r["mp_number"] < 0)
    assert invalid["meas_condition_mag"] == 0
    assert invalid["meas_condition_vac"] == 0
    assert invalid["meas_condition_pixel"] == "0,0"


def test_addressing_scores_are_nullable_ints(sample_msr):
    payload = get_msr_file(sample_msr)
    seen_int = False
    for row in payload["rows"]:
        for key in ("addressing1_score", "addressing2_score"):
            assert row[key] is None or isinstance(row[key], int)
            if isinstance(row[key], int):
                seen_int = True
    assert seen_int, "every addressing score was None — generator is not producing values"


# ── exe_detail_info ──────────────────────────────────────────────────────────

def test_exe_detail_info_is_sourced_from_the_parent_meas_hist(sample_msr):
    parent = next(r for r in get_meas_hist()["rows"] if r["msr"] == sample_msr)
    info = get_msr_file(sample_msr)["exe_detail_info"]
    assert info["class_name"] == parent["class_name"]
    assert info["recipe_name"] == parent["recipe_name"]
    assert info["idp_name"] == parent["idp_name"]
    assert info["idw_name"] == parent["idw_name"]
    assert info["lot_id"] == parent["lot_id"]


def test_exe_detail_info_has_wafer_geometry(sample_msr):
    info = get_msr_file(sample_msr)["exe_detail_info"]
    # nm, not mm: ec704a4 adopted the office-confirmed format ("300000000" =
    # 300 mm) and this assertion was left behind. Derived from the module's own
    # constant so the two cannot drift apart again.
    assert info["wafer_size"] == str(mock._WAFER_NM)
    assert info["wafer_id"].startswith(info["lot_id"])
    for key in ("chip_array", "chip_pitch", "map_offset", "map_origin", "process"):
        assert info[key]


# ── alignment ────────────────────────────────────────────────────────────────

def test_alignment_has_three_points_with_matching_keys(sample_msr):
    align = get_msr_file(sample_msr)["alignment"]
    assert set(align["image_file"]) == set(align["offset"]) == set(align["score"])
    assert set(align["image_file"]) == {"1", "2", "3"}
    for key in align["offset"]:
        method, x, y = align["offset"][key]
        assert method in ("OM", "SEM")
        assert x.lstrip("-").isdigit() and y.lstrip("-").isdigit()
        # Any non-negative integer. Nothing thresholds on the score yet, so the
        # scale is deliberately not asserted.
        assert align["score"][key].isdigit()


# ── spm_dict (placeholder mock — shape only, no signal) ──────────────────────

def test_spm_dict_is_a_32_point_profile(sample_msr):
    spm = get_msr_file(sample_msr)["spm_dict"]
    assert len(spm["Vol"]) == 32
    assert len(spm["wf_len"]) == 32
    assert len(spm["vave"]) == 1
    assert spm["wf_len"] == sorted(spm["wf_len"]), "wf_len must be monotonic"
    assert spm["wf_len"][0] < 0 < spm["wf_len"][-1]
    assert all(isinstance(v, float) for v in spm["Vol"])


# ── determinism ──────────────────────────────────────────────────────────────

def test_same_msr_always_yields_identical_data(sample_msr):
    get_msr_file.cache_clear()
    first = get_msr_file(sample_msr)
    get_msr_file.cache_clear()
    second = get_msr_file(sample_msr)
    assert first == second


@pytest.mark.skipif(has_office_adapter("msr_file"), reason=skip_reason("msr_file"))
def test_unconnected_office_adapter_fails_explicitly(sample_msr):
    previous = os.environ.get("SKEWNONO_MSR_FILE_PROVIDER")
    os.environ["SKEWNONO_MSR_FILE_PROVIDER"] = "office"
    try:
        with pytest.raises(RuntimeError, match=MISSING_ADAPTER_MESSAGE):
            get_msr_file(sample_msr)
    finally:
        if previous is None:
            os.environ.pop("SKEWNONO_MSR_FILE_PROVIDER", None)
        else:
            os.environ["SKEWNONO_MSR_FILE_PROVIDER"] = previous
