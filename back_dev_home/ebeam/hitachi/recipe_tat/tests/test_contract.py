"""Contract gate for recipe_tat. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
Office: SKEWNONO_RECIPE_TAT_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/recipe_tat
"""

from datetime import timedelta

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.recipe_tat import data
from back_dev_home.ebeam.hitachi.recipe_tat.contracts import (
    DailyTrendPoint,
    DeviceRow,
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
    assert statistics.median(counts.values()) >= 12
