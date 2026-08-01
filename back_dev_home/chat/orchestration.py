"""Application-owned orchestration for persisted chat turns."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from back_dev_home.chat import config, data
from back_dev_home.chat.contracts import Message
from back_dev_home.chat.runtime import data as runtime_data
from back_dev_home.chat.runtime.contracts import RuntimeRequest, RuntimeResult
from back_dev_home.chat.scope import data as scope_data
from back_dev_home.chat.scope.contracts import ScopeDecision


SCOPE_REFUSAL = (
    "이 채팅은 장비 매뉴얼, E-beam 계측, 팀 회의·이메일·보고서 관련 질문을 "
    "지원합니다. 해당 범위의 질문으로 다시 요청해 주세요."
)
MIXED_SCOPE_NOTICE = (
    "지원 범위를 벗어난 부분은 제외하고, 지원되는 업무 관련 질문에만 답변했습니다."
)


class ThreadNotFound(LookupError):
    """Raised when a thread is absent or is not owned by the caller."""


class ModelDoesNotSupportTools(ValueError):
    """Raised before persistence when agent mode cannot use the thread model."""


class ChatOrchestrator:
    """Coordinate idempotency, scope, runtime invocation, and persistence."""

    def __init__(
        self,
        store: Any = data,
        scope_classifier: Callable[[str], ScopeDecision] = scope_data.classify,
        runtime_invoker: Callable[
            [RuntimeRequest], RuntimeResult
        ] = runtime_data.invoke,
        model_finder: Callable[[str], dict | None] = config.find_model,
        *,
        runtime_name_finder: Callable[[], str] = config.get_runtime_name,
    ) -> None:
        self._store = store
        self._scope_classifier = scope_classifier
        self._runtime_invoker = runtime_invoker
        self._model_finder = model_finder
        self._runtime_name_finder = runtime_name_finder

    def send_message(
        self,
        user_id: str,
        thread_id: str,
        content: str,
        request_id: str,
    ) -> Message:
        """Run one persisted turn, replaying completed request IDs."""
        thread = self._store.get_thread(user_id, thread_id)
        if thread is None:
            raise ThreadNotFound("thread not found")

        if self._runtime_name_finder() == "agent":
            model = self._model_finder(thread["model"])
            if model is None or not model.get("supports_tools", False):
                raise ModelDoesNotSupportTools(
                    "the selected model does not support agent tools"
                )

        completed = self._store.get_message_by_request(
            thread_id, request_id, "assistant"
        )
        if completed is not None:
            return completed

        user_message = self._store.append_user_message(thread_id, content, request_id)
        decision = self._scope_classifier(user_message["content"])
        self._store.set_scope_decision(thread_id, request_id, decision)

        if decision["status"] in {"out_of_scope", "unsafe"}:
            return self._store.complete_turn(
                thread_id,
                request_id,
                self._scope_rejection_result(),
            )

        persisted = self._store.get_thread(user_id, thread_id)
        if persisted is None:
            raise ThreadNotFound("thread not found")
        runtime_request: RuntimeRequest = {
            "request_id": request_id,
            "thread_id": thread_id,
            "access_scope": {
                "user_id": user_id,
                "groups": [],
                "fabs": [],
            },
            "model": thread["model"],
            "system_prompt": thread.get("system_prompt"),
            "messages": self._runtime_messages(
                persisted["messages"], request_id, decision
            ),
            "scope_decision": decision,
        }
        result = self._runtime_invoker(runtime_request)
        if decision["status"] == "mixed":
            result["content"] = f"{MIXED_SCOPE_NOTICE}\n\n{result['content']}"
        return self._store.complete_turn(thread_id, request_id, result)

    @staticmethod
    def _runtime_messages(
        messages: list[Message],
        request_id: str,
        decision: ScopeDecision,
    ) -> list[dict]:
        runtime_messages = []
        for message in messages:
            content = message["content"]
            if (
                decision["status"] == "mixed"
                and message["role"] == "user"
                and message["request_id"] == request_id
                and decision["supported_query"]
            ):
                content = decision["supported_query"]
            runtime_messages.append({"role": message["role"], "content": content})
        return runtime_messages

    @staticmethod
    def _scope_rejection_result() -> RuntimeResult:
        return {
            "content": SCOPE_REFUSAL,
            "runtime": "scope_rejection",
            "model": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "latency_ms": 0,
            "sources": [],
            "tool_traces": [],
        }


orchestrator = ChatOrchestrator()
