"""recipe 모집단·버킷 분류·주차 궤적에 대한 회귀 테스트.

이 파일이 지키는 핵심 불변식은 하나입니다 — **recipe_id 는 표면을 가로지르는
조인 키다.** 실물에서 planstep_r3 의 recipe_id 가 cdsem_idp_ver 의 full_name 과
같은 값이기 때문입니다 (docs/datatables/idp_ver.txt L55). 예전 mock 은 버킷 이름을
id 에 박아(``RCP-R000-ALL-000``) 이 불변식을 깼고, recipe-statistics 와
recipe-params 의 교집합이 0건이었습니다.
"""

import pytest

from back_dev_home.ebeam.cdsem.device_statistics.providers import office_example
from back_dev_home.ebeam.cdsem.device_statistics.providers.recipe_params import (
    get_recipe_params,
)
from back_dev_home.ebeam.cdsem.device_statistics.providers.recipe_population import (
    POOL_RANGE,
    bucket_members,
    build_population,
    ends_with_pure_cd,
    is_normal_step,
    is_sample_recipe,
    lot_trajectory,
)
from back_dev_home.ebeam.cdsem.device_statistics.providers.statistics import (
    DEFAULT_TREND_POINTS,
    get_weekly_trend_data,
)


LOTS = ["R000", "R001", "R002", "R003"]


@pytest.fixture(scope="module")
def trend():
    return get_weekly_trend_data(LOTS)


# ── 조인 키 ───────────────────────────────────────────────────────────────

def test_recipe_ids_join_between_statistics_and_params(trend):
    """이 파일의 존재 이유. 예전에는 교집합이 0건이었습니다."""
    latest = list(trend)[-1]
    stat_ids = {
        (r["lot_cd"], r["recipe_id"]) for r in trend[latest]["all_rcp_info"]
    }
    param_ids = {(r["lot_cd"], r["recipe_id"]) for r in get_recipe_params(LOTS)}

    assert stat_ids, "recipe-statistics 가 비어 있으면 이 검증이 무의미합니다"
    assert stat_ids == param_ids


def test_recipe_id_carries_no_bucket_suffix(trend):
    """접미사 없는 id — 실물이 그렇습니다(statistics.py 모듈 docstring)."""
    latest = list(trend)[-1]
    for row in trend[latest]["all_rcp_info"]:
        for marker in ("-ALL-", "-ONL-", "-MOT-"):
            assert marker not in row["recipe_id"], row["recipe_id"]


def test_only_normal_and_only_sample_ids_do_not_collide(trend):
    """예전 ``bucket[:3]`` 은 두 버킷을 똑같이 "ONL" 로 잘라 id 가 겹쳤습니다.

    이제 두 버킷은 같은 모집단의 부분집합이므로, 겹치는 id 는 **같은 recipe** 를
    가리켜야 합니다 — 서로 다른 데이터를 든 동명이인이면 안 됩니다.
    """
    latest = list(trend)[-1]
    normal = {r["recipe_id"]: r for r in trend[latest]["only_normal_rcp_info"]}
    sample = {r["recipe_id"]: r for r in trend[latest]["only_sample_rcp_info"]}

    for recipe_id in set(normal) & set(sample):
        assert normal[recipe_id] == sample[recipe_id]


# ── 버킷은 한 모집단 위의 필터 ────────────────────────────────────────────

@pytest.mark.parametrize("bucket", ["only_normal", "mother_normal", "only_sample"])
def test_buckets_are_subsets_of_all(trend, bucket):
    latest = list(trend)[-1]
    all_ids = {
        (r["lot_cd"], r["recipe_id"]) for r in trend[latest]["all_rcp_info"]
    }
    subset = {
        (r["lot_cd"], r["recipe_id"]) for r in trend[latest][f"{bucket}_rcp_info"]
    }
    assert subset <= all_ids


def test_bucket_membership_follows_the_documented_predicates():
    population = build_population("R000", DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    members = bucket_members(population)

    assert members["only_normal"] == [
        r for r in population if is_normal_step(r["oper_desc"])
    ]
    assert members["only_sample"] == [
        r for r in population if is_sample_recipe(r["recipe_id"])
    ]
    # mother_normal 은 skip 되지 않은 것만 — "Y" 는 skip 입니다.
    assert all(r["skip_yn"].strip().upper() != "Y" for r in members["mother_normal"])
    assert all(ends_with_pure_cd(r["oper_desc"]) for r in members["mother_normal"])


def test_bucket_hierarchy_matches_the_screen_ordering(trend):
    """all > only_normal > mother_normal > only_sample.

    비교 페이지의 막대 서열이라 뒤집히면 화면 인상이 바뀝니다.
    """
    latest = list(trend)[-1]
    sizes = {
        b: len([r for r in trend[latest][f"{b}_rcp_info"] if r["lot_cd"] == "R000"])
        for b in ("all", "only_normal", "mother_normal", "only_sample")
    }
    assert sizes["all"] > sizes["only_normal"] > sizes["mother_normal"] > sizes["only_sample"]


# ── office 어댑터와의 규칙 일치 (드리프트 방지) ───────────────────────────

CLASSIFICATION_EXAMPLES = [
    # (oper_desc, recipe_id)
    ("SNC2(CELL OPEN ETCH CLN CD)", "RCP-R000-001"),
    ("SNC2(CELL OPEN ETCH CLN CD(E))", "RCP-R000-002"),
    ("SNC2(CELL OPEN ETCH CLN CD(F))", "RCP-R000-003_S"),
    ("PLD3(GATE POLY ETCH)", "RCP-R000-004SE"),
    ("MTC1(METAL1 CMP CD)", "RCP-R000-005"),
    ("", ""),
    ("VIA1(VIA ETCH CLN CD)", "RCP-R000-006_s"),
]


@pytest.mark.parametrize("oper_desc,recipe_id", CLASSIFICATION_EXAMPLES)
def test_predicates_agree_with_the_office_adapter(oper_desc, recipe_id):
    """mock 과 office_example 이 같은 답을 내야 합니다.

    두 벌이 갈라지면 집에서 만든 화면이 사무실에서 다르게 나옵니다. office 쪽은
    복사본(office.py)이 되는 템플릿이라 한쪽만 고치기 쉬워, 예시 표로 함께 묶습니다.
    """
    assert is_normal_step(oper_desc) == office_example._is_normal_step(oper_desc)
    assert ends_with_pure_cd(oper_desc) == office_example._ends_with_pure_cd(oper_desc)
    assert is_sample_recipe(recipe_id) == office_example._is_sample_recipe(recipe_id)


def test_non_sample_ids_never_match_the_sample_suffix_by_accident():
    """비-Sample id 는 숫자로 끝나야 합니다.

    office 쪽 주석이 경고하듯 ``SE`` 를 이름 끝에서 찾으면 PHASE/BASE/SET 같은
    평범한 단어가 전부 Sample 이 됩니다. mock 이 그 함정을 우연히 밟지 않는지 봅니다.
    """
    population = build_population("R000", DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    for identity in population:
        recipe_id = identity["recipe_id"]
        if not is_sample_recipe(recipe_id):
            assert recipe_id[-1].isdigit(), recipe_id


# ── 주차 궤적 ────────────────────────────────────────────────────────────

def test_recipe_ids_persist_across_weeks(trend):
    """3주 전에 있던 recipe 가 이번 주에도 같은 id 로 남아야 합니다.

    주차마다 새로 뽑으면 "트렌드" 가 아니라 매주 다른 표본입니다. 이 안정성이
    docs/datatables/device_statistics_weekly_trend.txt 가 말하는 "같은 계획이
    자라거나 줄어든 모습" 입니다.
    """
    dates = list(trend)
    first = {r["recipe_id"] for r in trend[dates[0]]["all_rcp_info"] if r["lot_cd"] == "R000"}
    last = {r["recipe_id"] for r in trend[dates[-1]]["all_rcp_info"] if r["lot_cd"] == "R000"}

    overlap = first & last
    assert len(overlap) >= 0.5 * min(len(first), len(last)), (
        f"주차 간 recipe 연속성이 없습니다: {len(overlap)} / {len(first)}"
    )


def test_growing_and_shrinking_lots_actually_move(trend):
    """궤적이 화면에서 방향으로 읽혀야 합니다 — 처음과 끝이 뚜렷이 달라야 합니다."""
    dates = list(trend)

    for lot in LOTS:
        series = [
            next(r for r in trend[d]["all_summary"] if r["lot_cd"] == lot)["para_all"]
            for d in dates
        ]
        traj = lot_trajectory(lot)
        change = (series[-1] - series[0]) / series[0]

        if traj == "growing":
            assert change > 0.25, f"{lot} growing 인데 {change:.0%} 만 변했습니다"
        elif traj == "shrinking":
            assert change < -0.20, f"{lot} shrinking 인데 {change:.0%} 만 변했습니다"
        elif traj == "ramp":
            # 중반 계단 — 전반부 평균보다 후반부 평균이 뚜렷이 큽니다.
            half = len(series) // 2
            before = sum(series[:half]) / half
            after = sum(series[half:]) / (len(series) - half)
            assert after > before * 1.3, f"{lot} ramp 의 계단이 보이지 않습니다"


def test_weekly_series_is_not_a_straight_line(trend):
    """자로 그은 듯 매끈하면 합성 티가 납니다 — 주차 흔들림이 살아 있는지 봅니다."""
    dates = list(trend)
    series = [
        next(r for r in trend[d]["all_summary"] if r["lot_cd"] == "R000")["para_all"]
        for d in dates
    ]
    deltas = [b - a for a, b in zip(series, series[1:])]
    assert len(set(deltas)) > 1, "주차 증분이 전부 같습니다 (흔들림 없음)"


def test_recipe_count_stays_inside_the_confirmed_domain(trend):
    """device 당 recipe 100~200 (D22). 궤적 배율이 이 창을 벗어나면 안 됩니다."""
    for date_key in trend:
        for row in trend[date_key]["all_summary"]:
            assert 100 <= row["total_recipe"] <= 200, (
                f"{row['lot_cd']} @ {date_key}: {row['total_recipe']}"
            )


def test_pool_range_cannot_breach_the_domain():
    """POOL_RANGE 를 손대면 도메인이 조용히 깨지므로 상수 자체를 묶어 둡니다."""
    lo, hi = POOL_RANGE
    assert round(lo * 0.58) >= 100, "궤적 최저 배율에서 100 아래로 내려갑니다"
    assert hi <= 200, "배율 1.0 에서 200 을 넘습니다"


# ── recipe_class 일관성 ───────────────────────────────────────────────────

def test_recipe_class_is_derived_from_the_recipe_name():
    """only_sample 버킷과 recipe_class 가 같은 규칙을 써야 합니다.

    예전에는 recipe_class 를 따로 굴려서, 같은 recipe 가 only_sample 버킷에는
    있는데 recipe_class 는 Main 인 모순이 가능했습니다.
    """
    for row in get_recipe_params(["R000"]):
        expected = "Sample" if is_sample_recipe(row["recipe_id"]) else "Main"
        assert row["recipe_class"] == expected, row["recipe_id"]
