"""Home stand-in for the RAG's ``agent_query`` — the whole turn in one call.

Composes the existing knowledge mocks (search, rewrite, follow-ups) so the
answer path exercises the same fixtures the tool assembly used, and the
result carries the agreed shape: content, Evidence sources (≤5, the
application cap), 3~5 follow-ups, rewrite None-when-unchanged, tool traces,
token counts None (the office side may add them later — chat handles both).
Deliberate difference from the office: content is a fixed template over the hits, not
an LLM answer; only the shape is contractual.
"""

from __future__ import annotations

import time

from back_dev_home.chat.answer.contracts import AnswerResult
from back_dev_home.chat.knowledge.contracts import AccessScope
from back_dev_home.chat.knowledge.providers import mock as knowledge


_NO_HIT_ANSWER = (
    "관련 매뉴얼 근거를 찾지 못했습니다. 장비명이나 오류 코드를 함께 적어 "
    "다시 질문해 주세요."
)


def answer_question(
    question: str,
    messages: list[dict],
    scope: AccessScope,
) -> AnswerResult:
    del messages  # the mock answers from the question alone
    started = time.perf_counter()
    rewritten = knowledge.rewrite_query(question)
    sources = knowledge.search_manuals(rewritten, None, scope, 5)
    duration_ms = int((time.perf_counter() - started) * 1000)
    if sources:
        cited = "\n".join(
            f"- {hit['title']} ({hit['locator']})" for hit in sources
        )
        content = f"매뉴얼 근거로 답변합니다.\n\n{cited}"
    else:
        content = _NO_HIT_ANSWER
    return {
        "content": content,
        "sources": sources,
        "follow_ups": knowledge.generate_follow_ups(question, content, sources),
        "rewrite": rewritten if rewritten != question else None,
        "tool_traces": [
            {
                "tool_name": "search_manuals",
                "query": rewritten,
                "result_count": len(sources),
                "duration_ms": duration_ms,
                "status": "success" if sources else "empty",
            }
        ],
        "prompt_tokens": None,
        "completion_tokens": None,
    }
