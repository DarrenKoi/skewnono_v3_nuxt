"""Home stand-in for the RAG's ``agent_query`` — the whole turn in one call.

Composes the existing knowledge mocks (search, rewrite, follow-ups) so the
answer path exercises the same fixtures the tool assembly used, and the
result carries the agreed shape: content, Evidence sources (≤5, the
application cap), 3~5 follow-ups, rewrite None-when-unchanged, tool traces,
token counts None (the office side may add them later — chat handles both).
Deliberate difference from the office: content is a fixed template over the hits, not
an LLM answer; only the shape is contractual.

**All four sources, not manuals only (2026-09-01).** ``source_type`` is one of
manual / meeting / email / report, and the office agent reaches all four. This
mock searched ``manuals`` alone, which quietly made two office-normal states
unreachable at home: a citation with ``figure_id: None`` (only the non-manual
fixtures have one) and a mixed-source answer. The figure-less citation is the
COMMON case at the office — text and table chunks carry no figure — so the UI
path for it was the one path no home session could see.
"""

from __future__ import annotations

import time

from backend.chat import data_tools
from backend.chat.answer.contract import AnswerResult
from backend.chat.contracts import AccessScope
from backend.chat.answer.providers import corpus


_NO_HIT_ANSWER = (
    "관련 근거를 찾지 못했습니다. 장비명이나 오류 코드를 함께 적어 "
    "다시 질문해 주세요."
)

# The four retrieval tools, in the order their traces are reported. Named as
# (tool_name, function) because the trace carries the tool's own name and the
# office reports one trace per call it made.
_SEARCHES = (
    ("search_manuals", corpus.search_manuals),
    ("search_meeting_summaries", corpus.search_meeting_summaries),
    ("search_emails", corpus.search_emails),
    ("search_reports", corpus.search_reports),
)

# The application cap, same as the office adapter's _RESULT_LIMIT.
_RESULT_LIMIT = 5

# Words that make the mock reach for a data tool, the way the office model
# would on a report-style question. Deliberately crude: the mock has no LLM,
# and the point is only that a home session can SEE an attachment render.
_TREND_WORDS = ("추세", "trend", "tat", "처리량")
_FAIL_WORDS = ("실패", "fail", "이상", "abnormal")


def _data_attachments(question: str, scope: AccessScope) -> tuple[list[dict], list[dict]]:
    """(attachments, traces) for a question that asks about a period.

    Runs the catalogue exactly as the RAG would — ``TOOLS[name].call(args,
    scope)`` — so the mock exercises the real tool path, mock ``data.py`` and
    all. Last 30 days, the tools' own default window.
    """
    lowered = question.lower()
    wanted: list[tuple[str, str, dict | None]] = []
    if any(word in lowered for word in _TREND_WORDS):
        wanted.append((
            "recipe_tat_daily_trend",
            "최근 30일 Recipe TAT 일별 추세 (CD-SEM)",
            {"type": "line", "x": "date", "y": ["total_meastime"], "series_by": None},
        ))
    if any(word in lowered for word in _FAIL_WORDS):
        wanted.append((
            "fail_issue_summary",
            "최근 30일 측정 실패 요약 (CD-SEM)",
            None,
        ))
        wanted.append((
            "fail_issue_daily_trend",
            "최근 30일 실패 일별 추세 (CD-SEM)",
            {"type": "bar", "x": "date", "y": ["align_fail_count", "meas_fail_count"],
             "series_by": None},
        ))
    attachments: list[dict] = []
    traces: list[dict] = []
    for name, title, chart in wanted:
        started = time.perf_counter()
        result = data_tools.TOOLS[name].call({}, scope)
        traces.append({
            "tool_name": name,
            "query": "{}",
            "result_count": result["row_count"],
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "status": "success" if result["rows"] else "empty",
        })
        attachments.append({
            "kind": "chart" if chart else "table",
            "title": title,
            "tool_name": name,
            "data": result,
            "chart": chart,
        })
    return attachments, traces


def answer_question(
    question: str,
    messages: list[dict],
    scope: AccessScope,
) -> AnswerResult:
    del messages  # the mock answers from the question alone
    rewritten = corpus.rewrite_query(question)

    hits: list = []
    traces: list[dict] = []
    for tool_name, search in _SEARCHES:
        started = time.perf_counter()
        found = search(rewritten, None, scope, _RESULT_LIMIT)
        traces.append({
            "tool_name": tool_name,
            "query": rewritten,
            "result_count": len(found),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "status": "success" if found else "empty",
        })
        hits.extend(found)

    # Each search sorts within its own source; merging needs one order across
    # them, on the same key so the tiebreak stays deterministic.
    hits.sort(key=lambda hit: (-float(hit["score"] or 0), hit["source_id"]))
    sources = hits[:_RESULT_LIMIT]

    attachments, data_traces = _data_attachments(question, scope)
    traces.extend(data_traces)

    if sources:
        cited = "\n".join(
            f"- {hit['title']} ({hit['locator']})" for hit in sources
        )
        content = f"찾은 근거로 답변합니다.\n\n{cited}"
    elif attachments:
        # A report-shaped answer: headings and a list, the markdown the office
        # model writes and the renderer must therefore handle.
        titles = "\n".join(f"- {item['title']}" for item in attachments)
        content = (
            "## 기간 요약\n\n요청하신 기간의 데이터를 아래 표와 차트로 정리했습니다.\n\n"
            f"### 포함된 자료\n\n{titles}"
        )
    else:
        content = _NO_HIT_ANSWER
    return {
        "content": content,
        "sources": sources,
        "follow_ups": corpus.generate_follow_ups(question, content, sources),
        "rewrite": rewritten if rewritten != question else None,
        "tool_traces": traces,
        "attachments": attachments,
        "prompt_tokens": None,
        "completion_tokens": None,
    }
