"""Byar 근사 신뢰구간 단독 검증.

이 함수는 이 기능에서 **유일하게 자명하지 않은 수식**입니다. 나머지는 합계와
나눗셈이라 눈으로 검증되지만, Byar 근사는 틀려도 그럴듯한 숫자를 냅니다 —
지수 하나만 잘못 써도 구간이 좁아지거나 넓어질 뿐 예외가 나지 않고, 그
결과는 "배지가 좀 덜/더 뜨네" 로만 보입니다. 그래서 문헌값 대조를 겁니다.
"""

import math

import pytest

from back_dev_home.ebeam.fail_issue.contracts import (
    CONFIDENCE_Z,
    FAIL_INDEX_MIN_EXPECTED,
)
from back_dev_home.ebeam.fail_issue.providers._shape import (
    byar_interval,
    standardised,
)


def test_matches_the_published_approximation():
    """관측 11 · 기대 5 → 약 [1.10, 3.94].

    Byar 의 근사식을 손으로 계산한 값입니다. 이 하나가 지수·계수 오타를
    전부 잡습니다.
    """
    low, high = byar_interval(11, 5.0)
    assert low == pytest.approx(1.0967, abs=1e-4)
    assert high == pytest.approx(3.9367, abs=1e-4)


def test_zero_observed_has_a_zero_lower_bound_and_does_not_raise():
    """obs=0 은 log/sqrt 가 정의되지 않는 자리입니다.

    분기를 빼면 ZeroDivisionError 가 납니다. 하한은 정확히 0 이어야 하며
    ('실패가 0건이면 진짜 0일 수도 있다'), 상한은 유한해야 합니다.
    """
    low, high = byar_interval(0, 4.0)
    assert low == 0.0
    assert high == pytest.approx(0.917, abs=1e-3)


def test_interval_always_brackets_the_point_estimate():
    for observed in range(0, 200):
        expected = 37.5
        low, high = byar_interval(observed, expected)
        index = observed / expected
        assert low <= index <= high, (observed, low, index, high)


def test_interval_narrows_as_the_sample_grows():
    """같은 지수(=1.0)를 유지한 채 규모만 키우면 구간이 좁아져야 합니다.

    이 단조성이 깨지면 '조용한 장비는 극단적이어야 배지를 받는다'는 설계의
    핵심 성질이 사라집니다.
    """
    widths = []
    for scale in (5, 20, 80, 320):
        low, high = byar_interval(scale, float(scale))
        widths.append(high - low)
    assert widths == sorted(widths, reverse=True), widths


def test_standardised_withholds_a_verdict_below_the_display_floor():
    assert standardised(0, 0.8) == (None, None, None)
    assert standardised(1, 0.5) == (None, None, None)


def test_standardised_reports_at_and_above_the_display_floor():
    index, low, high = standardised(3, FAIL_INDEX_MIN_EXPECTED)
    assert index == 3.0
    assert low is not None and high is not None
    assert low <= index <= high


def test_z_is_the_two_sided_95_percent_value():
    # 구간의 의미가 조용히 바뀌는 것을 막습니다. 이 값을 바꾸려면 설계 3.2절도
    # 함께 바꿔야 합니다.
    assert CONFIDENCE_Z == 1.96
    assert math.isclose(FAIL_INDEX_MIN_EXPECTED, 1.0)
