"""Stable response contracts for admin_logs endpoints."""

from __future__ import annotations

from typing import Any, TypedDict


__all__ = ["LogItem", "LogQueryResponse"]


class LogItem(TypedDict):
    # Every key is always emitted by _item_from_hit(); values may be None for
    # source fields that are absent, but the key itself is a stable part of the
    # contract, so office payloads must carry all of them.
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
    # Last page the backend will serve: ceil(total / page_size) clamped to the
    # OpenSearch result window. The pager derives from this, never from its
    # own copy of the window constant.
    page_count: int
    filters: dict[str, Any]
    items: list[LogItem]
