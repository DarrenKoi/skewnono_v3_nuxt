"""Shared types for the msr_image feature (phase-agnostic)."""

from typing import Literal, NamedTuple, TypedDict


class ImageLocator(NamedTuple):
    eqp_ip: str
    class_name: str
    msr: str
    name: str


class FetchedImage(NamedTuple):
    data: bytes
    content_type: str
    cond: str | None


class ImageListResponse(TypedDict):
    msr: str
    class_name: str
    images: list[str]
    total: int


class DownloadFailure(TypedDict):
    name: str
    error: str


class DownloadJobStatus(TypedDict):
    job_id: str
    status: Literal["running", "done", "error"]
    done: int
    total: int
    ok: int
    ng: int
    failures: list[DownloadFailure]
