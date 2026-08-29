"""Stable response contracts for access_control endpoints."""

from __future__ import annotations

from typing import TypedDict


__all__ = [
    "ExceptionRow",
    "DeniedRow",
    "ExceptionListResponse",
    "DeniedListResponse",
]


class ExceptionRow(TypedDict):
    user_id: str
    granted_at: str


class DeniedRow(TypedDict):
    user_id: str
    last_denied_at: str


# list_exceptions()/list_denied() each return a bare list — no wrapping
# object. routes.py assembles both into the GET /api/admin/access response.
ExceptionListResponse = list[ExceptionRow]
DeniedListResponse = list[DeniedRow]
