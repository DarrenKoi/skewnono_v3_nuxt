"""Home-runnable regression tests for the tracked office adapter template."""

from datetime import datetime

from back_dev_home.ebeam.lateral_recipe.providers import office_example


def _sem_row(index: int) -> dict:
    return {
        "eqp_id": f"ECXDX{index:03d}",
        "eqp_model_cd": "CG6300",
        "vendor_nm": "HITACHI",
        "available": "On",
    }


def test_measured_tool_is_ready_when_version_doc_has_no_matching_tools(monkeypatch):
    """측정 이력 must prevent the impossible version-found, 0-ready result."""
    monkeypatch.setattr(
        office_example,
        "_version_docs",
        lambda *_args: [{
            "version": 301,
            "modified": "2026-07-23T09:00:00",
            "eqp_id": [],
        }],
    )
    monkeypatch.setattr(
        office_example,
        "_roster",
        lambda *_args: [_sem_row(index) for index in range(1, 21)],
    )
    monkeypatch.setattr(
        office_example,
        "_measured_eqp_ids",
        lambda *_args: {"ECXDX005"},
        raising=False,
    )

    response = office_example.get_lateral_recipe(
        "cd-sem",
        "R3",
        "RWEAXXX/RWEA_SELHMULTO2",
    )

    assert response["ready_count"] == 1
    assert response["not_ready_count"] == 19
    assert [
        (version["recipe_version"], version["ready_count"])
        for version in response["versions"]
    ] == [(301, 1)]
    measured = next(row for row in response["rows"] if row["eqp_id"] == "ECXDX005")
    assert measured["recipe_ready"] is True
    assert measured["recipe_version"] == 301


def test_measured_tools_query_exact_recipe_and_fab(monkeypatch):
    captured = {}

    def fake_composite(index, field, sub_aggs, query):
        captured.update(
            index=index,
            field=field,
            sub_aggs=sub_aggs,
            query=query,
        )
        return [
            {"key": {"group": "ecxdx005"}},
            {"key": {"group": "ECXDX006"}},
        ]

    monkeypatch.setattr(
        office_example,
        "_composite_buckets",
        fake_composite,
        raising=False,
    )
    monkeypatch.setattr(
        office_example,
        "get_anchor_time",
        lambda: datetime(2026, 7, 23, 9, 0, 0),
        raising=False,
    )

    measured = office_example._measured_eqp_ids(
        "cd-sem",
        "r3",
        "RWEAXXX/RWEA_SELHMULTO2",
    )

    assert measured == {"ECXDX005", "ECXDX006"}
    assert captured["index"] == "meas_hist_cdsem"
    assert captured["field"] == "eqp_id.keyword"
    assert captured["sub_aggs"] == {}
    assert captured["query"] == {
        "bool": {
            "filter": [
                {
                    "range": {
                        "timestamp": {
                            "gte": "2026-06-23T09:00:00",
                        },
                    },
                },
                {
                    "term": {
                        "full_name.keyword": "RWEAXXX/RWEA_SELHMULTO2",
                    },
                },
                {
                    "term": {
                        "fab_name.keyword": "R3",
                    },
                },
            ],
        },
    }


def test_version_equipment_ids_match_roster_case_insensitively(monkeypatch):
    monkeypatch.setattr(
        office_example,
        "_version_docs",
        lambda *_args: [{
            "version": 301,
            "modified": "2026-07-23T09:00:00",
            "eqp_id": ["ecxdx005"],
        }],
    )
    monkeypatch.setattr(
        office_example,
        "_roster",
        lambda *_args: [_sem_row(5)],
    )
    monkeypatch.setattr(
        office_example,
        "_measured_eqp_ids",
        lambda *_args: set(),
        raising=False,
    )

    response = office_example.get_lateral_recipe(
        "cd-sem",
        "R3",
        "RWEAXXX/RWEA_SELHMULTO2",
    )

    assert response["ready_count"] == 1
    assert response["rows"][0]["recipe_version"] == 301


def test_measured_tool_is_ready_when_there_is_no_version_doc_at_all(monkeypatch):
    """IDP 버전 문서가 하나도 없어도 측정 이력은 보유를 증명합니다.

    측정-도구 병합 전체가 `if generated_at_by_version:` 아래 있었던 탓에,
    30일치 실행 이력이 있는데 버전 문서가 없는 레시피는 모든 장비를 미보유로
    보고했습니다 — 이 어댑터의 docstring 이 불가능하다고 적어 둔 결과입니다.
    귀속할 버전이 없으므로 recipe_version 은 None 이고, 화면에는 그 전용
    버킷(utils/lateralVersionGroups.ts 의 UNKNOWN_VERSION_KEY)이 있습니다.
    """
    monkeypatch.setattr(office_example, "_version_docs", lambda *_args: [])
    monkeypatch.setattr(
        office_example,
        "_roster",
        lambda *_args: [_sem_row(index) for index in range(1, 6)],
    )
    monkeypatch.setattr(
        office_example,
        "_measured_eqp_ids",
        lambda *_args: {"ECXDX002", "ECXDX004"},
        raising=False,
    )

    response = office_example.get_lateral_recipe("cd-sem", "R3", "RWEAXXX/R")

    assert response["ready_count"] == 2
    by_id = {row["eqp_id"]: row for row in response["rows"]}
    assert by_id["ECXDX002"]["recipe_ready"] is True
    assert by_id["ECXDX002"]["recipe_version"] is None
    assert by_id["ECXDX002"]["recipe_generated_at"] is None
    assert by_id["ECXDX001"]["recipe_ready"] is False
    # 버전 문서가 없으므로 버전 이력은 비어 있고, 카드의 최신 버전도 없습니다.
    assert response["versions"] == []
    assert response["latest_recipe_version"] is None


def test_ready_count_never_disagrees_with_the_rows(monkeypatch):
    """카드의 숫자는 표에서 셀 수 있는 것과 항상 같아야 합니다."""
    monkeypatch.setattr(
        office_example,
        "_version_docs",
        lambda *_args: [{
            "version": 12,
            "modified": "2026-07-23T09:00:00",
            "eqp_id": ["ECXDX001"],
        }],
    )
    monkeypatch.setattr(
        office_example,
        "_roster",
        lambda *_args: [_sem_row(index) for index in range(1, 6)],
    )
    monkeypatch.setattr(
        office_example,
        "_measured_eqp_ids",
        lambda *_args: {"ECXDX003"},
        raising=False,
    )

    response = office_example.get_lateral_recipe("cd-sem", "R3", "RWEAXXX/R")

    assert response["ready_count"] == sum(
        1 for row in response["rows"] if row["recipe_ready"]
    )
    # 측정으로만 알려진 장비는 최신 버전으로 채워집니다 (버전이 존재할 때).
    by_id = {row["eqp_id"]: row for row in response["rows"]}
    assert by_id["ECXDX003"]["recipe_version"] == 12
