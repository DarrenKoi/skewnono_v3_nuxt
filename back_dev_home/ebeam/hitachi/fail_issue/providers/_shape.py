"""mock·office 공용 payload 조립.

provider 는 자기 소스에서 격자(grid)만 만들고 여기로 넘깁니다. 지수·구간·
분위수를 두 provider 가 각자 계산하면 언젠가 어긋나고, 그때 어느 쪽이 맞는지
판정할 방법이 없습니다 — 집에서는 office 를 실행할 수 없으므로 그 판정자가
아예 존재하지 않습니다. recipe_tat/providers/_shape.py 와 같은 규약입니다.
"""

from __future__ import annotations

from math import sqrt

from back_dev_home.ebeam.hitachi.fail_issue.contracts import (
    CONFIDENCE_Z,
    FAIL_INDEX_MIN_EXPECTED,
)


def byar_interval(
    observed: int,
    expected: float,
    z: float = CONFIDENCE_Z,
) -> tuple[float, float]:
    """관측/기대 건수비의 신뢰구간 (Byar 근사).

    이 지수는 역학의 간접표준화 비(SMR)와 같은 양이고, Byar 근사는 그쪽의
    표준 처방입니다. 정확한 Garwood 구간(카이제곱 분위수)을 쓰지 않는 이유는
    scipy 의존을 들이지 않기 위해서이며, 근사 오차는 observed >= 1 에서
    소수 셋째 자리 수준이라 배지 판정에 영향을 주지 않습니다.

    observed == 0 은 sqrt(0) 로 0 나눗셈이 나는 자리라 분기가 필요합니다.
    하한은 그 경우 정확히 0 입니다 — 실패가 0건이면 참값이 0일 수도 있습니다.
    """
    if expected <= 0:
        return (0.0, 0.0)

    if observed <= 0:
        low = 0.0
    else:
        low = observed * (1 - 1 / (9 * observed) - z / (3 * sqrt(observed))) ** 3 / expected
        low = max(0.0, low)

    upper_n = observed + 1
    high = upper_n * (1 - 1 / (9 * upper_n) + z / (3 * sqrt(upper_n))) ** 3 / expected

    return (round(low, 4), round(high, 4))


def standardised(
    observed: int,
    expected: float,
) -> tuple[float | None, float | None, float | None]:
    """(index, low, high). 기대가 표시 하한 미만이면 셋 다 None.

    None 은 "실패하지 않았다"가 아니라 **"모른다"** 입니다. 호출자는 어느
    쪽으로도 판정하면 안 되며, 특히 0 으로 채우면 안 됩니다.
    """
    if expected < FAIL_INDEX_MIN_EXPECTED:
        return (None, None, None)
    low, high = byar_interval(observed, expected)
    return (round(observed / expected, 4), low, high)
