"""The data-tool catalogue the RAG binds — shape and scope rules, on mock data."""

from __future__ import annotations

import pytest

from backend.chat import data_tools
from backend.chat.data_tools import TOOLS, ROW_LIMIT


_SCOPE = {"user_id": "u1", "groups": [], "fabs": []}


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_every_tool_runs_with_no_arguments_and_returns_a_frame(name):
    """The model may call a tool with nothing filled in; the defaults answer."""
    result = TOOLS[name].call({}, _SCOPE)
    assert set(result) == {"columns", "rows", "row_count", "truncated"}
    assert result["columns"], name
    assert result["rows"], name
    assert all(len(row) == len(result["columns"]) for row in result["rows"])
    assert result["row_count"] >= len(result["rows"])


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_every_tool_declares_a_json_schema_the_model_can_fill(name):
    tool = TOOLS[name]
    assert tool.name == name
    assert tool.description
    assert tool.parameters["type"] == "object"
    assert "start_date" in tool.parameters["properties"]
    assert "end_date" in tool.parameters["properties"]


def test_cells_are_json_scalars_only():
    result = TOOLS["fail_issue_summary"].call({}, _SCOPE)
    for row in result["rows"]:
        for cell in row:
            assert cell is None or isinstance(cell, (str, int, float, bool))


def test_summary_drops_nested_rankings_and_keeps_the_scalar_fields():
    result = TOOLS["fail_issue_summary"].call({}, _SCOPE)
    assert result["row_count"] == 1
    assert "align_fail_rate" in result["columns"]
    # The payload's ranking lists are their own tools, not summary cells.
    assert not any("ranking" in column for column in result["columns"])


def test_a_period_narrows_the_trend():
    full = TOOLS["recipe_tat_daily_trend"].call({}, _SCOPE)
    narrow = TOOLS["recipe_tat_daily_trend"].call(
        {"start_date": "2026-04-01", "end_date": "2026-04-07"}, _SCOPE
    )
    assert 0 < len(narrow["rows"]) <= 7
    assert len(narrow["rows"]) < len(full["rows"])


def test_scope_fabs_override_the_model(monkeypatch):
    seen = {}

    def fake_daily_trend(tool_type, fab_names, start, end, lot_cd=None):
        seen["fab_names"] = fab_names
        return [{"date": "2026-09-01", "total_meastime": 1, "exec_count": 1}]

    from backend.ebeam.recipe_tat import data

    monkeypatch.setattr(data, "get_daily_trend", fake_daily_trend)
    TOOLS["recipe_tat_daily_trend"].call(
        {"fab_names": ["M99"]}, {"user_id": "u", "groups": [], "fabs": ["M14"]}
    )
    assert seen["fab_names"] == ("M14",)


def test_an_empty_scope_defers_to_the_model(monkeypatch):
    """Empty ``fabs`` means unrestricted (user-confirmed 2026-09-19)."""
    seen = {}

    def fake_daily_trend(tool_type, fab_names, start, end, lot_cd=None):
        seen["fab_names"] = fab_names
        return []

    from backend.ebeam.recipe_tat import data

    monkeypatch.setattr(data, "get_daily_trend", fake_daily_trend)
    TOOLS["recipe_tat_daily_trend"].call({"fab_names": ["M16"]}, _SCOPE)
    assert seen["fab_names"] == ("M16",)
    TOOLS["recipe_tat_daily_trend"].call({}, _SCOPE)
    assert seen["fab_names"] is None


def test_rows_are_capped_and_the_cap_is_reported():
    rows = [{"n": i} for i in range(ROW_LIMIT + 5)]
    frame = data_tools._frame(rows)
    assert len(frame["rows"]) == ROW_LIMIT
    assert frame["row_count"] == ROW_LIMIT + 5
    assert frame["truncated"] is True


def test_an_empty_result_is_an_empty_frame_not_an_error():
    assert data_tools._frame([]) == {
        "columns": [], "rows": [], "row_count": 0, "truncated": False
    }


def test_describe_names_every_tool():
    text = "\n".join(data_tools.describe())
    for name in TOOLS:
        assert name in text
