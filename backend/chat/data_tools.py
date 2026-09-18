"""The structured-data tool catalogue chat publishes to the RAG.

The RAG owns the answering loop (``agent_query``); chat owns the data. This
module is where the two meet for OpenSearch-backed facts: each tool wraps ONE
existing ``data.py`` function, so the same name resolves to ``mock.py`` at
home and ``office.py`` at the office with nothing to configure here. Proposed
in ``chat/docs/2026-09-18-chat-to-rag-data-tools-contract.md`` §1, answered
2026-09-19 (function calling supported, 256K context, empty ``fabs`` means
unrestricted).

The RAG side binds the catalogue as function-calling tools::

    from backend.chat.data_tools import TOOLS
    for tool in TOOLS.values():
        bind(name=tool.name, description=tool.description, parameters=tool.parameters)
    ...
    result = TOOLS[name].call(args, scope)      # -> ToolResult (dataframe dict)

Rules the catalogue enforces so the RAG never has to:

* **No raw query language.** Every parameter is typed; the model picks a tool
  and fills arguments, the application builds the query.
* **Scope wins.** When ``scope["fabs"]`` is non-empty it overrides whatever
  fab the model wrote. Empty means unrestricted (user-confirmed 2026-09-19),
  and the model is expected to ask the user which fab in conversation.
* **Aggregates before rows.** The goal is time-ranged reports, not single
  lookups the pages already serve, so the first tools are the trend and
  summary functions the pages draw from. Raw listings wait.
* **Results are dataframe dicts** (``columns`` + ``rows`` of JSON scalars),
  the repo's own convention, capped at :data:`ROW_LIMIT` rows for the screen.
  The cap is about readability, not the model's context (256K).

Failures propagate as exceptions in the same vocabulary ``agent_query``
already raises (``PermissionError`` / ``TimeoutError`` / anything else), so
the RAG needs no new translation. A tool failure is not a turn failure: the
RAG may catch it, report it in ``tool_traces`` with ``status: "error"`` and
keep answering.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

from backend.chat.contracts import AccessScope

__all__ = ["ROW_LIMIT", "TOOLS", "DataTool", "ToolResult", "describe"]

# Rows a table attachment carries. OFFICE-VERIFY against real payload sizes;
# the letter promised the office would move it once a report has been seen.
ROW_LIMIT = 200

_Scalar = str | int | float | bool | None


class ToolResult(TypedDict):
    """A dataframe dict. ``rows`` are positional against ``columns``."""

    columns: list[str]
    rows: list[list[_Scalar]]
    row_count: int  # before truncation
    truncated: bool


@dataclass(frozen=True)
class DataTool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema, OpenAI function-calling shape
    _run: Callable[[dict[str, Any], AccessScope], Sequence[Mapping[str, Any]]]

    def call(self, args: Mapping[str, Any] | None, scope: AccessScope) -> ToolResult:
        rows = self._run(dict(args or {}), scope)
        return _frame(rows)


def _frame(rows: Sequence[Mapping[str, Any]]) -> ToolResult:
    """Records → dataframe dict. Column order is the first record's key order.

    Nested values (lists, dicts) are dropped: an attachment cell is a scalar
    the screen can print, and a payload's ranking sub-lists belong to their
    own tool, not to a summary row.
    """
    if not rows:
        return {"columns": [], "rows": [], "row_count": 0, "truncated": False}
    columns = [
        key for key, value in rows[0].items() if not isinstance(value, (list, dict))
    ]
    kept = rows[:ROW_LIMIT]
    return {
        "columns": columns,
        "rows": [[_scalar(row.get(column)) for column in columns] for row in kept],
        "row_count": len(rows),
        "truncated": len(rows) > ROW_LIMIT,
    }


def _scalar(value: Any) -> _Scalar:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _fab_names(args: Mapping[str, Any], scope: AccessScope) -> tuple[str, ...] | None:
    """Scope overrides the model; an empty scope defers to the model; neither → all."""
    fabs = list(scope.get("fabs") or [])
    if not fabs:
        fabs = list(args.get("fab_names") or [])
    return tuple(fabs) or None


# Shared by every period tool: the pages' own argument shape, so the model
# can run two tools over one window without translating between them.
_PERIOD_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "start_date": {
            "type": "string",
            "description": "기간 시작일 YYYY-MM-DD (포함). 생략하면 데이터가 있는 마지막 날부터 뒤로 30일.",
        },
        "end_date": {
            "type": "string",
            "description": "기간 종료일 YYYY-MM-DD (포함). 생략하면 데이터가 있는 마지막 날.",
        },
        "tool_type": {
            "type": "string",
            "enum": ["cd-sem", "hv-sem"],
            "description": "장비 계열. 사용자가 말하지 않으면 cd-sem.",
        },
        "fab_names": {
            "type": "array",
            "items": {"type": "string"},
            "description": "fab 이름 목록 (예: M14, M16). 사용자 권한 범위가 있으면 그것이 우선한다.",
        },
        "lot_cd": {
            "type": "string",
            "description": "특정 device(lot code)로 좁힐 때만.",
        },
    },
    "required": [],
}


def _period_args(args: Mapping[str, Any], scope: AccessScope) -> dict[str, Any]:
    return {
        "tool_type": args.get("tool_type") or "cd-sem",
        "fab_names": _fab_names(args, scope),
        "start_date": args.get("start_date") or None,
        "end_date": args.get("end_date") or None,
    }


def _recipe_tat_daily_trend(args: dict[str, Any], scope: AccessScope):
    from backend.ebeam.recipe_tat import data

    period = _period_args(args, scope)
    return data.get_daily_trend(
        period["tool_type"],
        period["fab_names"],
        period["start_date"],
        period["end_date"],
        args.get("lot_cd") or None,
    )


def _fail_issue_summary(args: dict[str, Any], scope: AccessScope):
    from backend.ebeam.fail_issue import data

    period = _period_args(args, scope)
    summary = data.get_summary(
        period["tool_type"],
        period["fab_names"],
        period["start_date"],
        period["end_date"],
        args.get("lot_cd") or None,
    )
    # One-row table: the payload's scalar fields. Its ranking sub-lists are
    # dropped by _frame on purpose (see there).
    return [summary]


def _fail_issue_daily_trend(args: dict[str, Any], scope: AccessScope):
    from backend.ebeam.fail_issue import data

    period = _period_args(args, scope)
    return data.get_daily_trend(
        period["tool_type"],
        period["fab_names"],
        period["start_date"],
        period["end_date"],
        args.get("lot_cd") or None,
    )


TOOLS: dict[str, DataTool] = {
    tool.name: tool
    for tool in (
        DataTool(
            name="recipe_tat_daily_trend",
            description=(
                "Recipe TAT(측정 소요시간) 일별 추세. 기간 안의 날짜별 총 측정시간(초)과 "
                "실행 횟수를 돌려준다. 장비 부하·처리량이 기간 동안 어떻게 움직였는지 "
                "볼 때 쓴다. Daily recipe turnaround: per-day total measurement "
                "seconds and execution count over a period."
            ),
            parameters=_PERIOD_PARAMETERS,
            _run=_recipe_tat_daily_trend,
        ),
        DataTool(
            name="fail_issue_summary",
            description=(
                "기간 전체의 측정 실패 요약 한 줄: 총 실행, align 실패 건수/율, "
                "meas 실패 건수/율, 장비·recipe·lot 수. 기간의 이상 상황 규모를 한 번에 "
                "볼 때 쓴다. One-row failure summary for a period: executions, align/meas "
                "fail counts and rates, distinct equipment/recipes/lots."
            ),
            parameters=_PERIOD_PARAMETERS,
            _run=_fail_issue_summary,
        ),
        DataTool(
            name="fail_issue_daily_trend",
            description=(
                "측정 실패 일별 추세: 날짜별 실행 수, align 실패 수, meas 실패 수. "
                "실패가 기간 중 언제 늘었는지 볼 때 쓴다. Daily failure trend: per-day "
                "executions, align failures and measurement failures."
            ),
            parameters=_PERIOD_PARAMETERS,
            _run=_fail_issue_daily_trend,
        ),
    )
}


def describe() -> list[str]:
    """One line per tool, for the contract runner's report."""
    lines = [f"  data tools {len(TOOLS)} (backend.chat.data_tools.TOOLS), "
             f"rows capped at {ROW_LIMIT}"]
    for tool in TOOLS.values():
        params = ", ".join(tool.parameters["properties"])
        lines.append(f"             {tool.name}({params})")
    return lines
