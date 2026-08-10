"""para_* 구간 버킷 — 경계와 계약 정합.

경계는 이 화면의 숫자 전부를 정하는데 코드로는 상수 네 개일 뿐이라, 한 칸
어긋나도 예외 없이 "숫자가 조금 다르다" 로만 나타납니다. 그래서 경계 **양쪽
값**을 하나씩 못 박습니다.
"""

import pytest

from back_dev_home.ebeam.device_statistics import contracts
from back_dev_home.ebeam.device_statistics.para_buckets import (
    PARA_BUCKETS,
    bucket_for,
    count_points,
    para_block,
)


# 경계와 그 양쪽. x <= 5 / 5 < x <= 9 / 9 < x <= 13 / 13 < x <= 16 / 16 < x
@pytest.mark.parametrize(("point_count", "expected"), [
    (1, "para_5"),
    (5, "para_5"),
    (6, "para_9"),
    (9, "para_9"),
    (10, "para_13"),
    (13, "para_13"),
    (14, "para_16"),
    (16, "para_16"),
    (17, "para_over_16"),
    (60, "para_over_16"),
])
def test_boundaries(point_count, expected):
    assert bucket_for(point_count) == expected


def test_zero_and_negative_land_in_the_lowest_bucket():
    # 원천에 이런 값이 있는지는 확인된 바 없습니다. 있다면 어느 버킷에도 못
    # 들어가 조용히 사라지는 것보다 가장 낮은 구간에 보이는 편이 낫습니다.
    assert bucket_for(0) == "para_5"
    assert bucket_for(-3) == "para_5"


def test_the_confirmed_office_recipe_is_no_longer_all_zero():
    # office 확인 2026-08-10 — 이 recipe 가 정확 일치 정의에서는 세 파라미터
    # 모두 16/13/9/5 밖이라 para_all = 0 이었습니다. 구간 정의로 바뀐 이유가
    # 바로 이것이므로, 그 회귀를 여기서 잡습니다.
    counts = count_points({"EDGE": 10, "LEVEL": 4, "WAFER": 10}.values())
    assert counts["para_13"] == 2
    assert counts["para_5"] == 1
    assert counts["para_9"] == counts["para_16"] == counts["para_over_16"] == 0
    assert para_block(counts)["para_all"] == 3


def test_every_bucket_key_is_always_present():
    # 값이 0 인 버킷을 빠뜨리면 화면이 그 구간을 그리지 않고, 누적 막대가
    # recipe 마다 다른 칸 수로 나옵니다.
    counts = count_points([])
    assert set(counts) == set(PARA_BUCKETS)
    block = para_block({})
    for name in PARA_BUCKETS:
        assert block[name] == 0
        assert block[f"{name}_percent"] == 0.0
    assert block["para_all"] == 0


def test_para_all_is_the_parameter_total():
    # 구간이 전체를 덮으므로 "총 개수" 와 "버킷 합" 은 같은 값입니다 — 정확
    # 일치 시절 idp_ver.txt 에 열려 있던 질문이 여기서 닫힙니다.
    points = [1, 5, 6, 9, 10, 13, 14, 16, 17, 100]
    block = para_block(count_points(points))
    assert block["para_all"] == len(points)


def test_percentages_total_100():
    block = para_block(count_points([1, 6, 10, 14, 17]))
    total = sum(block[f"{name}_percent"] for name in PARA_BUCKETS)
    assert total == pytest.approx(100.0)


def test_contract_declares_exactly_these_buckets():
    # 계약과 버킷 목록이 갈라지면 mock 은 키를 내는데 계약은 모르는(또는 그
    # 반대인) 상태가 되고, 어느 쪽이 맞는지 화면에서만 드러납니다.
    for row_type in (contracts.RecipeInfoRow, contracts.SummaryRow):
        fields = set(row_type.__annotations__)
        for name in PARA_BUCKETS:
            assert name in fields, f"{row_type.__name__} is missing {name}"
            assert f"{name}_percent" in fields, f"{row_type.__name__} is missing {name}_percent"
        assert "para_all" in fields
        # 계약에만 남은 옛 버킷이 없는지 — 반대 방향의 드리프트입니다.
        stale = {
            f for f in fields
            if f.startswith("para_")
            and f != "para_all"
            and f.removesuffix("_percent") not in PARA_BUCKETS
        }
        assert not stale, f"{row_type.__name__} still declares {stale}"
