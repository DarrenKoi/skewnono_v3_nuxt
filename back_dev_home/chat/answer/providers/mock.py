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

from back_dev_home.chat.answer.contracts import AnswerResult
from back_dev_home.chat.contracts import AccessScope
from back_dev_home.chat.answer.providers import corpus


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

    if sources:
        cited = "\n".join(
            f"- {hit['title']} ({hit['locator']})" for hit in sources
        )
        content = f"찾은 근거로 답변합니다.\n\n{cited}"
    else:
        content = _NO_HIT_ANSWER
    return {
        "content": content,
        "sources": sources,
        "follow_ups": corpus.generate_follow_ups(question, content, sources),
        "rewrite": rewritten if rewritten != question else None,
        "tool_traces": traces,
        "prompt_tokens": None,
        "completion_tokens": None,
    }
