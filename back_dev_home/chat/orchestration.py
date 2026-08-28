"""Application-owned orchestration for persisted chat turns."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from back_dev_home.chat import config, conversation_log, data
from back_dev_home.chat.contracts import Message
from back_dev_home.chat.knowledge import data as knowledge_data
from back_dev_home.chat.runtime import data as runtime_data
from back_dev_home.chat.runtime.contracts import RuntimeRequest, RuntimeResult
from back_dev_home.chat.scope import data as scope_data
from back_dev_home.chat.scope.contracts import ScopeDecision
from back_dev_home.chat.scope.contracts import ScopeUnavailable


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
        conversation_recorder: Callable[..., None] = conversation_log.record_turn,
        query_rewriter: Callable[[str], str] = knowledge_data.rewrite_query,
        follow_up_generator: Callable[
            [str, str, list], list[str]
        ] = knowledge_data.generate_follow_ups,
    ) -> None:
        self._store = store
        self._scope_classifier = scope_classifier
        self._runtime_invoker = runtime_invoker
        self._model_finder = model_finder
        self._runtime_name_finder = runtime_name_finder
        self._conversation_recorder = conversation_recorder
        self._query_rewriter = query_rewriter
        self._follow_up_generator = follow_up_generator

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

        is_agent = self._runtime_name_finder() == "agent"
        if is_agent:
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
        if decision["status"] == "mixed" and not (
            decision["supported_query"] or ""
        ).strip():
            raise ScopeUnavailable(
                "A mixed scope decision must include a nonempty supported_query."
            )
        self._store.set_scope_decision(thread_id, request_id, decision)

        if decision["status"] in {"out_of_scope", "unsafe"}:
            assistant = self._store.complete_turn(
                thread_id,
                request_id,
                self._scope_rejection_result(),
            )
            self._record_conversation(
                user_id,
                thread["model"],
                user_message["content"],
                assistant,
                decision,
                tool_call_count=0,
            )
            return assistant

        persisted = self._store.get_thread(user_id, thread_id)
        if persisted is None:
            raise ThreadNotFound("thread not found")
        # The question the runtime actually answers: the supported clause for
        # a mixed turn, else the user's words. Rewrite and follow-ups are RAG
        # calls, so they run only where retrieval runs — agent mode. A rewrite
        # failure fails the turn (raw-question retrieval would look like a
        # working answer with worse recall); the user turn stays for retry.
        question = (
            decision["supported_query"]
            if decision["status"] == "mixed"
            else user_message["content"]
        )
        rewrite = self._rewrite(question) if is_agent else None
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
            "rewrite": rewrite,
        }
        result = self._runtime_invoker(runtime_request)
        result["rewrite"] = rewrite
        result["follow_ups"] = (
            self._follow_ups(question, result["content"], result["sources"])
            if is_agent
            else []
        )
        if decision["status"] == "mixed":
            result["content"] = f"{MIXED_SCOPE_NOTICE}\n\n{result['content']}"
        assistant = self._store.complete_turn(thread_id, request_id, result)
        self._record_conversation(
            user_id,
            thread["model"],
            user_message["content"],
            assistant,
            decision,
            tool_call_count=len(result["tool_traces"]),
        )
        return assistant

    def _rewrite(self, question: str) -> str | None:
        rewritten = self._query_rewriter(question)
        return rewritten if rewritten != question else None

    def _follow_ups(self, question: str, answer: str, sources: list) -> list[str]:
        # Suggestions are decoration on a turn that already succeeded; a RAG
        # failure here costs the chips, never the answer — same policy as the
        # conversation record below.
        try:
            return list(self._follow_up_generator(question, answer, sources))
        except Exception:
            logging.getLogger("skewnono.chat").exception(
                "failed to generate chat follow-up questions"
            )
            return []

    def _record_conversation(
        self,
        user_id: str,
        thread_model: str,
        user_content: str,
        assistant: Message,
        decision: ScopeDecision,
        *,
        tool_call_count: int,
    ) -> None:
        # The conversation record is telemetry riding on a turn that already
        # succeeded; a recorder failure costs the record, never the response.
        try:
            self._conversation_recorder(
                user_id=user_id,
                thread_model=thread_model,
                user_content=user_content,
                assistant=assistant,
                decision=decision,
                tool_call_count=tool_call_count,
            )
        except Exception:
            logging.getLogger("skewnono.chat").exception(
                "failed to record chat conversation turn"
            )

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
            "rewrite": None,
            "follow_ups": [],
        }


orchestrator = ChatOrchestrator()
