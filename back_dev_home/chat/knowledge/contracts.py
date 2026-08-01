"""Stable contracts for chat knowledge providers."""

from typing import Literal, TypedDict


class AccessScope(TypedDict):
    user_id: str
    groups: list[str]
    fabs: list[str]


class Evidence(TypedDict):
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
    score: float | None


class KnowledgeUnavailable(RuntimeError):
    pass


class KnowledgeTimeout(RuntimeError):
    pass


class KnowledgeDenied(RuntimeError):
    pass
