"""Home-runnable regression tests for the tracked office adapter template.

사무실 클러스터는 집에서 닿지 않으므로, 집에서 검증 가능한 부분은 딱
하나입니다: **버킷 → 격자 번역**. `callable()` 검사만으로는
`b["key"]["recipe"]` 같은 오타를 못 잡고, 그 오타는 office.py 사본에서
터집니다 — 그리고 사무실에서 터지는 어댑터 하나가 앱 팩토리 전체를
멈춥니다. OpenSearch 를 타는 두 함수(`_composite_buckets`, `_aggregate`)만
가짜로 바꾸고 나머지(필터 조립, 격자, 공용 조립기)는 진짜를 돌립니다.
"""

from back_dev_home.ebeam.recipe_tat.providers import office_example


def test_get_equipments_requests_four_named_sources_in_order(monkeypatch):
    captured = {}

    def fake_composite(index, field, sub_aggs, query):
        captured["index"] = index
        captured["field"] = field
        captured["sub_aggs"] = sub_aggs
        captured["query"] = query
        return []

    monkeypatch.setattr(office_example, "_composite_buckets", fake_composite)

    office_example.get_equipments("cd-sem", ("M14",), "2026-08-01", "2026-08-02")

    assert captured["index"] == "meas_hist_cdsem"
    # 이름은 아래 격자 번역이 읽는 키입니다 — 순서/이름이 바뀌면 표의 fab 열에
    # 모델이 들어가도 예외 하나 없이 잘못된 화면이 나옵니다.
    assert captured["field"] == [
        ("eqp", "eqp_id.keyword"),
        ("fab", "fab_name.keyword"),
        ("model", "eqp_model_cd.keyword"),
        ("recipe", "full_name.keyword"),
    ]
    assert captured["sub_aggs"] == {"tat": {"sum": {"field": "meastime"}}}
    assert {"term": {"fab_name.keyword": "M14"}} in captured["query"]["bool"]["filter"]


def test_get_equipments_translates_buckets_into_the_shared_assembler(monkeypatch):
    monkeypatch.setattr(
        office_example,
        "_composite_buckets",
        lambda *_a: [
            {
                "key": {"eqp": "CD01", "fab": "M14", "model": "CG6300",
                        "recipe": "ADI/A"},
                "doc_count": 2,
                "tat": {"value": 100.0},
            },
            {
                "key": {"eqp": "CD01", "fab": "M14", "model": "CG6300",
                        "recipe": "ADI/B"},
                "doc_count": 1,
                "tat": {"value": 50.0},
            },
            {
                "key": {"eqp": "CD02", "fab": "M14", "model": "CG6380",
                        "recipe": "ADI/A"},
                "doc_count": 1,
                "tat": {"value": 20.0},
            },
        ],
    )

    payload = office_example.get_equipments(
        "cd-sem", ("M14",), "2026-08-01", "2026-08-02"
    )

    rows = {row["eqp_id"]: row for row in payload["equipments"]}
    assert rows["CD01"]["fab_name"] == "M14"
    assert rows["CD01"]["eqp_model_cd"] == "CG6300"
    assert rows["CD01"]["exec_count"] == 3           # 두 레시피 버킷의 합
    assert rows["CD01"]["total_meastime"] == 150
    assert rows["CD01"]["recipe_count"] == 2
    assert rows["CD02"]["eqp_model_cd"] == "CG6380"
    assert payload["fleet"]["tool_count"] == 2
    assert payload["fab_names"] == ["M14"]


def test_get_equipment_compare_builds_both_grids(monkeypatch):
    captured = {}

    def fake_aggregate(index, aggs, query):
        captured["aggs"] = aggs
        captured["query"] = query
        return {
            "by_eqp": {
                "buckets": [
                    {
                        "key": "CD01",
                        "by_day": {
                            "buckets": [
                                {"key_as_string": "2026-08-01",
                                 "doc_count": 2, "tat": {"value": 60.0}},
                                {"key_as_string": "2026-08-02",
                                 "doc_count": 0, "tat": {"value": 0.0}},
                            ]
                        },
                    }
                ]
            }
        }

    monkeypatch.setattr(office_example, "_aggregate", fake_aggregate)
    monkeypatch.setattr(
        office_example,
        "_composite_buckets",
        lambda *_a: [
            {"key": {"eqp": "CD01", "recipe": "ADI/A"},
             "doc_count": 2, "tat": {"value": 60.0}},
        ],
    )

    payload = office_example.get_equipment_compare(
        "cd-sem", None, "2026-08-01", "2026-08-02", ("CD01", "CD02", "CD01")
    )

    # 선택은 5개로 상한이 걸려 있으므로 terms size 가 선택 수 전부를 덮습니다.
    assert payload["eqp_ids"] == ["CD01", "CD02"]          # 순서 보존 dedupe
    assert captured["aggs"]["by_eqp"]["terms"] == {
        "field": "eqp_id.keyword", "size": 2
    }
    assert {"terms": {"eqp_id.keyword": ["CD01", "CD02"]}} in (
        captured["query"]["bool"]["filter"]
    )
    histogram = captured["aggs"]["by_eqp"]["aggs"]["by_day"]["date_histogram"]
    # yyyy-MM-dd 가 아니면 조립기가 모든 행을 조용히 버립니다.
    assert histogram["format"] == "yyyy-MM-dd"
    assert histogram["extended_bounds"] == {"min": "2026-08-01", "max": "2026-08-02"}

    trends = {series["eqp_id"]: series for series in payload["trends"]}
    assert [point["total_meastime"] for point in trends["CD01"]["points"]] == [60, 0]
    # 버킷이 하나도 없던 장비도 0 으로 채운 계열을 받습니다.
    assert [point["total_meastime"] for point in trends["CD02"]["points"]] == [0, 0]
    assert [cell["meas_counts"] for cell in payload["recipes"][0]["cells"]] == [2, 0]


def test_get_equipment_compare_short_circuits_on_an_empty_selection(monkeypatch):
    def explode(*_args, **_kwargs):
        raise AssertionError("빈 선택으로 OpenSearch 를 때리면 안 됩니다.")

    monkeypatch.setattr(office_example, "_aggregate", explode)
    monkeypatch.setattr(office_example, "_composite_buckets", explode)

    payload = office_example.get_equipment_compare(
        "cd-sem", None, "2026-08-01", "2026-08-02", ()
    )

    assert payload["eqp_ids"] == []
    assert payload["trends"] == []
    assert payload["recipes"] == []


from datetime import datetime as _datetime


def test_summary_counts_executions_by_document_not_by_meastime(monkeypatch):
    """실행 건수와 평균 분모는 서로 다른 숫자입니다.

    meastime 은 msr_check == "Yes" 인 문서에만 있습니다(user-confirmed
    2026-08-10). 한 변수가 두 자리를 겸하던 탓에 요약 카드가 doc_count 로
    그려지는 자기 트렌드 차트보다 작게 나왔습니다.
    """
    captured = {}

    def fake_aggregate(index, aggs, query):
        captured["aggs"] = aggs
        return {
            "tat": {"value": 9000},
            "docs": {"value": 100},      # 실행 100건
            "measured": {"value": 90},   # 그중 10건은 msr_check != "Yes"
            "recipes": {"value": 7},
        }

    monkeypatch.setattr(office_example, "_aggregate", fake_aggregate)
    # get_anchor_time 은 클러스터에 max(timestamp) 를 묻습니다.
    monkeypatch.setattr(
        office_example, "get_anchor_time", lambda: _datetime(2026, 8, 10, 9, 0)
    )

    summary = office_example.get_summary("cd-sem", None, "2026-08-01", "2026-08-10")

    # 카드는 문서를 셉니다 — 측정이 실행된 이상 raw data 유무와 무관합니다.
    assert summary["total_executions"] == 100
    # 평균은 meastime 이 있는 문서로만 나눕니다. 100 으로 나눴다면 90.0 입니다.
    assert summary["avg_meastime"] == 100.0
    assert summary["total_tat_seconds"] == 9000

    # 두 집계가 서로 다른 필드를 세는지 고정합니다.
    assert captured["aggs"]["docs"] == {"value_count": {"field": "timestamp"}}
    assert captured["aggs"]["measured"] == {"value_count": {"field": "meastime"}}


def test_overlapping_lot_cd_shows_the_m_fab_tech_node(monkeypatch):
    """두 카탈로그에 모두 있는 lot 은 M-fab 이 이깁니다.

    user-confirmed 2026-08-10. 예전에는 prod_catg_cd 를 먼저 보는 바람에
    같은 lot 이 집에서는 기술 노드 칩으로, 사무실에서는 제품 카테고리 칩으로
    보였습니다 — mock 의 _analytics.lot_metadata() 는 device_desc 가 r3
    엔트리를 통째로 덮어써서 tech_nm 이 이깁니다.
    """
    monkeypatch.setattr(
        office_example, "_composite_buckets",
        lambda *a, **k: [{"key": {"group": "R00124001"}, "doc_count": 3,
                          "tat": {"value": 900}}],
    )
    monkeypatch.setattr(office_example, "_lot_id_to_lot_cd", lambda: {"R00124001": "R001"})
    # 겹치는 lot_cd — 양쪽 카탈로그에 모두 있습니다.
    monkeypatch.setattr(office_example, "_r3_device_grp", lambda: {"R001": "DRAM"})
    monkeypatch.setattr(office_example, "_device_desc", lambda: {"R001": {"tech_nm": "TP"}})

    rows = office_example.get_devices("cd-sem", None, "2026-08-01", "2026-08-10")

    assert rows[0]["tech_nm"] == "TP"
    assert rows[0]["prod_catg_cd"] is None
