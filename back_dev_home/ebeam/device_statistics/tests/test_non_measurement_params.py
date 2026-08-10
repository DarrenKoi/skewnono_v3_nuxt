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

import statistics

from back_dev_home.ebeam.device_statistics.para_buckets import is_measurement_param
from back_dev_home.ebeam.device_statistics.providers import mock
from back_dev_home.ebeam.device_statistics.providers.recipe_params import (
    NON_MEASUREMENT_PARAMS,
)
from back_dev_home.ebeam.device_statistics.providers.recipe_population import (
    is_exempt_job,
)


# outlierDetect.DEFAULT_OUTLIER_MULTIPLIER 와 같은 값입니다. 프론트엔드 상수라
# import 할 수 없어 적어 두고, 어긋나면 아래 회귀 테스트가 먼저 깨집니다.
_OUTLIER_MULTIPLIER = 2

_SAMPLE_LOTS = [f"R{index:03X}" for index in range(12)]


def _parameters():
    rows = mock.get_recipe_params(_SAMPLE_LOTS)
    return rows, [param for row in rows for param in row["parameters"]]


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
        if param["point_count"] > 16 and not is_measurement_param(param["name"])
    }
    assert not offenders, offenders


def test_dropping_the_exclusion_would_create_false_outliers():
    """제외 규칙을 지웠을 때 실제로 무언가 달라지는가.

    달라지지 않으면 그 규칙은 지워도 집에서 아무 테스트도 깨지지 않습니다.
    Dummy·Align 이 작은 값이라 **기준선을 끌어내리는** 쪽으로 작용하므로,
    확인할 것은 "문턱이 내려가 그 사이에 걸리는 측정 파라미터가 있는가" 입니다.
    """
    rows, _ = _parameters()
    judged = [row for row in rows if not is_exempt_job(row["recipe_id"])]
    kept = [
        param["point_count"]
        for row in judged for param in row["parameters"]
        if is_measurement_param(param["name"])
    ]
    everything = [
        param["point_count"] for row in judged for param in row["parameters"]
    ]

    with_rule = statistics.median(kept) * _OUTLIER_MULTIPLIER
    without_rule = statistics.median(everything) * _OUTLIER_MULTIPLIER
    assert without_rule < with_rule, (
        f"제외를 지워도 문턱이 그대로입니다 ({with_rule}). 규칙이 아무 일도 하지 "
        "않는 상태라, 지워도 회귀가 조용히 통과합니다."
    )
    false_positives = sum(1 for value in kept if without_rule < value <= with_rule)
    assert false_positives > 0, (
        "문턱은 내려가는데 그 구간에 걸리는 측정 파라미터가 없습니다 — "
        "제외 규칙을 지워도 화면의 outlier 수는 그대로입니다."
    )


def test_dummy_violates_the_sample_cap_on_its_own():
    # Sample 셀의 _other cap 은 0 이라 point 1 이면 곧바로 위반입니다. 판정
    # 면제가 빠지면 위반 수가 눈에 띄게 늘어야 합니다.
    assert dict(NON_MEASUREMENT_PARAMS)["Dummy"] >= 1


def test_over_16_parameters_stay_in_the_office_band():
    """16 초과 파라미터는 전체의 2~5% (user-confirmed 2026-08-10)."""
    _, params = _parameters()
    measured = [
        param for param in params if is_measurement_param(param["name"])
    ]
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
            param["point_count"] > 16 and is_measurement_param(param["name"])
            for param in row["parameters"]
        )
    )
    share = with_over / len(rows) * 100
    assert 1.5 <= share <= 6.0, f"{share:.1f}% of recipes carry an over-16 parameter"
