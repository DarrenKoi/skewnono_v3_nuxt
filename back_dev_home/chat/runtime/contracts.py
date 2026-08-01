"""Stable contracts for chat runtimes."""

from typing import Literal, TypedDict

from back_dev_home.chat.contracts import SourceRef
from back_dev_home.chat.knowledge.contracts import AccessScope
from back_dev_home.chat.scope.contracts import ScopeDecision


class RuntimeRequest(TypedDict):
    request_id: str
    thread_id: str
    access_scope: AccessScope
    model: str
    system_prompt: str | None
    messages: list[dict]
    scope_decision: ScopeDecision


class ToolTrace(TypedDict):
    tool_name: str
    query: str
    result_count: int
    duration_ms: int
    status: Literal["success", "empty", "denied", "timeout", "error"]


class RuntimeResult(TypedDict):
    content: str
    runtime: Literal["direct", "agent", "scope_rejection"]
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int
    sources: list[SourceRef]
    tool_traces: list[ToolTrace]


class RuntimeUnavailable(RuntimeError):
    pass


class RuntimeTimeout(RuntimeError):
    pass


class RuntimeLimitExceeded(RuntimeError):
    pass


class RuntimeDenied(RuntimeError):
    pass
