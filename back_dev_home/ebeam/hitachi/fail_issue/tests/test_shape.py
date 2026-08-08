"""`build_equipments_payload` 자체를 격자 하나로 직접 검증합니다.

test_contract.py 는 활성 provider 를 통해서만 이 함수에 닿습니다. 그런데
office 어댑터는 mock 을 전혀 거치지 않고 이 함수를 부르므로, 조립기의
불변식은 provider 와 무관하게 고정되어야 합니다.

여기서 지키는 것은 **간접표준화 그 자체**입니다. 계약 검사와 분위수 단조성
테스트는 `expected(t) = Σ_r exec(t,r) × base(r)` 를
`expected(t) = exec_count(t) × 플릿전체실패율` 이라는 순진한 식으로 바꿔도
그대로 통과합니다 — 즉 이 지수가 존재하는 이유(레시피 난이도가 아니라 장비를
재는 것)를 그 테스트들은 하나도 지키지 못합니다. 아래 격자들은 두 식의 답이
**설계상 달라지도록** 만들어져 있어서, 순진한 식으로 바꾸면 실패합니다.
"""

import pytest

from back_dev_home.ebeam.hitachi.fail_issue.providers._shape import (
    build_equipments_payload,
)


MODEL = "CG6300"
FAB = "R3"
START, END = "2026-07-25", "2026-08-08"


def _payload(grid):
    return build_equipments_payload("cd-sem", (FAB,), START, END, grid)


def _by_id(payload) -> dict:
    return {row["eqp_id"]: row for row in payload["equipments"]}


# 레시피 난이도가 다른 두 레시피를 정반대 비율로 도는 두 장비. 각 레시피에서
# 둘 다 **정확히 플릿 평균 실패율**입니다.
#
#   L/EASY  기저 5 %,  L/HARD  기저 30 %
#   EQ-EASYMIX : EASY 1000회(50 실패) + HARD  100회( 30 실패)
#   EQ-HARDMIX : EASY  100회( 5 실패) + HARD 1000회(300 실패)
#
# 원 실패율은 7.27 % 대 27.73 % 로 4배 가까이 벌어지지만 장비 상태는 동일
# 합니다. 지수는 둘 다 정확히 1.0 이어야 합니다.
MIX_GRID = [
    ("EQ-EASYMIX", FAB, MODEL, "L/EASY", 1000, 50, 50),
    ("EQ-EASYMIX", FAB, MODEL, "L/HARD", 100, 30, 30),
    ("EQ-HARDMIX", FAB, MODEL, "L/EASY", 100, 5, 5),
    ("EQ-HARDMIX", FAB, MODEL, "L/HARD", 1000, 300, 300),
]


def test_recipe_mix_cancels_out_so_equal_tools_both_score_one():
    rows = _by_id(_payload(MIX_GRID))

    easy = rows["EQ-EASYMIX"]
    hard = rows["EQ-HARDMIX"]

    # 원 비율은 크게 다릅니다 — 이 차이를 지수가 흡수하는 것이 요점입니다.
    assert easy["align_fail_rate"] == pytest.approx(0.0727, abs=1e-4)
    assert hard["align_fail_rate"] == pytest.approx(0.2773, abs=1e-4)

    assert easy["align_expected"] == pytest.approx(80.0, abs=1e-6)
    assert hard["align_expected"] == pytest.approx(305.0, abs=1e-6)
    assert easy["align_index"] == pytest.approx(1.0, abs=1e-4)
    assert hard["align_index"] == pytest.approx(1.0, abs=1e-4)

    # meas 는 같은 격자 열이므로 같은 답이 나와야 합니다. align 열을 실수로
    # 두 번 읽는 오타를 잡습니다.
    assert easy["meas_index"] == pytest.approx(1.0, abs=1e-4)
    assert hard["meas_index"] == pytest.approx(1.0, abs=1e-4)


def test_an_average_tool_gets_an_interval_that_straddles_one():
    """지수가 1.0 이면 구간이 1.0 을 걸쳐야 하고, 그래서 배지가 없습니다."""
    rows = _by_id(_payload(MIX_GRID))
    easy = rows["EQ-EASYMIX"]
    assert easy["align_index_low"] < 1.0 < easy["align_index_high"]
    assert easy["align_index_low"] == pytest.approx(0.7929, abs=1e-4)
    assert easy["align_index_high"] == pytest.approx(1.2446, abs=1e-4)


# 세 장비가 **같은 레시피만** 돕니다 — 레시피 구성이 동일하므로 지수 차이는
# 순수하게 장비 차이입니다. EQ-C 만 3배 실패합니다.
SAME_MIX_GRID = [
    ("EQ-A", FAB, MODEL, "L/EASY", 1000, 50, 50),
    ("EQ-B", FAB, MODEL, "L/EASY", 1000, 50, 50),
    ("EQ-C", FAB, MODEL, "L/EASY", 1000, 150, 150),
]


def test_a_genuinely_worse_tool_gets_an_interval_clear_of_one():
    rows = _by_id(_payload(SAME_MIX_GRID))

    # base = (50+50+150)/3000 = 0.08333 → expected = 83.333 for each
    assert rows["EQ-C"]["align_expected"] == pytest.approx(83.3333, abs=1e-3)
    assert rows["EQ-C"]["align_index"] == pytest.approx(1.8, abs=1e-3)
    assert rows["EQ-C"]["align_index_low"] == pytest.approx(1.5235, abs=1e-3)
    # 하한이 1.0 위 — 잡음으로 설명되지 않습니다.
    assert rows["EQ-C"]["align_index_low"] > 1.0

    assert rows["EQ-A"]["align_index"] == pytest.approx(0.6, abs=1e-3)
    assert rows["EQ-A"]["align_index_high"] == pytest.approx(0.791, abs=1e-3)
    # 상한이 1.0 아래 — 진짜로 좋습니다.
    assert rows["EQ-A"]["align_index_high"] < 1.0


def test_index_is_none_below_the_display_floor():
    """기대 실패가 1건 미만이면 지수도 구간도 없습니다."""
    grid = [
        ("EQ-BUSY", FAB, MODEL, "L/RARE", 10_000, 10, 10),
        ("EQ-QUIET", FAB, MODEL, "L/RARE", 5, 0, 0),
    ]
    rows = _by_id(_payload(grid))

    # base = 10/10005 ≈ 0.001 → EQ-QUIET 의 기대는 0.005건
    quiet = rows["EQ-QUIET"]
    assert quiet["align_index"] is None
    assert quiet["align_index_low"] is None
    assert quiet["align_index_high"] is None
    # 원 수치는 그대로 남습니다 — 판단만 보류하지 정보를 지우지 않습니다.
    assert quiet["exec_count"] == 5
    assert quiet["align_fail_count"] == 0


def test_percentiles_exclude_tools_without_an_index():
    """None 을 0 으로 채우면 p10 이 통째로 무너집니다."""
    grid = [
        ("EQ-BUSY", FAB, MODEL, "L/RARE", 10_000, 10, 10),
        ("EQ-QUIET", FAB, MODEL, "L/RARE", 5, 0, 0),
    ]
    payload = _payload(grid)
    percentiles = payload["fleet"]["percentiles"]["align_index"]
    # 지수를 가진 장비가 EQ-BUSY 하나뿐이므로 모든 분위수가 그 값입니다.
    # (base = 10/10005 이라 EQ-BUSY 의 지수는 정확히 1 이 아니라 1.0005 입니다 —
    #  EQ-QUIET 의 실행 5건이 분모에 들어가기 때문입니다.)
    assert set(percentiles) == {"p10", "p25", "p50", "p75", "p90"}
    assert all(v == pytest.approx(1.0, abs=1e-2) for v in percentiles.values())
    assert len(set(percentiles.values())) == 1


def test_percentiles_are_empty_when_nothing_qualifies():
    grid = [("EQ-QUIET", FAB, MODEL, "L/RARE", 5, 0, 0)]
    payload = _payload(grid)
    # base=0 → expected=0 → 하한 미달 → 대상 없음 → 빈 dict("판단 근거 없음")
    assert payload["fleet"]["percentiles"]["align_index"] == {}


def test_top_recipe_is_by_execution_count_with_a_deterministic_tiebreak():
    """동률이면 full_name 사전순 뒤가 이깁니다.

    tat 만으로 비교하면 dict 삽입 순서가 승자를 정하는데, 그 순서는
    mock(행 스캔)과 office(composite 버킷)가 서로 다릅니다.
    """
    grid = [
        ("EQ-TIE", FAB, MODEL, "A/FIRST", 100, 5, 5),
        ("EQ-TIE", FAB, MODEL, "Z/LAST", 100, 5, 5),
    ]
    row = _by_id(_payload(grid))["EQ-TIE"]
    assert row["top_recipe"] == "Z/LAST"
    assert row["top_recipe_share"] == pytest.approx(0.5, abs=1e-4)
    assert row["recipe_count"] == 2


def test_fleet_totals_match_the_sum_of_rows():
    payload = _payload(MIX_GRID)
    fleet = payload["fleet"]
    rows = payload["equipments"]

    assert fleet["tool_count"] == len(rows) == 2
    assert fleet["total_executions"] == sum(r["exec_count"] for r in rows)
    assert fleet["align_fail_count"] == sum(r["align_fail_count"] for r in rows)
    assert fleet["meas_fail_count"] == sum(r["meas_fail_count"] for r in rows)
    assert fleet["min_expected_fails"] == 1.0
    assert fleet["confidence_z"] == 1.96


def test_rows_sort_by_execution_count_desc_then_eqp_id():
    grid = [
        ("EQ-B", FAB, MODEL, "L/X", 100, 10, 10),
        ("EQ-A", FAB, MODEL, "L/X", 100, 10, 10),
        ("EQ-C", FAB, MODEL, "L/X", 500, 50, 50),
    ]
    ids = [r["eqp_id"] for r in _payload(grid)["equipments"]]
    assert ids == ["EQ-C", "EQ-A", "EQ-B"]


def test_empty_grid_yields_an_empty_but_well_formed_payload():
    payload = _payload([])
    assert payload["equipments"] == []
    assert payload["fleet"]["tool_count"] == 0
    assert payload["fleet"]["align_fail_rate"] == 0.0
    assert payload["fleet"]["median_exec_count"] == 0.0
    assert payload["fleet"]["percentiles"]["exec_count"] == {}
