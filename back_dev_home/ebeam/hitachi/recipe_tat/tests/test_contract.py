"""Contract gate for recipe_tat. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
Office: SKEWNONO_RECIPE_TAT_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
"""

from datetime import timedelta

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.recipe_tat import data
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    TAT_INDEX_MIN_SAMPLE,
    DailyTrendPoint,
    DeviceRow,
    EquipmentsPayload,
    RankingRow,
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


def test_get_ranking_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_ranking(tool_type, fab_names, start_date, end_date, limit=0, lot_cd=None)
    assert isinstance(rows, list)
    for row in rows:
        assert_matches(row, RankingRow)


def test_get_ranking_limit_zero_is_uncapped():
    # limit=0 (the route default) must return EVERY recipe in the range —
    # a positive limit trims the same, fully-sorted ranking from the top.
    tool_type, fab_names, start_date, end_date = _default_scope()
    everything = data.get_ranking(tool_type, fab_names, start_date, end_date, limit=0, lot_cd=None)
    top = data.get_ranking(tool_type, fab_names, start_date, end_date, limit=5, lot_cd=None)
    assert len(top) <= 5
    assert len(everything) >= len(top)
    if get_data_provider("recipe_tat") == "mock":
        # Deterministic only for the mock — office data may move between calls.
        assert everything[: len(top)] == top


def test_office_get_meas_hist_is_intentionally_disconnected():
    # Raw-row export is not part of the office wiring (routes only use the
    # aggregation endpoints). Pin that as a loud NotImplementedError so a
    # future office.py copy can't silently return wrong-shaped rows.
    import pytest

    office_example = pytest.importorskip(
        "back_dev_home.ebeam.hitachi.recipe_tat.providers.office_example"
    )
    with pytest.raises(NotImplementedError):
        office_example.get_meas_hist()


def test_get_summary_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    assert_matches(
        data.get_summary(tool_type, fab_names, start_date, end_date, lot_cd=None),
        SummaryPayload,
    )


def test_get_daily_trend_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    points = data.get_daily_trend(tool_type, fab_names, start_date, end_date, lot_cd=None)
    assert isinstance(points, list)
    for point in points:
        assert_matches(point, DailyTrendPoint)


def test_get_devices_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    devices = data.get_devices(tool_type, fab_names, start_date, end_date)
    assert isinstance(devices, list)
    for device in devices:
        assert_matches(device, DeviceRow)


def test_mock_rows_carry_real_sem_list_tools():
    # eqp_id를 지어내지 않습니다 — sem_list가 장비 명부의 진실입니다
    # (_tool_specs.py 모듈 docstring, meas_hist.txt 생성 규칙 1).
    if get_data_provider("recipe_tat") != "mock":
        return
    from back_dev_home.sem_list.providers.mock import _generate_rows

    roster = {}
    for row in _generate_rows():
        roster.setdefault(row["eqp_id"], row)   # 중복 eqp_id는 첫 행이 이깁니다

    for row in data.get_meas_hist():
        tool = roster.get(row["eqp_id"])
        assert tool is not None, f"sem_list에 없는 eqp_id: {row['eqp_id']}"
        assert row["fab_name"] == tool["fab_name"]
        assert row["eqp_model_cd"] == tool["eqp_model_cd"]
        assert row["vendor_nm"] == tool["vendor_nm"]


def test_mock_each_tool_lives_in_exactly_one_fab():
    # 물리 장비는 fab 하나에 있습니다. 이게 깨지면 장비별 표에서 한 장비가
    # 여러 fab에 걸쳐 나타납니다.
    if get_data_provider("recipe_tat") != "mock":
        return
    fabs_by_eqp: dict[str, set[str]] = {}
    for row in data.get_meas_hist():
        fabs_by_eqp.setdefault(row["eqp_id"], set()).add(row["fab_name"])
    offenders = {eqp: fabs for eqp, fabs in fabs_by_eqp.items() if len(fabs) > 1}
    assert not offenders, f"여러 fab에 걸친 장비: {offenders}"


def test_mock_lot_fac_matches_tool_fac():
    # 측정은 장비가 있는 fab에서 일어나고 lot이 거기 들어옵니다.
    if get_data_provider("recipe_tat") != "mock":
        return
    from back_dev_home.ebeam.cdsem.device_statistics.providers.mock import _lot_index

    lot_fac = _lot_index()
    for row in data.get_meas_hist():
        assert lot_fac[row["lot_cd"]] == row["fac_id"]


def test_mock_density_supports_the_tat_index():
    # 기본 조회(fab 1개 · 14일)에서 장비당 실행 수 중앙값이 표본 하한을
    # 넘어야 합니다. 이 가드가 없으면 누가 행 수를 줄였을 때 장비별 표의
    # TAT index 열이 조용히 전부 '—'가 됩니다.
    if get_data_provider("recipe_tat") != "mock":
        return
    import statistics

    anchor = data.get_anchor_time().date()
    end = anchor.isoformat()
    start = (anchor - timedelta(days=14)).isoformat()
    rows = [
        r for r in data.get_meas_hist()
        if r["tool_type"] == "cd-sem" and r["fab_name"] == "R3"
        and start <= r["timestamp"][:10] <= end
    ]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["eqp_id"]] = counts.get(row["eqp_id"], 0) + 1
    assert counts, "R3 / cd-sem / 최근 14일에 측정이 하나도 없습니다"
    assert statistics.median(counts.values()) >= TAT_INDEX_MIN_SAMPLE


def test_get_equipments_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    assert_matches(payload, EquipmentsPayload)


def test_get_equipments_is_sorted_by_total_meastime_desc():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_equipments(tool_type, fab_names, start_date, end_date)["equipments"]
    totals = [row["total_meastime"] for row in rows]
    assert totals == sorted(totals, reverse=True)


def test_get_equipments_totals_agree_with_summary():
    # 같은 범위를 두 엔드포인트가 다르게 집계하면 사용자는 어느 쪽도
    # 믿지 못합니다.
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    summary = data.get_summary(tool_type, fab_names, start_date, end_date, lot_cd=None)
    assert sum(r["exec_count"] for r in payload["equipments"]) == summary["total_executions"]
    assert sum(r["total_meastime"] for r in payload["equipments"]) == summary["total_tat_seconds"]


def test_get_equipments_tat_index_is_none_below_the_sample_floor():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_equipments(tool_type, fab_names, start_date, end_date)["equipments"]
    for row in rows:
        if row["exec_count"] < TAT_INDEX_MIN_SAMPLE:
            assert row["tat_index"] is None
        else:
            assert row["tat_index"] is not None and row["tat_index"] > 0


def test_get_equipments_occupancy_matches_the_window():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    # 포함 일수 × 86400 — start/end 양 끝을 모두 포함합니다.
    assert payload["fleet"]["window_seconds"] == (DEFAULT_DAYS + 1) * 86400
    for row in payload["equipments"]:
        # 6자리 반올림까지 포함해 정의를 고정합니다 (usage_ratio 와 같은 방식).
        # 허용오차 비교로는 반올림 자릿수가 바뀌어도 통과하는데, 그 자릿수는
        # office 어댑터가 그대로 복사해 쓰는 공용 조립기의 계약입니다.
        expected = row["total_meastime"] / payload["fleet"]["window_seconds"]
        assert row["occupancy"] == round(expected, 6)


def test_get_equipments_usage_ratio_is_defined_on_time_not_count():
    # 실행이 적어도 긴 레시피를 도는 장비는 놀고 있지 않습니다. usage_ratio가
    # 실행 수를 따라가면 그런 장비를 저사용으로 오진합니다.
    #
    # "시간 내림차순이면 비율도 내림차순"은 usage_ratio = 시간/중앙값이라
    # 항상 참이라서 아무것도 검증하지 못합니다. 정의를 직접 고정하고,
    # 두 기준이 실제로 갈리는 장비 쌍이 존재하는지도 함께 확인합니다.
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    rows = payload["equipments"]
    median = payload["fleet"]["median_total_meastime"]
    if len(rows) < 2 or not median:
        return

    for row in rows:
        assert row["usage_ratio"] == round(row["total_meastime"] / median, 4)

    # 두 기준이 갈리는 쌍이 하나도 없으면 위 단언은 우연히도 실행 수 기준과
    # 구별되지 않습니다. mock이 그 구별을 실제로 만들어내는지 확인합니다.
    diverges = any(
        (a["total_meastime"] > b["total_meastime"]) != (a["exec_count"] > b["exec_count"])
        for a in rows for b in rows if a is not b
    )
    assert diverges, "시간 순서와 실행 수 순서가 갈리는 장비 쌍이 없습니다"


def test_get_equipments_percentiles_cover_every_metric():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    percentiles = payload["fleet"]["percentiles"]
    for metric in ("usage_ratio", "tat_index", "occupancy", "recipe_count"):
        assert metric in percentiles
        summary = percentiles[metric]
        if not summary:
            continue
        values = [summary[key] for key in ("p10", "p25", "p50", "p75", "p90")]
        assert values == sorted(values)


def test_get_equipments_is_empty_outside_the_data_window():
    # 빈 범위: 목록도 분위수도 비고, 0으로 나누지 않습니다.
    payload = data.get_equipments("cd-sem", None, "1990-01-01", "1990-01-02")
    assert payload["equipments"] == []
    assert payload["fleet"]["tool_count"] == 0
    assert payload["fleet"]["percentiles"] == {
        "usage_ratio": {}, "tat_index": {}, "occupancy": {}, "recipe_count": {}
    }


def test_get_equipments_mock_exercises_every_badge_state():
    # mock이 UI의 모든 상태를 실제로 만들어내지 못하면 홈에서 배지를 검증할
    # 방법이 없습니다. R3 / cd-sem 기본 조회에 각 상태가 1대 이상 있어야
    # 합니다.
    if get_data_provider("recipe_tat") != "mock":
        return
    anchor = data.get_anchor_time().date()
    payload = data.get_equipments(
        "cd-sem", ("R3",), (anchor - timedelta(days=DEFAULT_DAYS)).isoformat(),
        anchor.isoformat()
    )
    rows = payload["equipments"]
    indexed = [r for r in rows if r["tat_index"] is not None]
    assert any(r["tat_index"] is None for r in rows), "표본 미달 장비가 없습니다"
    assert max(r["tat_index"] for r in indexed) > 1.05, "느린 장비가 없습니다"
    assert min(r["usage_ratio"] for r in rows) < 0.85, "저사용 장비가 없습니다"
    assert max(r["top_recipe_share"] for r in rows) >= 0.50, "편중 장비가 없습니다"
