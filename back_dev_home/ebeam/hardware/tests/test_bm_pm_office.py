"""Office BM/PM adapter tests.

These exercise the TRACKED template (`office_example`), never the gitignored
`office.py`, and never touch a cluster: every test feeds fabricated `_source`
dicts to the pure mappers or monkeypatches `fetch_hits`.
"""

from datetime import datetime

import pytest

from back_dev_home.ebeam.hardware.providers.bm_pm import office_example as office


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


def test_past_row_yields_an_empty_category_when_neither_field_says_bm_or_pm():
    # This is the value BmPmPanel.vue must not paint as a BM chip.
    hit = {**PAST_HIT, "pm_type": "기타", "eq_event": "EQ_CHECK"}
    assert office.past_row(hit, "CDX001")["category"] == ""


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
    from back_dev_home.ebeam.hardware.providers.bm_pm import mock

    mock_data = mock.build_bm_pm_data("CDX001", ANCHOR)
    assert set(office.past_row(PAST_HIT, "CDX001")) == set(mock_data["past"][0])
    assert set(office.future_row(FUTURE_HIT, "CDX001")) == set(mock_data["future"][0])


def _capture(monkeypatch, past_hits=(), future_hits=()):
    """Record each fetch_hits call and serve canned hits per index."""
    calls = []

    def fake_fetch_hits(index, query_body, size, sort=None, source=None):
        calls.append(
            {"index": index, "query": query_body, "size": size,
             "sort": sort, "source": source}
        )
        return list(past_hits if index == office.INDEX_PAST else future_hits)

    monkeypatch.setattr(office, "fetch_hits", fake_fetch_hits)
    return calls


def test_build_queries_both_indices_with_the_documented_windows(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_bm_pm_data("CDX001", ANCHOR)

    past = next(c for c in calls if c["index"] == office.INDEX_PAST)
    clauses = past["query"]["bool"]["filter"]
    assert {"term": {office.EQP_ID_KW: "CDX001"}} in clauses
    rng = next(c["range"][office.DOWN_DT] for c in clauses if "range" in c)
    assert rng["gte"] == "2025-11-21T09:00:00"   # anchor - 180d
    assert rng["lte"] == "2026-05-20T09:00:00"
    assert past["sort"] == [{office.DOWN_DT: {"order": "desc"}}]

    future = next(c for c in calls if c["index"] == office.INDEX_FUTURE)
    clauses = future["query"]["bool"]["filter"]
    rng = next(c["range"][office.PLAN_START] for c in clauses if "range" in c)
    assert rng["gte"] == "2026-05-20T09:00:00"
    assert rng["lte"] == "2026-08-18T09:00:00"    # anchor + 90d
    assert future["sort"] == [{office.PLAN_START: {"order": "asc"}}]


def test_build_does_not_filter_on_fab(monkeypatch):
    # eqp_id is the identity; a stale fab label must not empty the table.
    calls = _capture(monkeypatch)
    office.build_bm_pm_data("CDX001", ANCHOR)
    for call in calls:
        rendered = repr(call["query"])
        assert "fab_name" not in rendered
        assert "det_fac_id" not in rendered
        assert "fac_id" not in rendered


def test_build_requests_only_the_documented_source_fields(monkeypatch):
    calls = _capture(monkeypatch)
    office.build_bm_pm_data("CDX001", ANCHOR)
    past = next(c for c in calls if c["index"] == office.INDEX_PAST)
    assert "up_dt" not in past["source"]
    assert set(past["source"]) == set(office.PAST_SOURCE)


def test_build_returns_mapped_rows_and_cards(monkeypatch):
    _capture(monkeypatch, past_hits=[PAST_HIT], future_hits=[FUTURE_HIT])
    data = office.build_bm_pm_data("CDX001", ANCHOR)
    assert data["past"][0]["category"] == "BM"
    assert data["future"][0]["category"] == "PM"
    assert data["cards"] == {
        "last_bm": "2026-05-11 12:30",
        "next_pm": "2026-06-02 08:00",
        "planned_count": 1,
        "recent_count": 1,
    }


def test_build_is_an_empty_result_not_an_error_for_a_tool_with_no_work(monkeypatch):
    _capture(monkeypatch)
    data = office.build_bm_pm_data("CDX001", ANCHOR)
    assert data["past"] == []
    assert data["future"] == []
    assert data["cards"]["last_bm"] == "—"


def test_build_raises_when_a_side_fills_the_row_cap(monkeypatch):
    _capture(monkeypatch, past_hits=[PAST_HIT] * office.MAX_ROWS)
    with pytest.raises(LookupError, match="cap"):
        office.build_bm_pm_data("CDX001", ANCHOR)
