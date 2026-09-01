"""Stable response contracts for chat endpoints.

One contracts module per feature. ``Evidence``, ``AccessScope`` and the
``Knowledge*`` error family used to live in ``chat/knowledge/contracts.py``,
back when retrieval was a seam this app owned. It has not been one since
2026-08-31 — the RAG answers the whole turn — so the package was a name that
no longer described anything, importing backwards into this module while
fourteen files reached through it for types that have nothing to do with
retrieval. They are here now; the package is gone.

The ``Knowledge*`` names are kept as-is: they are what the RAG adapter raises
and what ``routes.py`` already translates to 403/503/504. Renaming them is
churn for its own sake and would have to travel to the office in a letter.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

__all__ = [
    "AccessScope",
    "Evidence",
    "KnowledgeUnavailable",
    "KnowledgeTimeout",
    "KnowledgeDenied",
    "SourceRef",
    "ToolTrace",
    "TurnResult",
    "MessageFeedback",
    "Message",
    "ThreadSummary",
    "Thread",
    "ThreadDetail",
]


class AccessScope(TypedDict):
    """Who is asking, as the retrieval filter the RAG applies at query time."""

    user_id: str
    groups: list[str]
    fabs: list[str]


class Evidence(TypedDict):
    """One cited chunk. Field rules: docs/datatables/hitachi/chat_rag_contract.txt."""

    source_id: str
    source_type: Literal["manual", "meeting", "email", "report"]
    title: str
    snippet: str
    revision: str | None
    occurred_at: str | None
    section: str | None
    page: int | None
    region: str | None
    locator: str | None
    # Opaque figure token, never a storage key: the server owns the bucket,
    # prefix and extension. None for text and table evidence.
    figure_id: str | None
    score: float | None


class KnowledgeUnavailable(RuntimeError):
    """The answer seam could not answer at all — routes translate this to 503."""


class KnowledgeTimeout(RuntimeError):
    """The turn exceeded its budget — routes translate this to 504."""


class KnowledgeDenied(RuntimeError):
    """Access scope refused the question — routes translate this to 403."""


class SourceRef(Evidence):
    pass


class ToolTrace(TypedDict):
    """One retrieval step the RAG reports back with its answer."""

    tool_name: str
    query: str
    result_count: int
    duration_ms: int
    status: Literal["success", "empty", "denied", "timeout", "error"]


class TurnResult(TypedDict):
    """What the orchestrator hands the store to persist as the assistant turn.

    ``runtime`` names which of the two paths produced it: the RAG answered, or
    the scope policy refused before anything was asked. There is no third
    value — chat has no LLM of its own.
    """

    content: str
    runtime: Literal["rag", "scope_rejection"]
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int
    sources: list[SourceRef]
    tool_traces: list[ToolTrace]
    rewrite: NotRequired[str | None]
    follow_ups: NotRequired[list[str]]


class MessageFeedback(TypedDict):
    rating: Literal["up", "down"]
    reasons: list[Literal[
        "incorrect",
        "insufficient_evidence",
        "wrong_source",
        "outdated",
        "unclear",
        "incorrect_scope_rejection",
        "other",
    ]]
    comment: str | None
    updated_at: str


class Message(TypedDict):
    id: str
    thread_id: str
    request_id: str | None
    role: str
    content: str
    model: str | None
    runtime: Literal["rag", "scope_rejection"] | None
    scope_status: Literal["in_scope", "mixed", "out_of_scope", "unsafe"] | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    sources: list[SourceRef]
    feedback: MessageFeedback | None
    # The RAG's retrieval expansion of the question this turn answered (None
    # when rejected or unchanged) and its suggested next questions. Both live
    # on the assistant turn; user turns carry None / [].
    rewrite: str | None
    follow_ups: list[str]
    created_at: str


class ThreadSummary(TypedDict):
    id: str
    title: str
    updated_at: str


class Thread(TypedDict):
    """A conversation. It names no model and no system prompt: both belong to
    the RAG, which owns the LLM call this app never makes."""

    id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str


class ThreadDetail(Thread):
    messages: list[Message]
