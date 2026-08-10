"""Home-runnable regression tests for the tracked office adapter template.

사무실 클러스터는 집에서 닿지 않으므로 OpenSearch 를 타는 함수만 가짜로
바꾸고, 나머지(필터 조립, 비율 계산)는 진짜를 돌립니다. office.py 는 이
템플릿의 사본이라, 여기서 잡히지 않는 실수는 사무실에서 처음 드러납니다.
"""

from datetime import datetime

from back_dev_home.ebeam.fail_issue.providers import office_example


def test_summary_rates_divide_by_documents_not_by_meastime(monkeypatch):
    """분자는 filter 의 doc_count 인데 분모만 value_count(meastime) 였습니다.

    meastime 이 없는 문서(msr_check != "Yes")의 실패는 분자에 들어가면서
    분모에서는 빠져 비율이 부풀려졌습니다. 게다가 MSR 파일이 없다는 것 자체가
    실패 신호라, 하필 문제가 몰린 곳에서 가장 크게 틀렸습니다.
    """
    captured = {}

    def fake_aggregate(index, aggs, query):
        captured["aggs"] = aggs
        return {
            "execs": {"value": 100},            # 실행 100건
            "align_fail": {"doc_count": 10},
            "align_na": {"doc_count": 2},
            "meas_fail": {"doc_count": 5},
            "eqps": {"value": 4},
            "recipes": {"value": 3},
        }

    monkeypatch.setattr(office_example, "_aggregate", fake_aggregate)
    monkeypatch.setattr(office_example, "_distinct_lot_cds", lambda *a, **k: 6)
    # get_anchor_time 은 클러스터에 max(timestamp) 를 묻습니다.
    monkeypatch.setattr(
        office_example, "get_anchor_time", lambda: datetime(2026, 8, 10, 9, 0)
    )

    summary = office_example.get_summary("cd-sem", None, "2026-08-01", "2026-08-10")

    assert summary["total_executions"] == 100
    assert summary["align_fail_rate"] == 0.1   # 10/100 — 90 으로 나눴다면 0.1111
    assert summary["meas_fail_rate"] == 0.05   # 5/100  — 90 으로 나눴다면 0.0556
    assert captured["aggs"]["execs"] == {"value_count": {"field": "timestamp"}}


def test_avg_fail_ratio_divides_by_every_row_in_the_group(monkeypatch):
    """평균은 표에 보이는 것의 평균이어야 합니다.

    OpenSearch 의 avg 는 필드를 **가진** 문서로만 나누는데, 행 경로는 결측
    fail_ratio 를 normalize_fail_ratio 로 0.0 으로 강제합니다 — 계약 타입도
    plain float 입니다. 그래서 avg 는 표가 0.0% 로 보여 주는 행을 빼 버렸고,
    카드가 "보이는 것의 평균" 이기를 그만뒀습니다. mock 은 전체 행으로
    나눕니다.

    meastime 과는 반대 판단입니다: 0초짜리 측정은 실재하지 않으므로 그쪽
    평균은 결측을 분모에서 뺍니다.
    """
    def fake_ranked(tool_type, clauses, sub_aggs, limit):
        assert sub_aggs["ratio_sum"] == {"sum": {"field": "fail_ratio"}}
        return [{
            "key": {"group": "ADI/ADI_CD_BIAS_001"},
            "doc_count": 4,                       # 실행 4건
            "fail": {"doc_count": 1, "eqps": {"buckets": []}},
            "ratio_sum": {"value": 80.0},         # 그중 fail_ratio 합이 80
        }]

    monkeypatch.setattr(office_example, "_ranked_recipe_buckets", fake_ranked)
    monkeypatch.setattr(office_example, "_bucket_fab_names", lambda b: [])

    rows = office_example.get_meas_ranking("cd-sem", None, "2026-08-01", "2026-08-10")

    # 80 / 4 = 20.0. avg 였다면 값을 가진 문서 수로 나눠 더 컸을 것입니다.
    assert rows[0]["avg_fail_ratio"] == 20.0
    assert rows[0]["exec_count"] == 4
