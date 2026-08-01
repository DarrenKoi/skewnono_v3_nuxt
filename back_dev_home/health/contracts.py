"""Stable response contracts for health endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = [
    "ServiceHealth",
    "ServicesHealthResponse",
    "JobRunRecord",
    "JobsHealthResponse",
]


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


class JobRunRecord(TypedDict, total=False):
    ts: str
    job: str
    event: Literal["start", "end", "error", "skip", "missed"]
    duration_ms: int
    error: str


class JobsHealthResponse(TypedDict):
    limit: int
    records: list[JobRunRecord]
