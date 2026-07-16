"""Stable response contracts for announcements endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = ["Announcement", "AnnouncementsResponse"]


class Announcement(TypedDict, total=False):
    id: str
    level: Literal["info", "warning", "critical"]
    title: str
    body: str
    starts_at: str
    ends_at: str
    dismissible: bool


AnnouncementsResponse = list[Announcement]
