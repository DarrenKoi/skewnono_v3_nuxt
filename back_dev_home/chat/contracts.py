"""Stable response contracts for chat endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict

from back_dev_home.chat.knowledge.contracts import Evidence

__all__ = [
    "ModelInfo",
    "SourceRef",
    "MessageFeedback",
    "Message",
    "ThreadSummary",
    "Thread",
    "ThreadDetail",
]


class ModelInfo(TypedDict):
    id: str
    label: str
    supports_tools: bool
    supports_vision: bool


class SourceRef(Evidence):
    pass


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
    runtime: Literal["direct", "agent", "scope_rejection"] | None
    scope_status: Literal["in_scope", "mixed", "out_of_scope", "unsafe"] | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    sources: list[SourceRef]
    feedback: MessageFeedback | None
    # Agent-mode retrieval expansion of the question this turn answered
    # (None when direct, rejected, or unchanged) and the RAG's suggested
    # next questions (empty outside agent mode). Both live on the assistant
    # turn; user turns carry None / [].
    rewrite: str | None
    follow_ups: list[str]
    created_at: str


class ThreadSummary(TypedDict):
    id: str
    title: str
    model: str
    updated_at: str


class Thread(TypedDict):
    id: str
    user_id: str
    title: str
    model: str
    system_prompt: str | None
    created_at: str
    updated_at: str


class ThreadDetail(Thread):
    messages: list[Message]
