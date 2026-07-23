"""BM/PM row-shape tests: shared value logic, mock parity, declared columns."""

from datetime import datetime

from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm._shared import (
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


def test_derive_cards_takes_the_soonest_future_pm():
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
