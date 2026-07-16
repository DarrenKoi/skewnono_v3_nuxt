"""Stable response contracts for admin_logs endpoints."""

from __future__ import annotations

from typing import Any, TypedDict


__all__ = ["LogItem", "LogQueryResponse"]


class LogItem(TypedDict, total=False):
    id: str
    index: str
    timestamp: str | None
    level: str | None
    event: str | None
    logger: str | None
    user_id: str | None
    method: str | None
    path: str | None
    status: int | None
    latency_ms: int | None
    feature: str | None
    message: str | None
    exception: dict[str, Any] | None
    raw: dict[str, Any]


class LogQueryResponse(TypedDict):
    generated_at: str
    page: int
    page_size: int
    total: int
    filters: dict[str, Any]
    items: list[LogItem]
