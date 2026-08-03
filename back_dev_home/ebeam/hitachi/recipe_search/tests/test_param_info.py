"""Composition for the three tiered recipe-search read endpoints.

Everything here runs against a hand-built RecipeDetailResponse rather than the
mock provider: the mock draws its Parameter values at random, so a test that
needs a parameter occupying TWO rows — the case the whole ``occurrences`` shape
exists for — cannot be written against it reliably.
"""

import pytest

from back_dev_home.ebeam.hitachi.recipe_search import param_info


LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}


def _row(parameter, seq, **overrides):
    row = {
        "Parameter": parameter,
        "img_add1": f"IMMP{seq:04d}",
        "img_add2": f"PRMP{seq:04d}",
        "img_meas1": f"IMMS{seq:04d}",
        "img_meas2": f"PRMS{seq:04d}",
        "image_add3": "non",
        "SEQ": seq,
        "Last_SEQ": seq + 2,
        "Region": 1,
        "Addressing": True,
        "Mother_Para": seq == 1,
        "Double_Addressing": False,
        "Meas_Counting": 5,
        "dnumber_removed": False,
    }
    row.update(overrides)
    return row


def _detail():
    return {
        "idp_image_info": [
            _row("Para_1", 1),
            _row("Para_13", 4, Addressing=False),
            _row("Para_13", 11),
        ],
        "wafer_mp_info": [
            {"Parameter": "Para_13", "P_No": 1, "D_No": 1},
            {"Parameter": "Para_1", "P_No": 2, "D_No": 2},
            {"Parameter": "Para_13", "P_No": 3, "D_No": 3},
        ],
        "wafer_align_info": [],
        "locator": LOCATOR,
        "recipe_id": "RCP_001",
        "fab_name": "M11",
        "tool_category": "cd-sem",
        "timestamp": "2026-08-02T00:00:00",
    }


def _fetch_stub(calls):
    """Stand in for get_param_detail, recording the items it was handed."""
    def fetch(items):
        calls.extend(items)
        return [
            {
                "parameter": item["parameter"],
                "amp": {"source": "PRMS0000", "rows": [{"key": "ACCV", "value": "800"}]},
                "af_pr": {"source": "ENMP0000",
                          "rows": [{"key": "MODE", "value": "AUTO", "section": "ADD1"}]},
                "images": [
                    {"slot": "img_add1", "stage": "Addressing 1", "name": "IMMP0004.jpeg",
                     "cond": {"source": "cond.txt", "rows": [{"key": "MAG", "value": "50k"}]}}
                ],
            }
            for item in items
        ]
    return fetch


# ── tier 0 ────────────────────────────────────────────────────────────────


def test_parameter_list_counts_rows_and_distinct_parameters_separately():
    out = param_info.build_parameter_list(_detail(), "cd-sem", "M11")
    assert out["total_rows"] == 3
    assert out["distinct_parameters"] == 2
    assert out["locator"] == LOCATOR


def test_parameter_list_roll_ups_count_rows_not_parameters():
    out = param_info.build_parameter_list(_detail(), "cd-sem", "M11")
    # Para_13 occupies two rows and is Addressing on only one of them.
    assert out["addressing_rows"] == 2
    assert out["mother_rows"] == 1


def test_parameter_list_returns_rows_verbatim():
    out = param_info.build_parameter_list(_detail(), "cd-sem", "M11")
    assert out["rows"] == _detail()["idp_image_info"]


# ── tier 1 ────────────────────────────────────────────────────────────────


def test_measurement_points_filters_by_parameter():
    out = param_info.build_measurement_points(_detail(), "Para_13")
    assert out["total"] == 2
    assert [p["P_No"] for p in out["points"]] == [1, 3]


# ── tier 2 ────────────────────────────────────────────────────────────────


def test_rows_for_parameter_returns_every_occurrence_in_row_order():
    rows = param_info.rows_for_parameter(_detail(), "Para_13")
    assert [row["SEQ"] for row in rows] == [4, 11]


def test_rows_for_parameter_is_empty_for_an_unknown_parameter():
    assert param_info.rows_for_parameter(_detail(), "Para_999") == []


def test_param_info_returns_one_occurrence_per_row():
    calls = []
    out = param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11",
        param_info.INCLUDE_PARTS, _fetch_stub(calls),
    )
    assert [occ["idp"]["SEQ"] for occ in out["occurrences"]] == [4, 11]
    assert len(calls) == 2


def test_param_info_flattens_setting_blocks_to_rows_plus_source():
    out = param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11",
        param_info.INCLUDE_PARTS, _fetch_stub([]),
    )
    occ = out["occurrences"][0]
    assert occ["amp"] == [{"key": "ACCV", "value": "800"}]
    assert occ["amp_source"] == "PRMS0000"
    assert occ["af_pr_source"] == "ENMP0000"
    assert occ["images"][0]["cond"] == [{"key": "MAG", "value": "50k"}]
    assert occ["images"][0]["cond_source"] == "cond.txt"


def test_include_amp_drops_every_other_slot_from_the_request():
    """The point of include=: a dropped slot is a file never read.

    Both adapters plan their reads with slots.get(...) through
    rawfiles.slot_sources, so an ABSENT key takes the same branch as an empty
    one. Filtering the response instead would cost the same FTP reads.
    """
    calls = []
    param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11", ("amp",), _fetch_stub(calls),
    )
    assert set(calls[0]["slots"]) == {"img_meas2"}


def test_include_amp_omits_the_other_parts_from_the_response():
    out = param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11", ("amp",), _fetch_stub([]),
    )
    occ = out["occurrences"][0]
    assert "amp" in occ
    assert "af_pr" not in occ
    assert "images" not in occ


def test_include_images_keeps_only_the_three_image_slots():
    calls = []
    param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11", ("images",), _fetch_stub(calls),
    )
    assert set(calls[0]["slots"]) == {"img_add1", "image_add3", "img_meas1"}


def test_param_info_caps_occurrences_and_says_so():
    """A cap that truncated silently would be the defect occurrences prevents.

    The caller must be able to tell "this parameter has 200 rows" from "this
    parameter has more and you were given 200".
    """
    detail = _detail()
    detail["idp_image_info"] = [_row("Para_X", seq) for seq in range(1, 260)]
    out = param_info.build_param_info(
        detail, "Para_X", "cd-sem", "M11",
        param_info.INCLUDE_PARTS, _fetch_stub([]),
    )
    assert len(out["occurrences"]) == param_info.MAX_OCCURRENCES
    assert out["total_occurrences"] == 259
    assert out["truncated"] is True


def test_param_info_is_not_flagged_truncated_when_it_is_whole():
    out = param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11",
        param_info.INCLUDE_PARTS, _fetch_stub([]),
    )
    assert out["total_occurrences"] == 2
    assert out["truncated"] is False


def test_parameter_list_ignores_rows_with_no_parameter_when_counting():
    detail = _detail()
    detail["idp_image_info"] = [*detail["idp_image_info"], _row("", 99)]
    out = param_info.build_parameter_list(detail, "cd-sem", "M11")
    assert out["total_rows"] == 4
    # Para_1 and Para_13 — the blank row is not a third parameter.
    assert out["distinct_parameters"] == 2


def test_param_info_on_an_unknown_parameter_fetches_nothing():
    calls = []
    out = param_info.build_param_info(
        _detail(), "Para_999", "cd-sem", "M11",
        param_info.INCLUDE_PARTS, _fetch_stub(calls),
    )
    assert out["occurrences"] == []
    assert calls == []


# ── include parsing ───────────────────────────────────────────────────────


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_parse_include_defaults_to_every_part(raw):
    assert param_info.parse_include(raw) == param_info.INCLUDE_PARTS


def test_parse_include_reads_a_comma_separated_list():
    assert param_info.parse_include("amp, images") == ("amp", "images")


def test_parse_include_rejects_an_unknown_part():
    with pytest.raises(ValueError):
        param_info.parse_include("amp,beam")
