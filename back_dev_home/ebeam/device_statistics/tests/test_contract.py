"""Contract gate for device_statistics. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/device_statistics
Office: SKEWNONO_DEVICE_STATISTICS_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/device_statistics

providers/office_example.py is still a stub, so the office command above fails
with its NotImplementedError rather than a contract violation — that is the
adapter being unwritten, not this gate being wrong.

This is the one feature of the seven that legitimately keys on `fac_id` rather
than `fab_name` (MIGRATION.md), and the join across r3_device_grp /
device_desc / recipe_params has to hold under either provider — that is
asserted unfenced. What is NOT provider-independent is that the tables have
ROWS at all: the mock fabricates them from a fixed RNG seed, while the office
source can return nothing for a lot list. Those assumptions are fenced behind
get_data_provider("device_statistics") == "mock", and the lookups that need a
sample row skip instead of failing when the active provider has none.
"""

import pytest

from back_dev_home._core.contract_check import assert_matches
from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.device_statistics import data
from back_dev_home.ebeam.device_statistics.para_buckets import (
    has_non_measurement_name,
)
from back_dev_home.ebeam.device_statistics.contracts import (
    DeviceDescRow,
    MeasActivityRow,
    R3DeviceGrpRow,
    RecipeParamsRow,
    RuleVersion,
    TrendBucket,
    step_key,
)
from back_dev_home.ebeam.device_statistics.providers.recipe_population import (
    is_exempt_job,
)


def _is_mock() -> bool:
    return get_data_provider("device_statistics") == "mock"


def _sample_lot_cd() -> str:
    """A real lot code, derived from live data rather than hardcoded.

    The mock's r3_device_grp is generated from a fixed RNG seed and always has
    rows; an office source can return none, and there is then no lot_cd to key
    the recipe/trend lookups off.
    """
    rows = data.get_r3_device_grp()
    if not rows:
        pytest.skip("active provider returned no r3_device_grp rows")
    return rows[0]["lot_cd"]


def test_r3_device_grp_matches_contract():
    rows = data.get_r3_device_grp()
    assert_matches(rows, list[R3DeviceGrpRow])
    if _is_mock():
        # Fixed RNG seed (20260426) — an empty table means the generator broke.
        assert rows, "mock r3_device_grp must not be empty"


def test_device_desc_matches_contract():
    rows = data.get_device_desc()
    assert_matches(rows, list[DeviceDescRow])
    if _is_mock():
        # Same fabricated source as r3_device_grp above.
        assert rows, "mock device_desc must not be empty"


def test_meas_activity_matches_contract():
    rows = data.get_meas_activity("R3")
    assert_matches(rows, list[MeasActivityRow])

    # 계약이 정렬(meas_count 내림차순)을 약속합니다 — 화면의 "측정 상위 N" 이
    # 앞에서 N 개를 자르는 근거이므로, 순서가 깨지면 필터가 조용히 틀립니다.
    counts = [row["meas_count"] for row in rows]
    assert counts == sorted(counts, reverse=True), "meas-activity must be sorted desc"
    assert all(count >= 0 for count in counts)

    if _is_mock():
        assert rows, "mock meas_activity must not be empty for R3"
        # mock 순위는 카탈로그의 lot 만 다룹니다. office 는 카탈로그에 없는
        # lot_cd 가 순위에 있을 수 있어(hist 에만 존재) 이 포함관계를
        # 강제하지 않습니다 — 화면이 교집합을 취합니다.
        catalog = {row["lot_cd"] for row in data.get_r3_device_grp()}
        assert {row["lot_cd"] for row in rows} <= catalog


def test_meas_activity_unknown_fab_is_empty():
    # fab 축이 없는 순위는 의미가 없고, 알 수 없는 fab 이 다른 fab 의 순위로
    # 해석되면 안 됩니다. 어느 provider 든 빈 배열이 정답입니다.
    assert data.get_meas_activity("does-not-exist") == []


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_meas_activity_blank_fab_is_empty(blank):
    # 빈 fab 도 마찬가지입니다. mock 에는 이 가드가 없어 get_device_desc([""])
    # 의 빈-토큰 경로로 떨어졌고, M-fab 전체 행이 하나의 순위로 돌아왔습니다 —
    # office 는 같은 입력에 빈 배열을 주므로, 프런트가 빈 fab 을 보내는 버그가
    # 집에서는 fab 을 가로지르는 순위로, 사무실에서는 빈 화면으로 보였습니다.
    assert data.get_meas_activity(blank) == []


def test_recipe_params_matches_contract():
    # Narrowed to a single lot_cd — an unfiltered call fans out over every
    # known lot (thousands) and is not a real usage pattern; the frontend
    # always joins a user-selected lot list before calling. See MIGRATION.md.
    lot_cd = _sample_lot_cd()
    rows = data.get_recipe_params([lot_cd])
    assert_matches(rows, list[RecipeParamsRow])

    # The lot_cd filter is the join key the whole feature is built on
    # (MIGRATION.md: fac_id/lot_cd must stay joinable across all three tables).
    # A row for a lot nobody asked for would land in the wrong device panel.
    for row in rows:
        assert row["lot_cd"] == lot_cd
        assert all(param["point_count"] >= 0 for param in row["parameters"])

    # 이 표면은 **recipe 단위**입니다 — 원천 cdsem_idp_ver 이 full_name 하나에
    # 파라미터 한 벌만 들고 있기 때문입니다. 프론트엔드가 recipe_id 로 Map 을
    # 만들어 조인하므로(utils/lotParamExport.ts), 두 행이 오면 뒤엣것이 조용히
    # 앞엣것을 덮습니다. 어느 provider 가 답하든 지켜야 하는 계약입니다.
    keys = [(row["lot_cd"], row["recipe_id"]) for row in rows]
    assert len(keys) == len(set(keys)), "recipe_id 가 lot 안에서 중복된 행이 있습니다"

    if _is_mock():
        # Every mock lot has fabricated recipes behind it; a real lot can have
        # no recipe rows yet.
        assert rows, "mock recipe_params must not be empty for a known lot"


def test_parameter_order_is_the_recipe_order_not_alphabetical():
    """``parameters`` 순서는 recipe 가 적어 둔 순서 그대로여야 합니다.

    순서 자체가 정보입니다 — WAFER 계열이 맨 앞에 오는 것이 관례이고, drill 을
    펼친 엔지니어가 위에서부터 읽습니다 (user-confirmed 2026-08-05). 이름순으로
    정렬하면 "WAFER" 가 알파벳상 거의 끝이라 **가장 중요한 파라미터가 목록 맨
    아래로** 밀립니다. office 어댑터가 실제로 그랬습니다.

    두 표면 모두에 걸리는 계약이라 여기서 지킵니다 — mock 은 WAFER 를 먼저
    만들고, office 는 _source dict 의 삽입 순서를 그대로 냅니다.
    """
    rows = data.get_recipe_params([_sample_lot_cd()])
    if not rows:
        pytest.skip("no recipe rows for this lot")

    for row in rows:
        names = [param["name"] for param in row["parameters"]]
        if len(names) < 2:
            continue
        assert names != sorted(names) or len(set(names)) == 1, (
            f"{row['recipe_id']} 의 파라미터가 이름순입니다 — 원본 순서가 "
            f"정렬로 덮였을 수 있습니다: {names}"
        )
        if _is_mock():
            # mock 은 WAFER → LEVEL → EDGE → OTHER 순으로 만듭니다. 단 준비용
            # 파라미터(Dummy·Align)가 있으면 그것이 **맨 앞**입니다
            # (user-confirmed 2026-08-10) — 정렬은 측정보다 먼저 하니까요.
            # 그래서 확인할 것은 "첫 칸이 WAFER" 가 아니라 "첫 **측정**
            # 파라미터가 WAFER" 입니다.
            measured = [
                name for name in names if not has_non_measurement_name(name)
            ]
            assert measured and measured[0].startswith("WAFER"), names


def test_region_groups_have_at_most_one_mother_and_are_contiguous():
    """``region`` 은 image definition 묶음(SEQ 그룹)이고 mother 는 그 머리입니다.

    프론트엔드의 계측 룰 판정이 이 구조에 그대로 기댑니다 — son 을 자기 이름의
    타입 cap 이 아니라 **그 묶음 mother 의 cap** 으로 잽니다
    (utils/ruleEngine.groupCaps, user-confirmed 2026-08-18). 그래서 지켜야 할 것이
    둘입니다.

      묶음마다 mother 는 최대 하나   둘이면 어느 cap 을 물려줄지가 순서에 달리고,
                                     그 차이는 예외가 아니라 "위반 수가 조금 다르다"
                                     로만 나타납니다.
      묶음은 연속 구간               파라미터 순서가 곧 측정 순서(SEQ 순서)입니다.
                                     흩어져 있으면 화면의 "1/8, 2/8 …" 이 성립하지
                                     않습니다.

    어느 provider 가 답하든 걸리는 계약입니다.
    """
    rows = data.get_recipe_params([_sample_lot_cd()])
    if not rows:
        pytest.skip("no recipe rows for this lot")

    for row in rows:
        seen: list[int] = []
        mothers: dict[int, int] = {}
        for param in row["parameters"]:
            region = param["region"]
            if region is None:
                # 묶을 근거가 없는 파라미터(비측정 파라미터, 또는 원천에서 Region
                # 을 읽지 못한 문서)입니다 — 프론트엔드가 자기 cap 으로 판정합니다.
                continue
            if not seen or seen[-1] != region:
                assert region not in seen, (
                    f"{row['recipe_id']} 의 region {region} 이 끊겼다 다시 나옵니다 "
                    f"— 묶음은 연속 구간이어야 합니다"
                )
                seen.append(region)
            if param["mother"]:
                mothers[region] = mothers.get(region, 0) + 1
                assert mothers[region] == 1, (
                    f"{row['recipe_id']} 의 region {region} 에 mother 가 둘 이상입니다"
                )

        if _is_mock():
            # mock 은 묶음의 **머리**를 mother 로 켭니다. mother 가 하나라도 있는
            # recipe 라면 모든 묶음에 머리가 있어야 합니다 — 일부 묶음만 머리가
            # 없으면 그 묶음의 son 들이 조용히 예전 판정(자기 cap)으로 돌아갑니다.
            if mothers:
                assert set(mothers) == set(seen), (
                    f"{row['recipe_id']}: mother 없는 묶음이 섞였습니다 "
                    f"{sorted(set(seen) - set(mothers))}"
                )


def test_sons_never_out_measure_their_region_head():
    """son 은 머리의 image 안에서 재므로 그보다 많이 잴 수 없습니다.

    이 성질이 깨지면 mock 이 **집에서만 존재하는 위반**을 만듭니다 — 물려받은
    cap 을 son 이 넘어 위반으로 잡히는데, 실물에서는 mother 가 이미 자기 cap 을
    넘었을 때나 일어나는 일입니다.

    OFFICE-VERIFY 인 추론이므로 mock 에만 겁니다 (근거는 recipe_params 의
    ``_assign_regions`` docstring). office 어댑터는 원천 값을 그대로 냅니다 —
    사무실 데이터가 이 추론을 깨면 그 사실 자체가 알아야 할 정보입니다.
    """
    if not _is_mock():
        pytest.skip("office 어댑터는 원천 point 수를 그대로 냅니다")

    rows = data.get_recipe_params([_sample_lot_cd()])
    assert rows
    for row in rows:
        head_points: dict[int, int] = {}
        for param in row["parameters"]:
            region = param["region"]
            if region is None:
                continue
            if region not in head_points:
                head_points[region] = param["point_count"]
                continue
            assert param["point_count"] <= head_points[region], (
                f"{row['recipe_id']} 의 {param['name']} 이 자기 묶음의 머리보다 "
                f"많이 쟀습니다 ({param['point_count']} > {head_points[region]})"
            )


def test_exempt_jobs_measure_at_a_different_scale():
    """특수 측정 job(_WCDU/_FCDU/_FULL/_HALF)은 정상 recipe 보다 훨씬 크게 잽니다.

    프론트엔드가 이 job 들을 outlier 중앙값 기준선에서 빼는 이유가 바로 이
    규모 차이입니다 (outlierDetect.ts). mock 이 같은 규모로 만들면 그 회귀가
    집에서 조용히 통과합니다.
    """
    if not _is_mock():
        pytest.skip("office 값은 우리가 정하지 않습니다")

    rows = data.get_recipe_params([_sample_lot_cd()])
    exempt_points: list[int] = []
    normal_points: list[int] = []
    for row in rows:
        target = (
            exempt_points
            if is_exempt_job(row["recipe_id"])
            else normal_points
        )
        target.extend(param["point_count"] for param in row["parameters"])

    assert exempt_points, "mock 이 특수 job 을 하나도 만들지 않았습니다"
    assert normal_points
    assert max(exempt_points) > max(normal_points), (
        "특수 job 이 정상 recipe 와 같은 규모면 outlier 제외 규칙이 무의미합니다"
    )


def test_dummy_and_align_keep_their_real_mixed_case_spelling():
    """Dummy·Align 은 **대문자가 아닙니다** (user-confirmed 2026-08-05).

    실물 파라미터 이름은 대체로 전부 대문자인데 이 둘만 그렇지 않습니다. 걸러
    내는 쪽(outlierDetect.isOutlierExemptParam, 룰의 name_override)은 양쪽 다
    대소문자를 무시하므로 어느 표기든 동작하지만, **mock 이 대문자로 만들면
    그 대소문자 무시 경로가 집에서 한 번도 실행되지 않습니다** — 규칙을
    `name == "DUMMY"` 로 좁히는 회귀가 집에서는 통과하고 사무실에서만 새어
    나갑니다.

    그래서 여기서 보는 것은 "존재" 가 아니라 **표기** 입니다.
    """
    if not _is_mock():
        pytest.skip("office 이름 표기는 우리가 정하지 않습니다")

    names = {
        param["name"]
        for row in data.get_recipe_params([_sample_lot_cd()])
        for param in row["parameters"]
    }

    for spelling in ("Dummy", "Align"):
        assert spelling in names, f"mock 이 {spelling} 을 만들지 않았습니다"
        assert spelling.upper() not in names, (
            f"{spelling.upper()} 는 실물 표기가 아닙니다 — 대문자로 만들면 "
            "대소문자 무시 경로가 집에서 검증되지 않습니다"
        )

    # 나머지 파라미터가 전부 대문자라는 것이 위 두 이름을 특별하게 만듭니다.
    others = names - {"Dummy", "Align"}
    assert others and all(name == name.upper() for name in others), sorted(others)


def test_weekly_trend_data_matches_contract():
    # Same narrowing rationale as recipe_params above.
    lot_cd = _sample_lot_cd()
    trend = data.get_weekly_trend_data([lot_cd])
    assert_matches(trend, dict[str, TrendBucket])

    # Whatever the source, every summary row in a bucket must belong to the
    # lot that was asked for — the route keys the chart series off it.
    for bucket in trend.values():
        for summary in bucket["all_summary"]:
            assert summary["lot_cd"] == lot_cd
            assert summary["avail_recipe"] <= summary["total_recipe"]

    # 행 1건 = 스텝 1건. 화면이 이 행들을 목록으로 그리며 `contracts.step_key` 를
    # ``v-for`` 의 :key 로 쓰므로(프론트엔드 utils/recipeStepSort.recipeStepKey),
    # 같은 lot 안에 같은 스텝이 두 번 오면 Vue 가 카드를 접어 스텝이 사라집니다.
    # recipe_id 로는 검사하지 않습니다 — 그것은 여러 스텝이 공유하는 조인 키입니다.
    for bucket in trend.values():
        for name, rows in bucket.items():
            if not name.endswith("_rcp_info"):
                continue
            steps = [(row["lot_cd"], *step_key(row)) for row in rows]
            assert len(steps) == len(set(steps)), f"{name} 에 중복된 스텝이 있습니다"

    if _is_mock():
        # Byte-identical per (lot_cd, date_index) from the seeded generator, so
        # an empty trend means it broke. An office lot can have no history.
        assert trend, "mock weekly trend must not be empty for a known lot"


def test_rules_matches_contract():
    # Provider-independent: BOTH providers serve the same in-code seed
    # (providers/rules.py) — in-app rule editing was dropped 2026-08-04, so
    # there is no "published elsewhere" state and R3 must always resolve.
    rules = data.get_rules("R3")
    assert rules is not None, "the R3 rule seed must resolve under any provider"

    assert_matches(rules, RuleVersion)
    assert rules["thresholds"]["yellow_at"] <= rules["thresholds"]["red_at"]
    # ruleEngine.selectorMatches does first-match selection over `cells`, so a
    # duplicated cell id makes which rule wins depend on load order.
    ids = [cell["id"] for cell in rules["cells"]]
    assert len(set(ids)) == len(ids), "rule cell ids must be unique"


def test_rules_unknown_fab_returns_none():
    # Provider-independent: the route turns None into a 404, so an unknown fab
    # must never resolve to some other fab's caps.
    assert data.get_rules("does-not-exist") is None


def test_sample_cells_exempt_the_non_measurement_parameters():
    """Sample 셀은 DUMMY·ALIGN 을 판정에서 면제해야 합니다.

    (DUMMY user-confirmed 2026-08-05, ALIGN 2026-08-10.)

    Sample 셀의 ``_other`` 는 0 이라, 면제가 없으면 이 두 파라미터가 point 1 만
    있어도 **항상 위반**입니다. 그 위반은 recipe 를 고쳐서 없앨 수 있는 종류가
    아니라, 고칠 수 있는 진짜 위반을 목록에서 밀어냅니다 — DUMMY 는 재는 대상이
    아니라 자리 표시이고, Align 은 측정이 아니라 측정을 위한 준비입니다.

    두 이름을 한 테스트에서 함께 보는 이유가 있습니다. 프론트엔드는 이미 둘을
    한 벌로 다루는데(``outlierDetect.NON_MEASUREMENT_PARAMS``,
    ``para_buckets.measurement_parameters``) 룰만 DUMMY 하나로 남아 있었고, 그
    비대칭이 눈에 띄지 않은 채 오래갔습니다. 목록으로 묶어 두면 다음에 한쪽만
    늘어나는 것이 실패로 나타납니다.

    ``cap: None`` 이 프론트엔드 capFor 의 "상한 없음 = 절대 위반 아님" 입니다
    (D9). 값이 0 이면 정반대 뜻이 되므로 None 인 것을 명시적으로 봅니다.
    """
    rules = data.get_rules("R3")
    assert rules is not None

    sample_cells = [
        cell for cell in rules["cells"]
        if cell["selector"].get("recipe_class") == "Sample"
    ]
    assert sample_cells, "R3 에 Sample 셀이 있어야 이 규칙이 의미를 갖습니다"

    for cell in sample_cells:
        assert cell["caps"]["_other"] == 0, cell["id"]
        for name in ("DUMMY", "ALIGN"):
            exempt = [
                ov for ov in cell["name_overrides"]
                if any(p.upper() == name for p in ov["patterns"])
            ]
            assert len(exempt) == 1, f"{cell['id']} 에 {name} 면제가 없습니다"
            assert exempt[0]["cap"] is None, f"{cell['id']} 의 {name} cap 은 None 이어야 합니다"


def test_lot_index_fac_ids_match_the_operating_fabs():
    # M12는 실재하지 않습니다 — docs/datatables/hitachi/sem_list.txt (user-confirmed
    # 2026-08-03). sem_list가 장비 명부의 진실이고, lot 풀의 fac_id는 그
    # 어휘를 벗어나면 안 됩니다. 벗어나면 recipe_tat의 장비<->lot 짝짓기가
    # 조용히 폴백 경로로 새어 나갑니다.
    from back_dev_home.ebeam.device_statistics.providers.mock import _lot_index
    from back_dev_home.sem_list.providers.mock import FAC_IDS

    fac_ids = set(_lot_index().values())
    assert fac_ids <= set(FAC_IDS), f"sem_list에 없는 fac_id: {fac_ids - set(FAC_IDS)}"
    assert "M12" not in fac_ids
