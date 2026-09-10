"""Stable response contracts for admin_logs endpoints."""

from __future__ import annotations

from typing import Any, TypedDict


__all__ = ["LogItem", "LogQueryResponse", "NamedLogQueryResponse"]


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


class NamedLogQueryResponse(LogQueryResponse):
    """A log page with its employee numbers expanded into names.

    What the ROUTE returns; the providers return ``LogQueryResponse``. The
    logging store records employee numbers and no names, so LogItem must not
    promise one — see activity/routes.py, which split the same way.

    ``members`` is a sibling map rather than a field on each row for two
    reasons. A 200-row page usually holds fewer than ten distinct users, so
    per-row names would repeat the same string dozens of times. And LogItem
    already carries the verbatim source document as ``raw`` — an ``emp_nm``
    sitting beside a ``raw`` that has no such field would read as an
    OpenSearch field it is not.

    Employee numbers the directory could not name are OMITTED rather than
    mapped to None: the caller falls back to the number, so an entry would say
    nothing, and the value type stays a plain str.
    """

    members: dict[str, str]
