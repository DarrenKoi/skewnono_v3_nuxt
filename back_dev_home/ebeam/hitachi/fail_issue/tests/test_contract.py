"""Contract gate for fail_issue. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/fail_issue
Office: SKEWNONO_FAIL_ISSUE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/fail_issue

The shape checks and the aggregation laws below are meaningful under both
providers: MIGRATION.md specifies the office adapter to drop zero-fail groups,
sort each ranking by fail count desc, rank from 1, and zero-fill + date-sort
the daily trend — the same laws providers/mock.py implements. What is NOT
provider-independent is that the window CONTAINS anything: the mock fabricates
a fixed row set around its own ANCHOR_TIME, while a live meas_hist index can
legitimately hold nothing for a fab/window. Those assumptions are fenced
behind get_data_provider("fail_issue") == "mock" so the office run cannot go
green on a mock-only invariant — nor red on an empty-but-valid index.

Deliberately NOT asserted: distinct_equipment / distinct_recipes / distinct_lots
against the row set. Office computes them with an OpenSearch `cardinality` agg,
which is approximate above ~3000 distinct values (see office_example.py), so
any exact-count law here would be a mock-only invariant wearing a disguise.
"""

from datetime import timedelta

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.fail_issue import data
from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    AlignRankingRow,
    DailyTrendPoint,
    DeviceRow,
    EquipmentComparePayload,
    EquipmentRow,
    EquipmentsPayload,
    MeasRankingRow,
    SummaryPayload,
)


# Mirrors resolve_analytics_scope's defaults (_analytics_routes.py):
# end_date = anchor, start_date = anchor - 14 days, no fab/lot filter.
DEFAULT_DAYS = 14


def _default_scope():
    anchor = data.get_anchor_time().date()
    end_date = anchor.isoformat()
    start_date = (anchor - timedelta(days=DEFAULT_DAYS)).isoformat()
    return "cd-sem", None, start_date, end_date


def _is_mock() -> bool:
    return get_data_provider("fail_issue") == "mock"


def _assert_triage_table(rows, count_key: str, rate_key: str) -> None:
    """Laws every ranking obeys under BOTH providers (MIGRATION.md §ranking).

    Zero-fail groups are dropped so the table stays a triage list, the sort is
    by (fail count, fail rate) descending, and rank is a 1-based dense index of
    that order. A ranking that violates any of these is wrong wherever the rows
    came from — which is exactly what should stay unfenced.
    """
    assert [row["rank"] for row in rows] == list(range(1, len(rows) + 1))
    for row in rows:
        assert row[count_key] > 0, "zero-fail groups must be dropped"
        assert row[count_key] <= row["exec_count"]
        assert 0.0 < row[rate_key] <= 1.0
        assert len(row["sample_eqp_ids"]) <= 5
    counts = [row[count_key] for row in rows]
    assert counts == sorted(counts, reverse=True), "ranking must be fail-count desc"


def test_get_summary_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    summary = data.get_summary(tool_type, fab_names, start_date, end_date, lot_cd=None)
    assert_matches(summary, SummaryPayload)

    # Counting laws, true of any correct aggregator: a fail is one of the
    # executions counted, and both rates are FRACTIONS (mock's `fails / total`,
    # office's `_rate()`) — not percentages.
    total = summary["total_executions"]
    assert total >= 0
    for key in ("align_fail_count", "align_na_count", "meas_fail_count"):
        assert 0 <= summary[key] <= total, f"{key} exceeds total_executions"
    for key in ("align_fail_rate", "meas_fail_rate"):
        assert 0.0 <= summary[key] <= 1.0, f"{key} is not a 0..1 fraction"

    if _is_mock():
        # The mock generates a fixed row set spanning its own ANCHOR_TIME, so an
        # empty default window means the generator broke. A live index may
        # genuinely hold nothing for these 14 days.
        assert total > 0, "mock fail_issue summary must cover some executions"


def test_get_daily_trend_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    points = data.get_daily_trend(tool_type, fab_names, start_date, end_date, lot_cd=None)
    assert isinstance(points, list)
    for point in points:
        assert_matches(point, DailyTrendPoint)

    # Both adapters zero-fill the range and return it date-ascending — the
    # chart plots the list in order and would render time backwards otherwise.
    dates = [point["date"] for point in points]
    assert dates == sorted(dates), "daily trend must be date-ascending"
    for point in points:
        assert point["align_fail_count"] <= point["exec_count"]
        assert point["meas_fail_count"] <= point["exec_count"]

    # Zero-fill is a BOTH-provider guarantee, so the point count is pinned by
    # the requested range rather than by what data happens to exist: the mock
    # backfills, and office sets date_histogram extended_bounds over the same
    # window (MIGRATION.md /daily-trend). Left unfenced deliberately — this is
    # the check that catches an office adapter dropping empty days.
    assert len(points) == DEFAULT_DAYS + 1, "daily trend must zero-fill the window"


def test_get_align_ranking_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_align_ranking(tool_type, fab_names, start_date, end_date, limit=1000, lot_cd=None)
    assert isinstance(rows, list)
    for row in rows:
        assert_matches(row, AlignRankingRow)

    _assert_triage_table(rows, "align_fail_count", "align_fail_rate")

    if _is_mock():
        # The mock's fabricated rows always contain align fails, so an empty
        # triage table means the generator or the filter broke. Office may
        # legitimately have had no align failure in the window.
        assert rows, "mock align ranking must not be empty"


def test_get_meas_ranking_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_meas_ranking(tool_type, fab_names, start_date, end_date, limit=1000, lot_cd=None)
    assert isinstance(rows, list)
    for row in rows:
        assert_matches(row, MeasRankingRow)

    _assert_triage_table(rows, "meas_fail_count", "meas_fail_rate")
    for row in rows:
        # Contract-fixed scales that differ between the two fields: the rate is
        # a fraction, avg_fail_ratio is the mean of per-row PERCENT fail_ratio.
        assert 0.0 <= row["avg_fail_ratio"] <= 100.0

    if _is_mock():
        # Same rationale as align above.
        assert rows, "mock meas ranking must not be empty"


def test_get_devices_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    devices = data.get_devices(tool_type, fab_names, start_date, end_date)
    assert isinstance(devices, list)
    for device in devices:
        assert_matches(device, DeviceRow)
        assert device["align_fail_count"] <= device["exec_count"]
        assert device["meas_fail_count"] <= device["exec_count"]

    if _is_mock():
        # MIGRATION.md calls an empty office /devices result valid (no chips
        # matched); the mock's lot_cd bridge is fabricated and always resolves.
        assert devices, "mock device list must not be empty"


def test_align_ranking_rows_carry_contributing_fabs():
    rows = data.get_align_ranking("cd-sem", ("R3", "M16B"), None, None, limit=20)
    assert rows
    for row in rows:
        assert row["fab_names"] == sorted(row["fab_names"])
        assert row["fab_names"]
        assert set(row["fab_names"]) <= {"R3", "M16B"}


def test_meas_ranking_rows_carry_contributing_fabs():
    rows = data.get_meas_ranking("cd-sem", ("R3", "M16B"), None, None, limit=20)
    assert rows
    for row in rows:
        assert row["fab_names"] == sorted(row["fab_names"])
        assert row["fab_names"]
        assert set(row["fab_names"]) <= {"R3", "M16B"}


def test_single_fab_rankings_tag_that_fab_only():
    align = data.get_align_ranking("cd-sem", ("R3",), None, None, limit=5)
    meas = data.get_meas_ranking("cd-sem", ("R3",), None, None, limit=5)
    assert all(row["fab_names"] == ["R3"] for row in align)
    assert all(row["fab_names"] == ["R3"] for row in meas)


# --- 장비별 뷰 ---------------------------------------------------------------


def test_equipments_payload_matches_the_contract():
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipments(tool_type, fabs, start, end)

    assert_matches(payload, EquipmentsPayload)
    for row in payload["equipments"]:
        assert_matches(row, EquipmentRow)


def test_each_tool_belongs_to_exactly_one_fab():
    """물리 장비는 fab 하나에 있습니다.

    이게 깨지면 장비별 표에서 한 장비가 여러 행으로 쪼개지고, 지수가 각
    조각의 부분 실행 수로 계산되어 전부 틀립니다.
    """
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipments(tool_type, fabs, start, end)

    seen: dict[str, str] = {}
    for row in payload["equipments"]:
        assert row["eqp_id"] not in seen, row["eqp_id"]
        seen[row["eqp_id"]] = row["fab_name"]


def test_fleet_totals_agree_with_the_rows():
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipments(tool_type, fabs, start, end)
    rows = payload["equipments"]
    fleet = payload["fleet"]

    assert fleet["tool_count"] == len(rows)
    assert fleet["total_executions"] == sum(r["exec_count"] for r in rows)
    assert fleet["align_fail_count"] == sum(r["align_fail_count"] for r in rows)
    assert fleet["meas_fail_count"] == sum(r["meas_fail_count"] for r in rows)


def test_equipments_fleet_totals_agree_with_summary():
    """mock.get_equipments 의 위치 기반 격자 인덱싱(cell[4]/[5]/[6])을 지킵니다.

    providers/mock.py 는 exec/align/meas 를 이름 없이 리스트 위치로 채웁니다
    (cell[4]=exec_count, cell[5]=align_fail_count, cell[6]=meas_fail_count) —
    이 순서가 실수로 바뀌어도 test_fleet_totals_agree_with_the_rows 는 잡지
    못합니다: 그 테스트는 /equipments 응답 내부(fleet vs rows)의 일관성만
    보고, /equipments 와 /summary 처럼 서로 다른 경로로 같은 창을 집계한
    두 값을 대조하지 않기 때문입니다. 여기서 그 대조를 합니다 —
    MIGRATION.md 가 office 의 수동 대조 절차로 이미 지시하는 바로 그
    비교입니다.

    mock 전용으로 걸어 둡니다: MIGRATION.md 는 eqp_model_cd.keyword 매핑이
    없으면 office 의 /equipments 가 (실제로는 데이터가 있어도) 빈 표를
    돌려주는 반면 /summary 는 정상 숫자를 돌려주는, 알려진 office 상황을
    문서화하고 있습니다. 이 테스트를 걸어 두지 않으면 그 문서화된 진단
    신호가 빨간 스위트로 뒤집힙니다.
    """
    if not _is_mock():
        pytest.skip("office 는 eqp_model_cd.keyword 미매핑 시 /equipments 만 비어 있을 수 있음 (MIGRATION.md)")

    tool_type, fabs, start, end = _default_scope()
    equipments = data.get_equipments(tool_type, fabs, start, end)
    summary = data.get_summary(tool_type, fabs, start, end, lot_cd=None)
    fleet = equipments["fleet"]

    assert fleet["total_executions"] == summary["total_executions"]
    assert fleet["align_fail_count"] == summary["align_fail_count"]
    assert fleet["meas_fail_count"] == summary["meas_fail_count"]


def test_index_and_its_interval_are_present_or_absent_together():
    """셋 중 하나만 None 인 상태는 있을 수 없습니다."""
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipments(tool_type, fabs, start, end)

    for row in payload["equipments"]:
        for aspect in ("align", "meas"):
            triple = (
                row[f"{aspect}_index"],
                row[f"{aspect}_index_low"],
                row[f"{aspect}_index_high"],
            )
            assert all(v is None for v in triple) or all(v is not None for v in triple), row
            if triple[0] is not None:
                assert triple[1] <= triple[0] <= triple[2], row


def test_equipment_compare_payload_matches_the_contract():
    tool_type, fabs, start, end = _default_scope()
    fleet = data.get_equipments(tool_type, fabs, start, end)
    picked = tuple(r["eqp_id"] for r in fleet["equipments"][:3])

    payload = data.get_equipment_compare(tool_type, fabs, start, end, picked)
    assert_matches(payload, EquipmentComparePayload)

    assert payload["eqp_ids"] == list(picked)
    for series in payload["trends"]:
        assert series["eqp_id"] in picked
    for recipe in payload["recipes"]:
        assert [c["eqp_id"] for c in recipe["cells"]] == list(picked)


def test_compare_trends_cover_the_whole_window():
    tool_type, fabs, start, end = _default_scope()
    fleet = data.get_equipments(tool_type, fabs, start, end)
    picked = tuple(r["eqp_id"] for r in fleet["equipments"][:2])
    if not picked:
        pytest.skip("no equipment in scope")

    payload = data.get_equipment_compare(tool_type, fabs, start, end, picked)
    expected_days = DEFAULT_DAYS + 1        # 양 끝 포함
    for series in payload["trends"]:
        assert len(series["points"]) == expected_days


def test_compare_with_no_selection_is_empty_not_everything():
    """빈 선택에 전체 플릿을 돌려주면 화면이 조용히 거짓말을 합니다."""
    tool_type, fabs, start, end = _default_scope()
    payload = data.get_equipment_compare(tool_type, fabs, start, end, ())
    assert payload["eqp_ids"] == []
    assert payload["trends"] == []
    assert payload["recipes"] == []
