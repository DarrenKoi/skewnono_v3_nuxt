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
    EquipmentComparePayload,
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


def test_office_example_exposes_the_equipment_endpoints():
    # 스텁이 아니라 실제 구현이 자리에 있는지 고정합니다. import 가능해야
    # 하는 이유가 더 중요합니다: office.py 는 이 파일의 사본이고, 여기서
    # ImportError 가 나면 사무실에서는 앱 팩토리 전체가 죽습니다.
    import pytest

    office_example = pytest.importorskip(
        "back_dev_home.ebeam.hitachi.recipe_tat.providers.office_example"
    )
    assert callable(office_example.get_equipments)
    assert callable(office_example.get_equipment_compare)


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
    #
    # 부등호를 양쪽 다 strict 하게 씁니다. `(a>b) != (c>d)` 형태는 exec_count
    # 가 그냥 **같기만** 해도 참이 되는데, 장비 84대짜리 기본 조회에서 실행 수
    # 동률은 사실상 확실히 생깁니다 — 그러면 이 주석이 말하는 순위 역전을
    # 하나도 보여주지 못한 채 통과합니다.
    diverges = any(
        a["total_meastime"] > b["total_meastime"] and a["exec_count"] < b["exec_count"]
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
    # indexed 가 비면 아래 max()가 ValueError 로 터져 의도한 메시지를 삼킵니다.
    # 게다가 바로 위 단언은 그 상황에서도 통과하므로(전부 None), 이 가드가
    # 없으면 "모든 장비가 표본 미달"이라는 mock 퇴행이 엉뚱한 예외로 보고됩니다.
    assert indexed, "tat_index 가 계산된 장비가 하나도 없습니다 (전부 표본 미달)"
    # 프론트엔드 equipmentSignals.ts의 TAT_CEIL은 1.10입니다. 예전 기준
    # (> 1.05)은 그 배지가 실제로 뜰 수 있는지 증명하지 못하는 채로도
    # 통과했습니다 — 1.12로 올려 TAT_CEIL을 여유 있게 넘는지 검증합니다.
    # 백엔드가 프론트엔드 상수를 import할 수 없어 이 주석이 둘을 묶어
    # 둡니다 — TAT_CEIL이 바뀌면 이 숫자도 같이 봐야 합니다.
    #
    # 조회 범위가 R3인 이유는 R3가 최악의 칸이어서가 **아닙니다** — 5대짜리
    # 셀 감쇠가 가장 심한 칸은 M11A입니다(recipe_tat/providers/mock.py의
    # _tool_scalars 독스트링). R3인 이유는 workload 0.30짜리 표본 미달 장비를
    # R3에만 심어 두었기 때문입니다. 위의 "표본 미달 장비가 없습니다" 단언이
    # 성립하는 fab이 R3 하나뿐이라 이 조회가 R3여야 합니다.
    assert max(r["tat_index"] for r in indexed) > 1.12, "느린 장비가 없습니다"
    # 대칭 검증: 프론트엔드 TAT_FLOOR는 0.92입니다. 느림과 같은 이유로
    # 빠름 배지도 실제로 뜨는지 검증이 필요합니다.
    assert min(r["tat_index"] for r in indexed) < 0.92, "빠른 장비가 없습니다"
    assert min(r["usage_ratio"] for r in rows) < 0.85, "저사용 장비가 없습니다"
    assert max(r["top_recipe_share"] for r in rows) >= 0.50, "편중 장비가 없습니다"


def _two_busiest_eqp_ids():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_equipments(tool_type, fab_names, start_date, end_date)["equipments"]
    return tuple(row["eqp_id"] for row in rows[:2])


def test_get_equipment_compare_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, _two_busiest_eqp_ids()
    )
    assert_matches(payload, EquipmentComparePayload)


def test_get_equipment_compare_zero_fills_every_cell():
    # 모든 행의 cells 길이가 선택 장비 수와 같아야 합니다. 짧으면 프론트엔드
    # 열이 밀려서 다른 장비의 숫자를 보여주게 됩니다.
    tool_type, fab_names, start_date, end_date = _default_scope()
    eqp_ids = _two_busiest_eqp_ids()
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, eqp_ids
    )
    for row in payload["recipes"]:
        assert [cell["eqp_id"] for cell in row["cells"]] == list(eqp_ids)


def test_get_equipment_compare_trends_cover_the_whole_range():
    tool_type, fab_names, start_date, end_date = _default_scope()
    eqp_ids = _two_busiest_eqp_ids()
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, eqp_ids
    )
    assert [series["eqp_id"] for series in payload["trends"]] == list(eqp_ids)
    for series in payload["trends"]:
        dates = [point["date"] for point in series["points"]]
        assert dates[0] == start_date and dates[-1] == end_date
        assert dates == sorted(dates)
        assert len(dates) == DEFAULT_DAYS + 1


def test_get_equipment_compare_recipes_sorted_by_total_desc():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, _two_busiest_eqp_ids()
    )
    totals = [row["total_meastime"] for row in payload["recipes"]]
    assert totals == sorted(totals, reverse=True)


def test_get_equipment_compare_with_no_eqp_ids_is_empty():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipment_compare(tool_type, fab_names, start_date, end_date, ())
    assert payload["eqp_ids"] == []
    assert payload["trends"] == []
    assert payload["recipes"] == []


def test_get_equipment_compare_agrees_with_the_equipments_table():
    # 두 엔드포인트가 같은 장비의 같은 기간을 다르게 집계하면, 사용자는
    # 표에서 고른 숫자가 비교 화면에서 달라지는 것을 보게 됩니다.
    tool_type, fab_names, start_date, end_date = _default_scope()
    eqp_ids = _two_busiest_eqp_ids()
    table = {
        row["eqp_id"]: row
        for row in data.get_equipments(tool_type, fab_names, start_date, end_date)[
            "equipments"
        ]
    }
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, eqp_ids
    )

    for index, eqp_id in enumerate(eqp_ids):
        expected = table[eqp_id]
        points = payload["trends"][index]["points"]
        assert sum(p["total_meastime"] for p in points) == expected["total_meastime"]
        assert sum(p["exec_count"] for p in points) == expected["exec_count"]

        cells = [row["cells"][index] for row in payload["recipes"]]
        assert sum(c["total_meastime"] for c in cells) == expected["total_meastime"]
        assert sum(c["meas_counts"] for c in cells) == expected["exec_count"]
        # 0 채움 칸은 레시피 수에 들어가지 않습니다 — 합집합의 다른 장비가
        # 돈 레시피까지 세면 recipe_count 가 부풀어 오릅니다.
        assert sum(1 for c in cells if c["meas_counts"]) == expected["recipe_count"]


def test_request_scope_caps_and_echoes_eqp_ids():
    # 절단을 조용히 하지 않습니다 — 6대를 보내면 5대만 쓰였다는 사실이
    # 응답에 드러나야 합니다.
    from flask import Flask

    from back_dev_home.ebeam.hitachi._analytics_routes import (
        MAX_EQP_IDS,
        resolve_analytics_scope,
    )

    app = Flask(__name__)
    query = "eqp_id=" + ",".join(f"EQP{n}" for n in range(1, 8))
    with app.test_request_context(f"/?{query}"):
        scope = resolve_analytics_scope("cdsem", data.get_anchor_time())
    assert scope is not None
    assert len(scope.eqp_ids) == MAX_EQP_IDS
    assert scope.eqp_ids == ("EQP1", "EQP2", "EQP3", "EQP4", "EQP5")


def test_request_scope_eqp_ids_default_to_empty():
    from flask import Flask

    from back_dev_home.ebeam.hitachi._analytics_routes import resolve_analytics_scope

    app = Flask(__name__)
    with app.test_request_context("/?fab_name=R3"):
        scope = resolve_analytics_scope("cdsem", data.get_anchor_time())
    assert scope is not None and scope.eqp_ids == ()


def test_request_scope_keeps_eqp_id_case_verbatim():
    # fab_name 과 달리 eqp_id 는 대문자로 정규화하지 않습니다 — 사무실
    # 인덱스의 표기를 그대로 term 조회해야 하는 정확 일치 키입니다.
    from flask import Flask

    from back_dev_home.ebeam.hitachi._analytics_routes import resolve_analytics_scope

    app = Flask(__name__)
    with app.test_request_context("/?fab_name=r3&eqp_id=cd-sem_r3_01, Mx01 "):
        scope = resolve_analytics_scope("cdsem", data.get_anchor_time())
    assert scope is not None
    assert scope.eqp_ids == ("cd-sem_r3_01", "Mx01")
    assert scope.fab_names == ("R3",)


def test_ranking_rows_carry_contributing_fabs():
    rows = data.get_ranking("cd-sem", ("R3", "M16B"), None, None, limit=20)
    assert rows
    for row in rows:
        assert row["fab_names"] == sorted(row["fab_names"])
        assert row["fab_names"]
        assert set(row["fab_names"]) <= {"R3", "M16B"}


def test_single_fab_ranking_tags_that_fab_only():
    rows = data.get_ranking("cd-sem", ("R3",), None, None, limit=5)
    assert all(row["fab_names"] == ["R3"] for row in rows)
