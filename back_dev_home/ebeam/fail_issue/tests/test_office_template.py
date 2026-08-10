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
