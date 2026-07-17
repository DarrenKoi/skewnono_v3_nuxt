"""Stable response contracts for chat endpoints."""

from __future__ import annotations

from typing import TypedDict

__all__ = ["ModelInfo", "Message", "ThreadSummary", "Thread", "ThreadDetail"]


class ModelInfo(TypedDict):
    id: str
    label: str


class Message(TypedDict):
    id: str
    thread_id: str
    role: str
    content: str
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
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
