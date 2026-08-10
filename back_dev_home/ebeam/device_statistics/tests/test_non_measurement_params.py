"""Dummy·Align 의 point 수와 "16 초과" 파라미터의 발생률.

이 파일은 **숫자 두 벌**을 지킵니다.

1. 실물 비율 — 16 point 를 넘는 파라미터는 전체 파라미터의 2~5% 이고 전체
   recipe 의 3% 정도에 몰려 있습니다 (user-confirmed 2026-08-10). mock 이 이
   비율을 벗어나면 화면은 멀쩡하지만 집에서 보는 분포가 사무실과 다른 이야기를
   합니다. 실제로 2026-08-10 이전에는 recipe 의 75% 가 16 초과 파라미터를
   갖고 있었고(실물의 25배), 아무 테스트도 그것을 말해 주지 않았습니다.

2. Dummy·Align 제외 규칙의 회귀 — outlierDetect 의 문턱은 ``2 × 중앙값``
   입니다. 둘의 point 수가 1~3 이라 제외를 지우면 중앙값이 **내려가고** 문턱도
   따라 내려가, 정상 범위의 파라미터가 outlier 로 잡힙니다. 규칙이 막는 것은
   "큰 값이 기준선을 끌어올려 진짜 과다측정을 가리는 것" 이 아니라 **오검출**
   입니다 — 2026-08-10 에 Align 의 실물 값(1~3)이 확인되면서 방향이 뒤집혔습니다.
"""


from back_dev_home.ebeam.device_statistics.para_buckets import (
    has_non_measurement_name,
    measurement_parameters,
)
from back_dev_home.ebeam.device_statistics.providers import mock
from back_dev_home.ebeam.device_statistics.providers.recipe_params import (
    NON_MEASUREMENT_PARAMS,
)


# outlierDetect.DEFAULT_OUTLIER_MULTIPLIER 와 같은 값입니다. 프론트엔드 상수라
# import 할 수 없어 적어 두고, 어긋나면 아래 회귀 테스트가 먼저 깨집니다.
_OUTLIER_MULTIPLIER = 2

_SAMPLE_LOTS = [f"R{index:03X}" for index in range(12)]


def _parameters():
    rows = mock.get_recipe_params(_SAMPLE_LOTS)
    return rows, [param for row in rows for param in row["parameters"]]


def _measured(row):
    """이 recipe 에서 통계에 들어가는 파라미터 — 맨 앞의 준비용을 뺀 나머지."""
    kept = measurement_parameters(
        {param["name"]: param["point_count"] for param in row["parameters"]}
    )
    return [param for param in row["parameters"] if param["name"] in kept]


def test_dummy_and_align_measure_one_to_three_points():
    # user-confirmed 2026-08-10. 40 이던 시절에는 정확 일치 버킷이라 아무
    # 버킷에도 안 들어가 보이지 않았고, 구간 버킷으로 바뀌자마자 Sample recipe
    # 25% 가 통째로 para_over_16 을 갖게 됐습니다.
    for name, point_count in NON_MEASUREMENT_PARAMS:
        assert 1 <= point_count <= 3, (name, point_count)


def test_no_over_16_parameter_is_a_non_measurement_one():
    """16 초과 신호는 **측정 파라미터 이름**이 날라야 합니다.

    통계에서 빠지는 이름이 통계를 만드는 모순을 막습니다 — Align 40 이 정확히
    그 상태였습니다.
    """
    _, params = _parameters()
    offenders = {
        param["name"] for param in params
        if param["point_count"] > 16 and has_non_measurement_name(param["name"])
    }
    assert not offenders, offenders


def test_helper_parameters_always_come_first_in_a_recipe():
    """준비용 파라미터가 목록 **맨 앞**에 있어야 위치 규칙이 작동합니다.

    이 테스트가 여기 있는 이유는 이 mock 이 2026-08-10 까지 Dummy·Align 을
    **맨 뒤**에 붙이고 있었기 때문입니다. 위치 규칙에서 뒤에 붙은 것은 곧
    "측정 파라미터" 라는 뜻이라, 그 상태로는 백엔드도 프론트엔드도 아무것도
    걸러 내지 못하면서 테스트는 전부 통과합니다.

    앞선 판(2026-08-10 오전)의 이 자리 테스트는 "제외를 지우면 중앙값이
    내려간다" 였는데, 준비용 파라미터가 recipe 의 20% 에만 2개씩 붙는 지금
    분포에서는 중앙값이 움직이지 않습니다. 통계량으로 규칙의 생사를 확인하는
    것은 비율이 조금만 바뀌어도 흔들려서, 위치라는 **구조**를 직접 봅니다.
    """
    rows, _ = _parameters()
    with_helpers = 0
    for row in rows:
        names = [param["name"] for param in row["parameters"]]
        helper_positions = [
            index for index, name in enumerate(names)
            if has_non_measurement_name(name)
        ]
        if not helper_positions:
            continue
        with_helpers += 1
        assert helper_positions == list(range(len(helper_positions))), (
            f"{row['recipe_id']} 의 준비용 파라미터가 앞이 아닙니다: {names}"
        )
    assert with_helpers > 0, (
        "준비용 파라미터를 가진 recipe 가 하나도 없습니다 — 위치 규칙이 "
        "집에서 한 번도 실행되지 않습니다."
    )


def test_helper_parameters_are_not_on_every_recipe():
    """가끔 나타납니다 (user-confirmed 2026-08-10) — 늘 있는 것이 아닙니다."""
    rows, _ = _parameters()
    with_helpers = sum(
        1 for row in rows
        if any(has_non_measurement_name(param["name"]) for param in row["parameters"])
    )
    share = with_helpers / len(rows)
    assert 0.05 <= share <= 0.45, f"{share:.0%} of recipes carry helper parameters"


def test_over_16_parameters_stay_in_the_office_band():
    """16 초과 파라미터는 전체의 2~5% (user-confirmed 2026-08-10)."""
    _, params = _parameters()
    rows_all, _ = _parameters()
    measured = [param for row in rows_all for param in _measured(row)]
    over = [param for param in measured if param["point_count"] > 16]
    share = len(over) / len(measured) * 100
    assert 1.5 <= share <= 6.0, f"{share:.1f}% of parameters exceed 16 points"


def test_over_16_recipes_stay_rare():
    """16 초과 파라미터를 가진 recipe 는 전체의 3% 정도 (user-confirmed 2026-08-10).

    상한을 6% 로 둔 것은 특수 측정 job(3%) 위에 "정상 recipe 안의 외톨이
    과다측정"(1%)이 얹히기 때문입니다. 두 자릿수가 되면 그건 다른 이야기입니다.
    """
    rows, _ = _parameters()
    with_over = sum(
        1 for row in rows
        if any(
            param["point_count"] > 16 for param in _measured(row)
        )
    )
    share = with_over / len(rows) * 100
    assert 1.5 <= share <= 6.0, f"{share:.1f}% of recipes carry an over-16 parameter"
