"""Stable contract for the answer seam — one call answers a whole turn.

Agreed with the RAG side 2026-08-31
(``chat/docs/2026-08-31-chat-to-rag-answer-contract-agreed.md``): the ``rag``
provider is a thin bridge to ``skewnono_rag.retrieve.agent.agent_query`` and
this shape mirrors what that returns. Errors reuse the knowledge family —
routes already translate them (403/503/504).
"""

from typing import TypedDict

from back_dev_home.chat.contracts import Evidence, ToolTrace


class AnswerResult(TypedDict):
    content: str
    sources: list[Evidence]
    follow_ups: list[str]
    rewrite: str | None
    tool_traces: list[ToolTrace]
    prompt_tokens: int | None
    completion_tokens: int | None
