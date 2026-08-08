"""`build_equipments_payload` 자체를 격자 하나로 직접 검증합니다.

test_contract.py 는 활성 provider 를 통해서만 이 함수에 닿습니다. 그런데
office 어댑터(Task 6)는 mock 을 전혀 거치지 않고 이 함수를 부르므로, 조립기의
불변식은 provider 와 무관하게 고정되어야 합니다.

여기서 지키는 것은 **간접표준화 그 자체**입니다. 계약·표본 하한·분위수
단조성 테스트는 전부 `expected(t) = Σ_r count(t,r) × base(r)` 를
`expected(t) = exec_count(t) × 플릿전체평균` 이라는 순진한 식으로 바꿔도
그대로 통과합니다 — 즉 이 지수가 존재하는 이유(일감 종류가 아니라 장비를
재는 것)를 그 테스트들은 하나도 지키지 못합니다. 아래 격자는 두 식의 답이
**설계상 달라지도록** 만들어져 있어서, 순진한 식으로 바꾸면 실패합니다.
"""

from back_dev_home.ebeam.recipe_tat.contracts import TAT_INDEX_MIN_SAMPLE
from back_dev_home.ebeam.recipe_tat.providers._shape import (
    EquipmentGridRow,
    build_equipment_compare_payload,
    build_equipments_payload,
    days_in_range,
    window_seconds,
)


MODEL = "CG6300"
FAB = "R3"
START, END = "2026-07-25", "2026-08-08"


def _payload(grid):
    # Fixtures stay positional — a table of 6-tuples is what makes the ratios
    # in these tests readable at a glance. This is the ONE place position maps
    # to name, and the constructor checks the arity.
    return build_equipments_payload(
        "cd-sem", (FAB,), START, END, [EquipmentGridRow(*row) for row in grid]
    )


def _by_id(payload) -> dict:
    return {row["eqp_id"]: row for row in payload["equipments"]}


def test_same_work_at_the_same_rate_scores_1_regardless_of_recipe_mix():
    """레시피 구성만 다르고 속도는 같은 두 장비 — 둘 다 정확히 1.0.

    EQ-FASTMIX 는 빠른 레시피(100 s) 위주, EQ-SLOWMIX 는 느린 레시피(500 s)
    위주로 돌되 **각 레시피에서는 둘 다 정확히 플릿 평균 속도**입니다. 평균
    TAT 은 140 s 대 460 s 로 3배 넘게 벌어지지만 장비 상태는 동일하므로
    지수는 둘 다 1.0 이어야 합니다.

    두 장비가 두 레시피를 모두 돌기 때문에 `base(r)` 이 실제로 장비를 가로질러
    평균낸 값입니다 — 한 장비가 어떤 레시피의 유일한 실행자여서 그 항이 자동
    으로 1.0 이 되는 퇴화 사례가 아닙니다.
    """
    grid = [
        ("EQ-FASTMIX", FAB, MODEL, "QC/FAST_001", 18, 1800),    # 100 s/회
        ("EQ-FASTMIX", FAB, MODEL, "ADI/SLOW_001", 2, 1000),    # 500 s/회
        ("EQ-SLOWMIX", FAB, MODEL, "QC/FAST_001", 2, 200),      # 100 s/회
        ("EQ-SLOWMIX", FAB, MODEL, "ADI/SLOW_001", 18, 9000),   # 500 s/회
    ]
    rows = _by_id(_payload(grid))
    fast_mix, slow_mix = rows["EQ-FASTMIX"], rows["EQ-SLOWMIX"]

    # 표본 하한을 넘겨야 지수가 계산됩니다 (넘지 못하면 아래가 None 비교로
    # 통과해버리는 게 아니라 실패하지만, 의도를 분명히 해 둡니다).
    assert fast_mix["exec_count"] >= TAT_INDEX_MIN_SAMPLE
    assert slow_mix["exec_count"] >= TAT_INDEX_MIN_SAMPLE

    assert fast_mix["tat_index"] == 1.0
    assert slow_mix["tat_index"] == 1.0

    # 평균 TAT 은 크게 다릅니다 — 지수가 평균을 따라갔다면 여기서 갈렸어야 합니다.
    assert fast_mix["avg_meastime"] == 140.0
    assert slow_mix["avg_meastime"] == 460.0

    # 순진한 식(장비 실행 수 × 플릿 전체 평균)이었다면 같은 격자에서 0.47 과
    # 1.53 이 나옵니다. 이 두 줄이 위 단언을 "그냥 참인 값"이 아니게 만듭니다.
    fleet_avg = (2800 + 9200) / 40
    assert round(2800 / (20 * fleet_avg), 4) == 0.4667
    assert round(9200 / (20 * fleet_avg), 4) == 1.5333


def test_a_genuinely_slower_tool_scores_above_1_by_the_constructed_ratio():
    """같은 레시피를 20 % 느리게 도는 장비 — 지수 비가 정확히 1.2.

    앞 테스트가 "일감이 다르면 지수가 흔들리지 않는다"를 지킨다면, 이 테스트는
    "장비가 실제로 느리면 지수가 움직인다"를 지킵니다. 둘 다 있어야 지수가
    상수 1.0 으로 퇴화하는 구현을 잡아냅니다.
    """
    grid = [
        ("EQ-NORMAL", FAB, MODEL, "GATE/CD_001", 12, 1200),   # 100 s/회
        ("EQ-SLUGGISH", FAB, MODEL, "GATE/CD_001", 12, 1440),  # 120 s/회 = 1.2배
    ]
    rows = _by_id(_payload(grid))
    normal, sluggish = rows["EQ-NORMAL"], rows["EQ-SLUGGISH"]

    # base = 2640/24 = 110 s. 기대 TAT 은 양쪽 다 12 × 110 = 1320.
    assert normal["tat_index"] == 0.9091      # 1200/1320
    assert sluggish["tat_index"] == 1.0909    # 1440/1320
    assert sluggish["tat_index"] > 1.0 > normal["tat_index"]

    # 구성한 20 % 차이가 지수 비로 그대로 살아남습니다.
    assert abs(sluggish["tat_index"] / normal["tat_index"] - 1.2) < 1e-3


def test_a_zero_count_cell_is_skipped_instead_of_raising():
    """실행 0건 버킷이 섞여도 터지지 않고, 분모를 부풀리지도 않습니다.

    mock 은 행마다 count 를 1씩 더하므로 count 0 인 칸을 만들 수 없지만,
    office 의 composite 집계는 doc_count 0 인 버킷을 낼 수 있습니다. 즉 이
    경로는 mock 이 영원히 밟지 못하는, office 에서만 처음 실행되는 코드입니다.
    """
    grid = [
        ("EQ-GHOST", FAB, MODEL, "GATE/CD_001", 12, 1200),
        ("EQ-GHOST", FAB, MODEL, "GATE/NEVER_RAN_001", 0, 0),
    ]
    row = _by_id(_payload(grid))["EQ-GHOST"]

    # 실행이 있는 레시피만 분모에 들어갑니다: 12 × 100 = 1200 → 정확히 1.0.
    # 0.0 을 더하는 구현이었다면 분모가 그대로라 여기서는 같아 보이지만,
    # base 에 없는 이름을 인덱싱하는 구현이었다면 KeyError 로 터집니다.
    assert row["tat_index"] == 1.0
    assert row["total_meastime"] == 1200


def test_below_the_sample_floor_the_index_is_unknown_not_fast():
    """표본 미달 장비는 None 이고, 분위수 표본에서도 빠집니다.

    "모른다"를 0.0 으로 채워 세면 p10 이 바닥으로 끌려가 프론트엔드의 꼬리
    판정이 의미를 잃습니다.
    """
    grid = [
        ("EQ-STARVED", FAB, MODEL, "QC/FAST_001", TAT_INDEX_MIN_SAMPLE - 1, 100),
        ("EQ-BUSY", FAB, MODEL, "QC/FAST_001", TAT_INDEX_MIN_SAMPLE, 1200),
    ]
    payload = _payload(grid)
    rows = _by_id(payload)
    assert rows["EQ-STARVED"]["tat_index"] is None
    assert rows["EQ-BUSY"]["tat_index"] is not None

    # 지수를 가진 장비가 1대뿐이므로 모든 분위수가 그 한 값이어야 합니다.
    # 미달 장비를 0.0 으로 섞었다면 p10 이 0.0 으로 내려앉습니다.
    percentiles = payload["fleet"]["percentiles"]["tat_index"]
    assert set(percentiles.values()) == {rows["EQ-BUSY"]["tat_index"]}


def test_top_recipe_ties_break_on_full_name_not_insertion_order():
    """총 TAT 이 같은 레시피가 둘일 때 승자가 격자 순서에 흔들리지 않습니다.

    `top_recipe` 는 표에 그대로 표시되고 `편중` 배지의 입력이기도 합니다.
    tat 만으로 `max` 를 하면 동률에서 dict 삽입 순서 — 즉 격자가 도착한
    순서 — 가 승자를 정하는데, 그 순서는 mock(행 스캔)과 office(composite
    버킷)가 서로 다릅니다. 같은 격자를 뒤집어 넣어도 같은 답이 나와야
    합니다.
    """
    forward = [
        ("EQ-TIE", FAB, MODEL, "QC/AAA_001", 6, 600),
        ("EQ-TIE", FAB, MODEL, "QC/ZZZ_001", 6, 600),
    ]
    reverse = list(reversed(forward))

    assert _by_id(_payload(forward))["EQ-TIE"]["top_recipe"] == \
        _by_id(_payload(reverse))["EQ-TIE"]["top_recipe"]
    # 어느 쪽이 이기는지까지 못박아 둡니다 — "정해져 있다"만 검사하면
    # 규칙을 뒤집는 변경이 조용히 통과합니다.
    assert _by_id(_payload(forward))["EQ-TIE"]["top_recipe"] == "QC/ZZZ_001"


def test_window_seconds_includes_both_endpoints_and_refuses_bad_ranges():
    assert window_seconds("2026-08-01", "2026-08-01") == 86400
    assert window_seconds("2026-07-25", "2026-08-08") == 15 * 86400
    assert window_seconds("2026-08-08", "2026-07-25") == 0    # 뒤집힌 범위
    assert window_seconds(None, "2026-08-08") == 0


def test_days_in_range_includes_both_endpoints_and_refuses_bad_ranges():
    assert days_in_range("2026-08-01", "2026-08-03") == [
        "2026-08-01", "2026-08-02", "2026-08-03"
    ]
    assert days_in_range("2026-08-01", "2026-08-01") == ["2026-08-01"]
    assert days_in_range("2026-08-03", "2026-08-01") == []    # 뒤집힌 범위
    assert days_in_range(None, "2026-08-03") == []
    assert days_in_range("2026-08-01", None) == []


# --------------------------------------------------------------------------
# build_equipment_compare_payload
#
# 프론트엔드는 `cells` 를 **위치로** 읽습니다 — n번째 칸이 응답의 n번째
# eqp_id 라고 믿습니다. 그래서 아래 격자는 세 가지 그럴듯한 오구현이 모두
# 실패하도록 짜여 있습니다:
#
#   1. 열을 집합(set)으로 만든 구현      -> 순서가 요청과 달라집니다
#   2. 열을 격자 등장 순서로 만든 구현    -> REQUESTED 와 다릅니다
#   3. 실제로 돈 장비만 열로 만든 구현    -> ONLY_A 행이 4칸이 안 됩니다
#
# 요청 순서(EQ-C, EQ-A, EQ-IDLE, EQ-B)는 격자 등장 순서(EQ-A, EQ-B, EQ-C)와
# 다르고, 알파벳 순서·집합 순회 순서와도 다릅니다. 칸마다 값이 전부 달라서
# 열이 한 칸만 밀려도 값 단언에서 잡힙니다.
# --------------------------------------------------------------------------

COMPARE_START, COMPARE_END = "2026-08-01", "2026-08-03"

# EQ-IDLE 은 선택됐지만 이 범위에 측정이 하나도 없는 장비입니다.
REQUESTED = ("EQ-C", "EQ-A", "EQ-IDLE", "EQ-B")

# (eqp_id, full_name, meas_counts, total_meastime)
RECIPE_GRID = [
    ("EQ-A", "ADI/SHARED_001", 3, 300),      # 100 s/회
    ("EQ-B", "ADI/SHARED_001", 5, 1000),     # 200 s/회
    ("EQ-C", "ADI/SHARED_001", 2, 500),      # 250 s/회
    ("EQ-A", "QC/ONLY_A_001", 4, 400),       # EQ-A 만 돈 레시피
    ("EQ-OUTSIDE", "ADI/SHARED_001", 99, 99_000),   # 선택되지 않은 장비
]

# (eqp_id, date, total_meastime, exec_count)
TREND_GRID = [
    ("EQ-A", "2026-08-02", 300, 3),
    ("EQ-A", "2026-08-01", 400, 4),
    ("EQ-B", "2026-08-02", 1000, 5),
    ("EQ-C", "2026-08-03", 500, 2),
    ("EQ-A", "2026-07-30", 999, 9),          # 조회 범위 밖의 날
    ("EQ-OUTSIDE", "2026-08-01", 999, 9),    # 선택되지 않은 장비
]


def _compare(eqp_ids=REQUESTED, trend_rows=TREND_GRID, recipe_rows=RECIPE_GRID):
    return build_equipment_compare_payload(
        "cd-sem", (FAB,), COMPARE_START, COMPARE_END, eqp_ids, trend_rows, recipe_rows
    )


def _recipe_row(payload, full_name) -> dict:
    return next(row for row in payload["recipes"] if row["full_name"] == full_name)


def test_compare_cells_follow_the_requested_order_not_the_grid_order():
    """모든 행의 칸이 **요청 순서 그대로** 4개여야 합니다.

    이 단언이 지키는 것은 프론트엔드가 `cells[i]` 를 `eqp_ids[i]` 로 읽는다는
    계약입니다. 라벨만 맞고 값이 밀린 구현을 잡으려고 값까지 함께 고정합니다 —
    칸마다 (건수, 시간, 평균)이 전부 다른 값이라 한 칸만 어긋나도 실패합니다.
    """
    payload = _compare()
    assert payload["eqp_ids"] == list(REQUESTED)

    shared = _recipe_row(payload, "ADI/SHARED_001")
    assert shared["cells"] == [
        {"eqp_id": "EQ-C", "meas_counts": 2, "total_meastime": 500, "avg_meastime": 250.0},
        {"eqp_id": "EQ-A", "meas_counts": 3, "total_meastime": 300, "avg_meastime": 100.0},
        {"eqp_id": "EQ-IDLE", "meas_counts": 0, "total_meastime": 0, "avg_meastime": 0.0},
        {"eqp_id": "EQ-B", "meas_counts": 5, "total_meastime": 1000, "avg_meastime": 200.0},
    ]


def test_compare_zero_fills_tools_that_never_ran_the_recipe():
    """한 장비만 돈 레시피도 선택 장비 수만큼 칸을 갖습니다.

    돈 장비만 칸을 만드는 구현이면 이 행은 1칸짜리가 되어, 프론트엔드에서
    EQ-A 의 숫자가 EQ-C 열 아래에 그려집니다.
    """
    only_a = _recipe_row(_compare(), "QC/ONLY_A_001")
    assert only_a["cells"] == [
        {"eqp_id": "EQ-C", "meas_counts": 0, "total_meastime": 0, "avg_meastime": 0.0},
        {"eqp_id": "EQ-A", "meas_counts": 4, "total_meastime": 400, "avg_meastime": 100.0},
        {"eqp_id": "EQ-IDLE", "meas_counts": 0, "total_meastime": 0, "avg_meastime": 0.0},
        {"eqp_id": "EQ-B", "meas_counts": 0, "total_meastime": 0, "avg_meastime": 0.0},
    ]


def test_compare_ignores_grid_rows_for_unselected_tools():
    """선택 밖 장비의 행은 합계에도 열에도 들어오지 않습니다.

    office 집계는 필터를 걸어도 선택 밖 버킷을 낼 수 있습니다(예: 상한 절단
    이후). 그 행을 그냥 넣으면 `cells[eqp_id]` 에서 KeyError 로 터지고,
    합계만 더하는 구현이면 조용히 남의 시간이 섞입니다.
    """
    payload = _compare()
    assert "EQ-OUTSIDE" not in payload["eqp_ids"]
    assert all(series["eqp_id"] != "EQ-OUTSIDE" for series in payload["trends"])
    # 500 + 300 + 1000 — EQ-OUTSIDE 의 99,000 이 빠져 있어야 합니다.
    assert _recipe_row(payload, "ADI/SHARED_001")["total_meastime"] == 1800


def test_compare_recipes_are_sorted_by_the_selection_total():
    payload = _compare()
    assert [row["full_name"] for row in payload["recipes"]] == [
        "ADI/SHARED_001", "QC/ONLY_A_001"
    ]
    assert [row["total_meastime"] for row in payload["recipes"]] == [1800, 400]


def test_compare_splits_full_name_at_the_first_slash_only():
    """full_name = f"{class_name}/{recipe_name}" 이므로 첫 '/' 로만 나눕니다.

    레시피 이름 자체에 '/' 가 들어간 경우 마지막 '/' 로 나누면 class 가
    "OVL/M2M" 이 되어 표의 class 열이 조용히 틀립니다.
    """
    row = _recipe_row(
        _compare(eqp_ids=("EQ-A",), trend_rows=[],
                 recipe_rows=[("EQ-A", "OVL/M2M/REV2", 1, 50)]),
        "OVL/M2M/REV2",
    )
    assert row["class_name"] == "OVL"
    assert row["recipe_name"] == "M2M/REV2"


def test_compare_trends_zero_fill_every_day_and_drop_out_of_range_rows():
    """트렌드 x축은 조회 기간의 모든 날이고, 범위 밖 행은 버립니다.

    조용한 날을 건너뛰면 선택 장비들의 x축이 서로 달라져 겹쳐 그릴 수
    없습니다. 그리고 EQ-IDLE 처럼 측정이 하나도 없는 장비도 계열을 가져야
    범례에서 사라지지 않습니다.
    """
    payload = _compare()
    assert [series["eqp_id"] for series in payload["trends"]] == list(REQUESTED)

    by_id = {series["eqp_id"]: series["points"] for series in payload["trends"]}
    for points in by_id.values():
        assert [point["date"] for point in points] == [
            "2026-08-01", "2026-08-02", "2026-08-03"
        ]

    # 2026-07-30 행(999 s)은 범위 밖이라 어느 날에도 더해지지 않습니다.
    assert by_id["EQ-A"] == [
        {"date": "2026-08-01", "total_meastime": 400, "exec_count": 4},
        {"date": "2026-08-02", "total_meastime": 300, "exec_count": 3},
        {"date": "2026-08-03", "total_meastime": 0, "exec_count": 0},
    ]
    assert all(
        point["total_meastime"] == 0 and point["exec_count"] == 0
        for point in by_id["EQ-IDLE"]
    )


def test_compare_dedupes_the_selection_and_keeps_the_first_position():
    """중복 eqp_id 는 열을 하나만 차지합니다.

    같은 장비를 두 열로 그리면 합계가 두 번 세어진 것처럼 읽히고, 열 수가
    사용자가 체크한 수와 달라집니다.
    """
    payload = _compare(eqp_ids=("EQ-B", "EQ-A", "EQ-B"))
    assert payload["eqp_ids"] == ["EQ-B", "EQ-A"]
    assert [series["eqp_id"] for series in payload["trends"]] == ["EQ-B", "EQ-A"]
    for row in payload["recipes"]:
        assert [cell["eqp_id"] for cell in row["cells"]] == ["EQ-B", "EQ-A"]


def test_compare_with_no_selection_still_echoes_the_scope():
    """선택이 비면 빈 응답이지만 조회 범위는 그대로 되돌려줍니다.

    프론트엔드가 응답만 보고 "어떤 조회의 결과인가"를 알 수 있어야, 늦게
    도착한 응답을 현재 필터와 대조해 버릴 수 있습니다.
    """
    payload = _compare(eqp_ids=())
    assert payload["eqp_ids"] == []
    assert payload["trends"] == []
    assert payload["recipes"] == []
    assert payload["tool_type"] == "cd-sem"
    assert payload["fab_names"] == [FAB]
    assert payload["start_date"] == COMPARE_START
    assert payload["end_date"] == COMPARE_END
