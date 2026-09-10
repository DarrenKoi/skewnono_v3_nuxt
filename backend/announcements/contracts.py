"""Stable response contracts for announcements endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = ["Announcement", "AnnouncementsResponse"]


class _AnnouncementRequired(TypedDict):
    # Identity + display content: an announcement without them is unusable by
    # the frontend, so office payloads must carry all four.
    id: str
    level: Literal["info", "warning", "critical"]
    title: str
    body: str


class Announcement(_AnnouncementRequired, total=False):
    # Genuinely optional: dismissibility and time bounds. (Base-class + total
    # False is used instead of NotRequired because this module enables
    # `from __future__ import annotations`, under which NotRequired is not
    # recognized by TypedDict's required/optional-key computation.)
    dismissible: bool
    starts_at: str
    ends_at: str


AnnouncementsResponse = list[Announcement]
