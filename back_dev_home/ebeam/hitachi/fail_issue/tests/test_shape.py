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
    build_equipment_compare_payload,
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
#   align: L/EASY 기저 5 %,  L/HARD 기저 30 %  → 기대 80 / 305
#   meas : L/EASY 기저 10 %, L/HARD 기저 40 %  → 기대 140 / 410
#   (align 과 meas 의 건수를 서로 다르게 둔 이유: 두 열이 같은 값이면 한쪽
#   열을 두 번 읽는 오타가 있어도 이 격자로는 잡히지 않습니다.)
#   EQ-EASYMIX : EASY 1000회(align 50 / meas 100) + HARD 100회(align 30 / meas 40)
#   EQ-HARDMIX : EASY  100회(align  5 / meas  10) + HARD 1000회(align 300 / meas 400)
#
# 원 실패율은 align 7.27 % 대 27.73 %, meas 12.73 % 대 37.27 % 로 벌어지지만
# 장비 상태는 동일합니다. 두 지수 모두 둘 다 정확히 1.0 이어야 합니다.
MIX_GRID = [
    ("EQ-EASYMIX", FAB, MODEL, "L/EASY", 1000, 50, 100),
    ("EQ-EASYMIX", FAB, MODEL, "L/HARD", 100, 30, 40),
    ("EQ-HARDMIX", FAB, MODEL, "L/EASY", 100, 5, 10),
    ("EQ-HARDMIX", FAB, MODEL, "L/HARD", 1000, 300, 400),
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

    # align 과 meas 의 건수·기저율이 서로 다르므로, 한쪽 열을 두 번 읽는
    # 오타는 여기서 반드시 드러납니다. (같은 값이었을 때 이 주장은
    # 데이터가 뒷받침하지 못하는 빈 주장이었습니다.)
    assert easy["align_fail_count"] == 80
    assert easy["meas_fail_count"] == 140
    assert easy["meas_expected"] == pytest.approx(140.0, abs=1e-6)
    assert hard["meas_expected"] == pytest.approx(410.0, abs=1e-6)
    assert easy["meas_fail_rate"] == pytest.approx(0.1273, abs=1e-4)
    assert hard["meas_fail_rate"] == pytest.approx(0.3727, abs=1e-4)
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
# 순수하게 장비 차이입니다. EQ-C 만 3배 실패합니다. align 과 meas 건수를
# 다르게 둔 이유는 위 MIX_GRID 와 같습니다 — 열이 뒤바뀌어도 걸리도록.
SAME_MIX_GRID = [
    ("EQ-A", FAB, MODEL, "L/EASY", 1000, 50, 80),
    ("EQ-B", FAB, MODEL, "L/EASY", 1000, 50, 80),
    ("EQ-C", FAB, MODEL, "L/EASY", 1000, 150, 240),
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

    # 같은 장비의 meas 지수도 1.8 이지만 **다른 건수·다른 기대치**에서
    # 나옵니다 (240 / 133.33). 두 열이 뒤바뀌면 2.88 또는 1.125 가 나와
    # 이 두 주장이 동시에 성립할 수 없습니다.
    assert rows["EQ-C"]["meas_fail_count"] == 240
    assert rows["EQ-C"]["meas_expected"] == pytest.approx(133.3333, abs=1e-3)
    assert rows["EQ-C"]["meas_index"] == pytest.approx(1.8, abs=1e-3)
    assert rows["EQ-A"]["meas_expected"] == pytest.approx(133.3333, abs=1e-3)
    assert rows["EQ-A"]["meas_index"] == pytest.approx(0.6, abs=1e-3)


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


# --- 비교 payload -----------------------------------------------------------

COMPARE_START, COMPARE_END = "2026-08-01", "2026-08-03"   # 3일


def _compare(eqp_ids, trend_rows, recipe_rows):
    return build_equipment_compare_payload(
        "cd-sem", (FAB,), COMPARE_START, COMPARE_END,
        eqp_ids, trend_rows, recipe_rows,
    )


def test_cells_follow_the_requested_order_and_zero_fill_absentees():
    """열이 밀리면 비교표가 다른 장비의 숫자를 보여줍니다.

    EQ-TWO 는 R/ONLYONE 을 돌지 않았으므로 그 칸이 0 이어야 하고, cells 의
    순서는 요청 순서(EQ-ONE, EQ-TWO)를 그대로 따라야 합니다.
    """
    payload = _compare(
        ["EQ-ONE", "EQ-TWO"],
        [],
        [
            ("EQ-ONE", "R/ONLYONE", 100, 10, 12),
            ("EQ-ONE", "R/SHARED", 50, 5, 6),
            ("EQ-TWO", "R/SHARED", 70, 7, 8),
        ],
    )

    assert payload["eqp_ids"] == ["EQ-ONE", "EQ-TWO"]
    by_name = {row["full_name"]: row for row in payload["recipes"]}

    only = by_name["R/ONLYONE"]
    assert [c["eqp_id"] for c in only["cells"]] == ["EQ-ONE", "EQ-TWO"]
    assert only["cells"][0]["align_fail_count"] == 10
    assert only["cells"][1] == {
        "eqp_id": "EQ-TWO",
        "exec_count": 0,
        "align_fail_count": 0,
        "meas_fail_count": 0,
    }

    shared = by_name["R/SHARED"]
    assert shared["total_exec_count"] == 120
    assert shared["total_align_fail_count"] == 12
    assert shared["total_meas_fail_count"] == 14


def test_full_name_splits_into_class_and_recipe_on_the_first_slash():
    payload = _compare(
        ["EQ-ONE"], [], [("EQ-ONE", "ADI/M1/CD", 10, 1, 1)]
    )
    row = payload["recipes"][0]
    assert row["class_name"] == "ADI"
    assert row["recipe_name"] == "M1/CD"
    assert row["full_name"] == "ADI/M1/CD"


def test_trends_cover_every_day_in_range_even_when_silent():
    """조용한 날을 건너뛰면 x축이 거짓말을 합니다."""
    payload = _compare(
        ["EQ-ONE"],
        [("EQ-ONE", "2026-08-02", 30, 3, 4)],
        [],
    )
    points = payload["trends"][0]["points"]
    assert [p["date"] for p in points] == ["2026-08-01", "2026-08-02", "2026-08-03"]
    assert points[0]["exec_count"] == 0
    assert points[1]["align_fail_count"] == 3
    assert points[2]["meas_fail_count"] == 0


def test_rows_outside_the_selection_are_ignored():
    """범위 밖 장비의 행이 섞여 들어와도 합계를 오염시키면 안 됩니다."""
    payload = _compare(
        ["EQ-ONE"],
        [("EQ-GHOST", "2026-08-02", 999, 99, 99)],
        [("EQ-GHOST", "R/SHARED", 999, 99, 99)],
    )
    assert payload["recipes"] == []
    assert all(p["exec_count"] == 0 for p in payload["trends"][0]["points"])


def test_duplicate_eqp_ids_collapse_while_preserving_order():
    payload = _compare(["EQ-B", "EQ-A", "EQ-B"], [], [])
    assert payload["eqp_ids"] == ["EQ-B", "EQ-A"]


def test_empty_selection_returns_an_empty_payload():
    payload = _compare([], [], [])
    assert payload["eqp_ids"] == []
    assert payload["trends"] == []
    assert payload["recipes"] == []


def test_recipes_sort_by_combined_fails_then_name():
    """백엔드는 활성 탭을 모르므로 두 지표를 합친 결정적 순서만 보장합니다.

    프론트엔드가 활성 aspect 로 다시 정렬하지만, 페이지네이션이 안정적이려면
    백엔드 순서에 동률 파훼가 있어야 합니다.
    """
    payload = _compare(
        ["EQ-ONE"],
        [],
        [
            ("EQ-ONE", "R/LOW", 100, 1, 1),
            ("EQ-ONE", "R/HIGH", 100, 20, 30),
            ("EQ-ONE", "B/TIE", 100, 5, 5),
            ("EQ-ONE", "A/TIE", 100, 5, 5),
        ],
    )
    assert [r["full_name"] for r in payload["recipes"]] == [
        "R/HIGH", "A/TIE", "B/TIE", "R/LOW"
    ]
