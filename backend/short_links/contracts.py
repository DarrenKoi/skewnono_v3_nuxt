"""Stable response contract for short-link endpoints."""

from __future__ import annotations

from typing import TypedDict


__all__ = ["ShortLink"]


class ShortLink(TypedDict):
    # `code` is the short opaque id that appears in /s/<code>; `target` is the
    # root-relative in-app path it resolves to (already validated by
    # targets.normalize_target at mint time, so it is trusted on read).
    code: str
    target: str
    created_at: str
