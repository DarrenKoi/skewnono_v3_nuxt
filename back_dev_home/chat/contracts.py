"""Stable response contracts for chat endpoints."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from back_dev_home.chat.knowledge.contracts import Evidence

__all__ = [
    "SourceRef",
    "ToolTrace",
    "TurnResult",
    "MessageFeedback",
    "Message",
    "ThreadSummary",
    "Thread",
    "ThreadDetail",
]


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
