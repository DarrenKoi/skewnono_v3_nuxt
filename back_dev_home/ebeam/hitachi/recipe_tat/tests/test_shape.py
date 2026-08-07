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

from back_dev_home.ebeam.hitachi.recipe_tat.contracts import TAT_INDEX_MIN_SAMPLE
from back_dev_home.ebeam.hitachi.recipe_tat.providers._shape import (
    build_equipments_payload,
    window_seconds,
)


MODEL = "CG6300"
FAB = "R3"
START, END = "2026-07-25", "2026-08-08"


def _payload(grid):
    return build_equipments_payload("cd-sem", (FAB,), START, END, grid)


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


def test_window_seconds_includes_both_endpoints_and_refuses_bad_ranges():
    assert window_seconds("2026-08-01", "2026-08-01") == 86400
    assert window_seconds("2026-07-25", "2026-08-08") == 15 * 86400
    assert window_seconds("2026-08-08", "2026-07-25") == 0    # 뒤집힌 범위
    assert window_seconds(None, "2026-08-08") == 0
