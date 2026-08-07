from back_dev_home.ebeam.hitachi._analytics import percentile_summary


def test_percentile_summary_is_empty_for_no_values():
    assert percentile_summary([]) == {}


def test_percentile_summary_is_monotonic():
    # p10 <= p25 <= p50 <= p75 <= p90 은 정의상 항상 성립해야 합니다.
    # 프론트엔드의 배지 판정이 "꼬리에 있는가"를 이 값들로 묻기 때문입니다.
    summary = percentile_summary([5, 1, 9, 3, 7, 2, 8, 4, 6, 10])
    keys = ["p10", "p25", "p50", "p75", "p90"]
    values = [summary[key] for key in keys]
    assert values == sorted(values)


def test_percentile_summary_uses_nearest_rank():
    # 10개 표본에서 p10은 최솟값, p90은 9번째 값(nearest-rank).
    summary = percentile_summary(range(1, 11))
    assert summary["p10"] == 1.0
    assert summary["p50"] == 5.0
    assert summary["p90"] == 9.0


def test_percentile_summary_handles_a_single_value():
    assert percentile_summary([4.5]) == {
        "p10": 4.5, "p25": 4.5, "p50": 4.5, "p75": 4.5, "p90": 4.5
    }
