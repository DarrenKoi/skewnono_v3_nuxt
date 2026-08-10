"""Dummy·Align 의 point 수와 "16 초과" 파라미터의 발생률.

이 파일은 **숫자 두 벌**을 지킵니다.

1. 실물 비율 — 16 point 를 넘는 파라미터는 전체 파라미터의 2~5% 이고 전체
   recipe 의 3% 정도에 몰려 있습니다 (user-confirmed 2026-08-10). mock 이 이
   비율을 벗어나면 화면은 멀쩡하지만 집에서 보는 분포가 사무실과 다른 이야기를
   합니다. 실제로 2026-08-10 이전에는 recipe 의 75% 가 16 초과 파라미터를
   갖고 있었고(실물의 25배), 아무 테스트도 그것을 말해 주지 않았습니다.

2. Align 이 outlier 회귀를 살려 두는가 — outlierDetect 의 문턱은
   ``2 × 중앙값`` 입니다. Align 의 point 수가 그 아래로 내려가면 "Dummy·Align 을
   outlier 집계에서 뺀다" 는 규칙을 **지워도** 집의 테스트가 조용히 통과합니다.
   Align 은 16 이하여야 하고(실물 사실) 동시에 문턱보다는 커야 하는데, 이 둘
   사이가 좁아서 한쪽만 보고 값을 만지면 다른 쪽이 깨집니다.
"""

import statistics

from back_dev_home.ebeam.device_statistics.providers import mock
from back_dev_home.ebeam.device_statistics.providers.recipe_params import (
    NON_MEASUREMENT_PARAMS,
)


# outlierDetect.DEFAULT_OUTLIER_MULTIPLIER 와 같은 값입니다. 프론트엔드 상수라
# import 할 수 없어 적어 두고, 어긋나면 아래 회귀 테스트가 먼저 깨집니다.
_OUTLIER_MULTIPLIER = 2

_NON_MEASUREMENT_NAMES = {name for name, _ in NON_MEASUREMENT_PARAMS}

_SAMPLE_LOTS = [f"R{index:03X}" for index in range(12)]


def _parameters():
    rows = mock.get_recipe_params(_SAMPLE_LOTS)
    return rows, [param for row in rows for param in row["parameters"]]


def test_align_does_not_exceed_16_points():
    # user-confirmed 2026-08-10. 40 이던 시절에는 정확 일치 버킷이라 아무
    # 버킷에도 안 들어가 보이지 않았고, 구간 버킷으로 바뀌자마자 Sample recipe
    # 25% 가 통째로 para_over_16 을 갖게 됐습니다.
    align = dict(NON_MEASUREMENT_PARAMS)["Align"]
    assert align <= 16, align


def test_align_still_clears_the_outlier_threshold():
    """Align 이 문턱 위에 있어야 outlier 제외 규칙의 회귀가 살아 있습니다."""
    _, params = _parameters()
    measured = [
        param["point_count"] for param in params
        if param["name"] not in _NON_MEASUREMENT_NAMES
    ]
    threshold = statistics.median(measured) * _OUTLIER_MULTIPLIER
    align = dict(NON_MEASUREMENT_PARAMS)["Align"]
    assert align > threshold, (
        f"Align({align}) 이 outlier 문턱({threshold}) 아래로 내려갔습니다. "
        "이 상태에서는 Dummy·Align 제외 규칙을 지워도 테스트가 조용히 통과합니다 "
        "— 값을 올릴 수는 없으므로(16 이하가 실물) 회귀 설계를 다시 보십시오."
    )


def test_dummy_violates_the_sample_cap_on_its_own():
    # Sample 셀의 _other cap 은 0 이라 point 1 이면 곧바로 위반입니다. 판정
    # 면제가 빠지면 위반 수가 눈에 띄게 늘어야 합니다.
    assert dict(NON_MEASUREMENT_PARAMS)["Dummy"] >= 1


def test_over_16_parameters_stay_in_the_office_band():
    """16 초과 파라미터는 전체의 2~5% (user-confirmed 2026-08-10)."""
    _, params = _parameters()
    measured = [
        param for param in params if param["name"] not in _NON_MEASUREMENT_NAMES
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
            param["point_count"] > 16
            and param["name"] not in _NON_MEASUREMENT_NAMES
            for param in row["parameters"]
        )
    )
    share = with_over / len(rows) * 100
    assert 1.5 <= share <= 6.0, f"{share:.1f}% of recipes carry an over-16 parameter"
