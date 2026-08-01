"""Stable contracts for chat scope providers."""

from typing import Literal, TypedDict


class ScopeDecision(TypedDict):
    status: Literal["in_scope", "mixed", "out_of_scope", "unsafe"]
    reason_code: str
    supported_query: str | None


class ScopeUnavailable(RuntimeError):
    pass
