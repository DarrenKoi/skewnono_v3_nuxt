"""Stable response contracts for health endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = ["ServiceHealth", "ServicesHealthResponse"]


Status = Literal["up", "down"]


class ServiceHealth(TypedDict):
    id: str
    label: str
    status: Status
    latency_ms: int | None
    detail: str


class ServicesHealthResponse(TypedDict):
    checked_at: str
    services: list[ServiceHealth]
