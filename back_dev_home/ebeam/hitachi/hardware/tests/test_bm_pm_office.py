"""Office BM/PM adapter tests.

These exercise the TRACKED template (`office_example`), never the gitignored
`office.py`, and never touch a cluster: every test feeds fabricated `_source`
dicts to the pure mappers or monkeypatches `fetch_hits`.
"""

from datetime import datetime

import pytest

from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm import office_example as office


ANCHOR = datetime(2026, 5, 20, 9, 0)

PAST_HIT = {
    "eqp_id": "CDX001",
    "down_dt": "2026-05-11T08:00:00",
    "equp_dt": "2026-05-11T12:30:00",
    "hub_load_tm": "2026-05-11T13:05:00",
    "pm_type": "",
    "eq_event": "BM_ALIGN",
    "lot_id": "CG6300000123",
    "last_recipe_id": "CD_BIAS_A01",
    "note_comment": "필터 교체",
    "zzproblem": "진공도 미달",
    "hltext": "",
}

FUTURE_HIT = {
    "eqp_id": "CDX001",
    "tool_start_tm": "2026-06-02T08:00:00",
    "tool_end_tm": "2026-06-02T17:00:00",
    "chg_tm": "2026-05-18T11:00:00",
    "event_name": "PM_QUARTER",
    "work_item_nm": "정기 PM — 컬럼 청소",
    "work_user_cd": "K12345",
}


def test_past_row_maps_index_fields_onto_the_row_contract():
    row = office.past_row(PAST_HIT, "CDX001")
    assert row["job_starts"] == "2026-05-11 08:00"   # down_dt
    assert row["job_end"] == "2026-05-11 12:30"      # equp_dt
    assert row["timestamp"] == "2026-05-11 13:05"    # hub_load_tm
    assert row["category"] == "BM"                   # pm_type empty -> eq_event
    assert row["lot_id"] == "CG6300000123"
    assert row["engr_note"] == "[Comment] 필터 교체\n[Problem] 진공도 미달"


def test_past_row_leaves_job_end_blank_while_the_tool_is_still_down():
    hit = {**PAST_HIT, "equp_dt": None}
    assert office.past_row(hit, "CDX001")["job_end"] == ""


def test_past_row_rejects_a_row_with_no_down_time():
    hit = {**PAST_HIT, "down_dt": ""}
    with pytest.raises(ValueError, match="down_dt"):
        office.past_row(hit, "CDX001")


def test_past_row_rejects_a_hit_for_another_tool():
    hit = {**PAST_HIT, "eqp_id": "CDX999"}
    with pytest.raises(ValueError, match="CDX999"):
        office.past_row(hit, "CDX001")


def test_past_row_never_reads_up_dt():
    # up_dt is unused by contract; a populated one must not reach the row.
    hit = {**PAST_HIT, "up_dt": "2026-05-11T20:00:00"}
    assert "2026-05-11 20:00" not in office.past_row(hit, "CDX001").values()


def test_future_row_maps_index_fields_onto_the_row_contract():
    row = office.future_row(FUTURE_HIT, "CDX001")
    assert row["job_starts"] == "2026-06-02 08:00"   # tool_start_tm
    assert row["job_end"] == "2026-06-02 17:00"      # tool_end_tm
    assert row["timestamp"] == "2026-05-18 11:00"    # chg_tm
    assert row["category"] == "PM"
    assert row["work_user_cd"] == "K12345"


def test_future_row_rejects_a_row_with_no_planned_start():
    hit = {**FUTURE_HIT, "tool_start_tm": ""}
    with pytest.raises(ValueError, match="tool_start_tm"):
        office.future_row(hit, "CDX001")


def test_rows_match_the_mock_key_set_exactly():
    # The dispatcher swaps mock.py and office.py by name; divergent keys show
    # up as blank cells rather than an error, so pin them against each other.
    from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm import mock

    mock_data = mock.build_bm_pm_data("CDX001", ANCHOR)
    assert set(office.past_row(PAST_HIT, "CDX001")) == set(mock_data["past"][0])
    assert set(office.future_row(FUTURE_HIT, "CDX001")) == set(mock_data["future"][0])
