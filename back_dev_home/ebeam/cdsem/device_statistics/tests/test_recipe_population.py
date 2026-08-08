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
    _JUDGE_EXEMPT_SUFFIXES,
    bucket_members,
    build_population,
    ends_with_pure_cd,
    is_exempt_job,
    is_normal_bucket_step,
    is_sample_recipe,
    lot_trajectory,
    mother_para_all,
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


# ── 이름 형태 ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lot_cd", LOTS)
def test_recipe_id_has_the_office_slash_shape(lot_cd):
    """실물 full_name 은 "class_name/recipe_name" 입니다.

    docs/datatables/recipe_name_list.txt L56 (user-confirmed 2026-07-29).
    """
    population = build_population(lot_cd, DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    assert population

    for row in population:
        class_name, sep, recipe_name = row["recipe_id"].partition("/")
        assert sep == "/", row["recipe_id"]
        assert class_name and recipe_name, row["recipe_id"]


@pytest.mark.parametrize("lot_cd", LOTS)
def test_recipe_name_order_differs_from_process_order(lot_cd):
    """이름순과 공정순은 **다른 순서여야** 합니다 — 실물에서 독립인 두 축이므로.

    lot 상세 팝업의 정렬 토글("공정순" / "recipe 이름")이 집에서 눈에 보이는지를
    지키는 테스트입니다. 예전 ``RCP-{lot}-{idx:03d}`` 는 이름의 사전순이 곧
    oper_seq 순이라 두 정렬이 **같은 표를 두 번** 냈고, 토글을 눌러도 화면이
    그대로였습니다. 사무실에서는 recipe 이름을 MMDM 이 부여하므로 공정 순서와
    무관합니다 — mock 도 그 독립성을 재현해야 두 정렬을 가르는 코드 경로가
    집에서 실행됩니다.
    """
    population = build_population(lot_cd, DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    assert len(population) > 1

    by_oper = [
        r["recipe_id"] for r in
        sorted(population, key=lambda r: (r["oper_seq"], r["samp_seq"], r["recipe_id"]))
    ]
    by_name = sorted(r["recipe_id"] for r in population)

    assert by_oper != by_name


@pytest.mark.parametrize("lot_cd", LOTS)
def test_recipe_id_is_unique_within_a_lot(lot_cd):
    """조인 키이므로 lot 안에서 유일해야 합니다 — 겹치면 파라미터가 섞입니다."""
    population = build_population(lot_cd, DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    recipe_ids = [r["recipe_id"] for r in population]

    assert len(recipe_ids) == len(set(recipe_ids))


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
        r for r in population
        if is_normal_bucket_step(r["oper_desc"], r["skip_yn"])
    ]
    assert members["only_sample"] == [
        r for r in population if is_sample_recipe(r["recipe_id"])
    ]
    # only_normal 은 skip 되지 않은 것만 — "Y" 는 skip 입니다 — 그리고 스텝명 끝이
    # 순수한 CD 인 것만입니다("CD(E)" 인 추가계측은 빠집니다).
    assert all(r["skip_yn"].strip().upper() != "Y" for r in members["only_normal"])
    assert all(ends_with_pure_cd(r["oper_desc"]) for r in members["only_normal"])


def test_mother_normal_shares_the_step_filter_and_narrows_by_mother():
    """mother_normal 은 only_normal 의 **부분집합**이며, 갈리는 축은 mother 뿐입니다.

    스텝을 더 좁히는 버킷이 아니라 한 단계 아래(파라미터)로 들어가는 버킷입니다
    (user-confirmed 2026-08-04). 두 조건이 다시 갈라지면 여기서 먼저 깨집니다.
    """
    population = build_population("R000", DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    members = bucket_members(population)

    normal_ids = {r["recipe_id"] for r in members["only_normal"]}
    mother_ids = {r["recipe_id"] for r in members["mother_normal"]}

    assert mother_ids <= normal_ids
    assert members["mother_normal"] == [
        r for r in members["only_normal"] if mother_para_all(r) > 0
    ]
    # 양쪽 경로가 집에서 실제로 실행되는지 — mother 없는 recipe 가 하나도 없으면
    # "recipe 를 좁힌다" 는 규칙이 한 번도 검증되지 않습니다.
    assert mother_ids, "mother 를 가진 recipe 가 하나도 없습니다"
    assert normal_ids - mother_ids, "mother 없는 recipe 가 하나도 없습니다"


def test_mother_para_never_exceeds_its_bin():
    """``mother_para_N <= para_N``. 넘으면 화면에서 100% 를 넘는 막대가 됩니다."""
    population = build_population("R000", DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    for identity in population:
        for key in ("para_16", "para_13", "para_9", "para_5"):
            assert identity[f"mother_{key}"] <= identity[key], identity["recipe_id"]


def test_mother_normal_summary_counts_only_mother_parameters(trend):
    """이 버킷의 para_* 는 mother 기준이라 only_normal 보다 작아야 합니다."""
    latest = list(trend)[-1]
    normal = next(r for r in trend[latest]["only_normal_summary"] if r["lot_cd"] == "R000")
    mother = next(r for r in trend[latest]["mother_normal_summary"] if r["lot_cd"] == "R000")

    assert 0 < mother["para_all"] < normal["para_all"]


def test_mother_flag_agrees_between_statistics_and_recipe_params():
    """두 표면이 "이 recipe 에 mother 가 있는가" 에 같은 답을 해야 합니다.

    요약의 para_* 와 health 가 읽는 parameters 는 서로 다른 모듈이 각자 난수로
    만듭니다. 여기가 갈라지면 mother_normal 버킷에는 있는데 mother 파라가 하나도
    없는 recipe 가 생기고, 프론트엔드의 health 가 조용히 0/0 으로 떨어집니다 —
    오류가 아니라 "판정 없음" 으로만 보이므로 발견이 아주 늦습니다.
    """
    population = build_population("R000", DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    has_mother = {r["recipe_id"]: mother_para_all(r) > 0 for r in population}

    for row in get_recipe_params(["R000"]):
        flagged = any(p["mother"] for p in row["parameters"])
        assert flagged == has_mother[row["recipe_id"]], row["recipe_id"]


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
    # (oper_desc, skip_yn, recipe_id)
    ("SNC2(CELL OPEN ETCH CLN CD)", "N", "RCP-R000-001"),
    ("SNC2(CELL OPEN ETCH CLN CD)", "Y", "RCP-R000-001"),   # skip -> 버킷 밖
    ("SNC2(CELL OPEN ETCH CLN CD)", "", "RCP-R000-001"),    # 빈 값 -> 측정 중
    ("SNC2(CELL OPEN ETCH CLN CD(E))", "N", "RCP-R000-002"),
    ("SNC2(CELL OPEN ETCH CLN CD(F))", "N", "RCP-R000-003_S"),
    # 괄호 꼬리가 단어인 경우 (user-confirmed 2026-08-05). 규칙이 꼬리의 길이를
    # 가정하지 않는지 — 한 글자 예시만으로는 드러나지 않습니다.
    ("SNC2(CELL OPEN ETCH CLN CD(BENDING))", "N", "RCP-R000-007"),
    ("PLD3(GATE POLY ETCH)", "N", "RCP-R000-004SE"),
    ("MTC1(METAL1 CMP CD)", "N", "RCP-R000-005"),
    ("", "", ""),
    ("VIA1(VIA ETCH CLN CD)", "N", "RCP-R000-006_s"),
    ("MTC1(METAL1 CMP CD)", "N", "RCP-R000-008_HALF"),
]


def test_paren_cd_steps_are_excluded_from_only_normal_whatever_the_tail():
    """"CD(...)" 꼬리는 길이와 무관하게 추가계측입니다.

    only_normal 이 답하는 질문이 "정규 CD 측정 스텝인가" 이므로, 꼬리가 한
    글자든(E/F) 단어든(BENDING) 똑같이 빠져야 합니다.
    """
    assert ends_with_pure_cd("SNC2(CELL OPEN ETCH CLN CD)") is True
    for tail in ("E", "F", "BENDING", "REWORK"):
        oper_desc = f"SNC2(CELL OPEN ETCH CLN CD({tail}))"
        assert ends_with_pure_cd(oper_desc) is False, oper_desc


@pytest.mark.parametrize("oper_desc,skip_yn,recipe_id", CLASSIFICATION_EXAMPLES)
def test_predicates_agree_with_the_office_adapter(oper_desc, skip_yn, recipe_id):
    """mock 과 office_example 이 같은 답을 내야 합니다.

    두 벌이 갈라지면 집에서 만든 화면이 사무실에서 다르게 나옵니다. office 쪽은
    복사본(office.py)이 되는 템플릿이라 한쪽만 고치기 쉬워, 예시 표로 함께 묶습니다.
    """
    assert ends_with_pure_cd(oper_desc) == office_example._ends_with_pure_cd(oper_desc)
    assert is_sample_recipe(recipe_id) == office_example._is_sample_recipe(recipe_id)
    assert (
        is_normal_bucket_step(oper_desc, skip_yn)
        == office_example._is_normal_bucket_step(oper_desc, skip_yn)
    )


def test_non_sample_ids_never_match_the_sample_suffix_by_accident():
    """비-Sample id 는 숫자 또는 판정 외 job 접미사로 끝나야 합니다.

    office 쪽 주석이 경고하듯 ``SE`` 를 이름 끝에서 찾으면 PHASE/BASE/SET 같은
    평범한 단어가 전부 Sample 이 됩니다. mock 이 그 함정을 우연히 밟지 않는지 봅니다.
    특수 job 접미사(_WCDU/_FCDU/_FULL user-confirmed 2026-08-04,
    _HALF/_BCDU/_MTX user-confirmed 2026-08-05)는 실물 이름의 일부이며
    ``(_S|SE)$`` 와 겹치지 않습니다.
    """
    population = build_population("R000", DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    for identity in population:
        recipe_id = identity["recipe_id"]
        if not is_sample_recipe(recipe_id):
            assert (
                recipe_id[-1].isdigit()
                or recipe_id.endswith(_JUDGE_EXEMPT_SUFFIXES)
            ), recipe_id


def test_judge_exempt_suffixes_are_present_in_the_pool():
    """특수 측정 job 이름이 실제로 생성되는지 봅니다.

    없으면 프론트엔드의 두 exempt 경로(판정 lotHealth.isExemptJob, outlier
    outlierDetect)가 집에서 한 번도 실행되지 않습니다 — mock 이 office 를
    대역한다는 원칙(CLAUDE.md)입니다.
    """
    expected = set(_JUDGE_EXEMPT_SUFFIXES)
    population = build_population("R000", DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    present = {
        suffix
        for suffix in expected
        for r in population
        if r["recipe_id"].endswith(suffix)
    }
    assert present == expected, present


def test_is_exempt_job_covers_every_name_the_pool_generates():
    """판정 술어가 생성된 이름을 빠짐없이 잡는지 봅니다.

    ``recipe_params`` 가 측정 배율을 먹일 대상을 이 술어로 고르므로, 둘이
    갈라지면 *이름은 _HALF 인데 측정 규모는 정상* 인 recipe 가 생깁니다.
    """
    population = build_population("R000", DEFAULT_TREND_POINTS - 1, DEFAULT_TREND_POINTS)
    for identity in population:
        recipe_id = identity["recipe_id"]
        expected = recipe_id.endswith(_JUDGE_EXEMPT_SUFFIXES)
        assert is_exempt_job(recipe_id) is expected, recipe_id


def test_is_exempt_job_is_a_pattern_not_the_generation_list():
    """표본에 없는 CDU 이름도 잡아야 합니다.

    이것이 이 규칙의 핵심입니다 — _WCDU/_FCDU 만 열거해 두었더니 실물의 _BCDU
    가 그대로 분석에 섞여 들었습니다 (user-confirmed 2026-08-05). 앞 글자는 어떤
    map 을 재는지를 뜻할 뿐이라 종류가 늘 수 있으므로, 판정은 목록이 아니라
    "_*CDU" 패턴이어야 합니다.
    """
    for name in ("RCP-R000-001_BCDU", "RCP-R000-001_XCDU", "RCP-R000-001_CDU"):
        assert is_exempt_job(name), name

    # 끝에 고정입니다 — 이름 한복판의 CDU 나 밑줄 없는 CDU 는 정상 recipe 입니다.
    for name in ("RCP_WCDU-R000-001", "RCP-R000-001CDU", "RCP-R000-001"):
        assert not is_exempt_job(name), name


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
