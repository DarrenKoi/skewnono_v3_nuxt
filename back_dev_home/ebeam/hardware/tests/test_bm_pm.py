"""BM/PM row-shape tests: shared value logic, mock parity, declared columns."""

from datetime import datetime, timedelta

from back_dev_home.ebeam.hardware import data as hardware_data
from back_dev_home.ebeam.hardware.providers.bm_pm._shared import (
    classify_category,
    derive_cards,
    fmt_dt,
    merge_notes,
)


def test_fmt_dt_matches_the_chart_axis_format():
    # bmPmMarkers.ts matches job_starts against the charts' x values.
    assert fmt_dt(datetime(2026, 5, 20, 9, 5)) == "2026-05-20 09:05"
    assert fmt_dt(None) == ""


def test_classify_category_reads_values_carrying_extra_characters():
    # Office pm_type/eq_event are not clean "BM"/"PM" strings.
    assert classify_category("PM2", "") == "PM"
    assert classify_category("", "BM_ALIGN") == "BM"


def test_classify_category_walks_past_an_unrecognisable_candidate():
    # pm_type present but meaningless: eq_event still decides.
    assert classify_category("기타", "PM_WEEKLY") == "PM"


def test_classify_category_returns_empty_when_nothing_matches():
    # The row still renders; it only drops out of the chart overlay.
    assert classify_category("기타", "") == ""
    assert classify_category() == ""


def test_classify_category_prefers_pm_when_a_value_carries_both():
    assert classify_category("BM/PM 정기") == "PM"


def test_merge_notes_labels_each_note_and_drops_empty_ones():
    row = {"note_comment": "필터 교체", "zzproblem": "", "hltext": "재점검 필요"}
    assert merge_notes(row) == "[Comment] 필터 교체\n[Highlight] 재점검 필요"


def test_merge_notes_is_empty_when_every_note_is_blank():
    assert merge_notes({"note_comment": "", "zzproblem": None}) == ""


def test_derive_cards_falls_back_to_job_starts_when_tool_is_still_down():
    past = [{"category": "BM", "job_starts": "2026-05-01 08:00", "job_end": ""}]
    cards = derive_cards(past, [])
    assert cards["last_bm"] == "2026-05-01 08:00"
    assert cards["recent_count"] == 1
    assert cards["next_pm"] == "—"
    assert cards["planned_count"] == 0


def test_derive_cards_takes_the_first_future_pm():
    future = [
        {"category": "BM", "job_starts": "2026-05-02 08:00"},
        {"category": "PM", "job_starts": "2026-05-10 08:00"},
        {"category": "PM", "job_starts": "2026-05-20 08:00"},
    ]
    assert derive_cards([], future)["next_pm"] == "2026-05-10 08:00"


def test_derive_cards_uses_the_most_recent_past_bm():
    past = [
        {"category": "PM", "job_starts": "2026-05-18 08:00", "job_end": "2026-05-18 16:00"},
        {"category": "BM", "job_starts": "2026-05-11 08:00", "job_end": "2026-05-11 12:00"},
        {"category": "BM", "job_starts": "2026-05-01 08:00", "job_end": "2026-05-01 12:00"},
    ]
    assert derive_cards(past, [])["last_bm"] == "2026-05-11 12:00"


import re

from back_dev_home.ebeam.hardware.providers.bm_pm import mock as bm_pm_mock

ANCHOR = datetime(2026, 5, 20, 9, 0)

PAST_KEYS = {
    "eqp_id", "job_starts", "job_end", "category", "pm_type", "eq_event",
    "lot_id", "last_recipe_id", "note_comment", "zzproblem", "hltext",
    "timestamp", "engr_note",
}
FUTURE_KEYS = {
    "eqp_id", "job_starts", "job_end", "category", "event_name",
    "work_item_nm", "work_user_cd", "timestamp",
}


def test_mock_past_rows_carry_the_full_key_set():
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    assert data["past"], "mock should fabricate past work for any tool"
    for row in data["past"]:
        assert set(row) == PAST_KEYS


def test_mock_future_rows_carry_the_full_key_set():
    # Seeded so this tool has planned work; build_future_frame can return none.
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    for row in data["future"]:
        assert set(row) == FUTURE_KEYS


def test_mock_rows_use_the_chart_timestamp_format():
    # bmPmMarkers.ts matches these against the charts' x-axis values.
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    for row in data["past"]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row["job_starts"])
        assert row["job_end"] == "" or re.fullmatch(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row["job_end"]
        )


def test_mock_past_is_newest_first_and_future_is_soonest_first():
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    starts = [row["job_starts"] for row in data["past"]]
    assert starts == sorted(starts, reverse=True)
    plans = [row["job_starts"] for row in data["future"]]
    assert plans == sorted(plans)


def test_mock_is_deterministic_for_a_tool_and_anchor():
    first = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    second = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    assert first == second


def test_mock_produces_some_unclassifiable_rows_for_the_ui_to_render():
    # Real pm_type/eq_event do not always say BM or PM. The mock must exercise
    # that path so the "" category is visible at home, not only at the office.
    seen = set()
    for tool in ("CDX001", "CDX002", "CDX003", "HVX010", "HVX011"):
        for row in bm_pm_mock.build_bm_pm_data(tool, ANCHOR)["past"]:
            seen.add(row["category"])
    assert seen >= {"BM", "PM", ""}


def test_mock_engr_note_merges_the_populated_notes():
    data = bm_pm_mock.build_bm_pm_data("CDX001", ANCHOR)
    row = next(r for r in data["past"] if r["note_comment"])
    assert "[Comment]" in row["engr_note"]


def _bm_pm_payload():
    end = ANCHOR
    start = end - timedelta(days=14)
    return hardware_data.get_hardware_service("cdsem", "bm-pm", "CDX001", "R3", start, end)


def test_every_declared_column_exists_on_every_row():
    # A typo in either list shows up as a blank column, never as an error.
    payload = _bm_pm_payload()
    for section in payload["tables"]:
        declared = {column["key"] for column in section["columns"]}
        for row in section["rows"]:
            missing = declared - set(row)
            assert not missing, f"{section['key']} row is missing {sorted(missing)}"


def test_past_table_declares_the_three_note_columns_as_expandable():
    payload = _bm_pm_payload()
    past = next(s for s in payload["tables"] if s["key"] == "past_work")
    labels = {c["key"]: c for c in past["columns"]}
    for key, label in (("note_comment", "Comment"), ("zzproblem", "Problem"), ("hltext", "Highlight")):
        assert labels[key]["label"] == label
        assert labels[key]["expandable"] is True


def test_engr_note_rides_along_without_being_a_column():
    # bmPmMarkers.ts reads row.engr_note; BmPmPanel.vue must not show it.
    payload = _bm_pm_payload()
    past = next(s for s in payload["tables"] if s["key"] == "past_work")
    assert "engr_note" not in {c["key"] for c in past["columns"]}
    assert all("engr_note" in row for row in past["rows"])
