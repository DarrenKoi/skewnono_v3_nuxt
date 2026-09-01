"""Application-owned orchestration for persisted chat turns.

One turn is: replay a completed request id, classify scope, ask the answer
seam, persist, log. The answer seam is the RAG (or its home mock), which
answers the WHOLE turn — rewrite and follow-up suggestions arrive inside its
result rather than being separate calls this module makes.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from back_dev_home.chat import conversation_log
from back_dev_home.chat import store as chat_store
from back_dev_home.chat.answer import data as answer_data
from back_dev_home.chat.answer.contract import AnswerResult
from back_dev_home.chat.contracts import Message, TurnResult
from back_dev_home.chat.contracts import AccessScope
from back_dev_home.chat.scope import policy as scope_policy
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


class ChatOrchestrator:
    """Coordinate idempotency, scope, the answer call, and persistence."""

    def __init__(
        self,
        store: Any = chat_store,
        scope_classifier: Callable[[str], ScopeDecision] = scope_policy.classify,
        answerer: Callable[
            [str, list[dict], AccessScope], AnswerResult
        ] = answer_data.answer_question,
        *,
        conversation_recorder: Callable[..., None] = conversation_log.record_turn,
    ) -> None:
        self._store = store
        self._scope_classifier = scope_classifier
        self._answerer = answerer
        self._conversation_recorder = conversation_recorder

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
                user_message["content"],
                assistant,
                decision,
                tool_call_count=0,
            )
            return assistant

        persisted = self._store.get_thread(user_id, thread_id)
        if persisted is None:
            raise ThreadNotFound("thread not found")
        # The question the answer seam is asked: the supported clause for a
        # mixed turn, else the user's words. History is prior turns only —
        # the current question travels alone (agreed RAG contract).
        question = (
            decision["supported_query"]
            if decision["status"] == "mixed"
            else user_message["content"]
        )
        history = self._history(persisted["messages"], request_id)
        access_scope: AccessScope = {
            "user_id": user_id,
            "groups": [],
            "fabs": [],
        }
        started = time.perf_counter()
        answer = self._answerer(question, history, access_scope)
        result = self._turn_result(answer, started)
        if decision["status"] == "mixed":
            result["content"] = f"{MIXED_SCOPE_NOTICE}\n\n{result['content']}"
        assistant = self._store.complete_turn(thread_id, request_id, result)
        self._record_conversation(
            user_id,
            user_message["content"],
            assistant,
            decision,
            tool_call_count=len(result["tool_traces"]),
        )
        return assistant

    @staticmethod
    def _turn_result(answer: AnswerResult, started: float) -> TurnResult:
        """Wrap what the RAG returned in what the store persists.

        ``model`` is None on purpose: the RAG picks and calls its own model
        and does not report which. Latency is measured here rather than taken
        from the answer because this is the number the user waited.
        """
        return {
            "content": answer["content"],
            "runtime": "rag",
            "model": None,
            "prompt_tokens": answer["prompt_tokens"],
            "completion_tokens": answer["completion_tokens"],
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "sources": answer["sources"],
            "tool_traces": answer["tool_traces"],
            "rewrite": answer["rewrite"],
            "follow_ups": answer["follow_ups"],
        }

    def _record_conversation(
        self,
        user_id: str,
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
    def _history(messages: list[Message], request_id: str) -> list[dict]:
        """Prior turns, without the question being asked now.

        The current user turn is already persisted when this runs (so a retry
        of the same request id replays instead of re-asking), which is exactly
        the message the contract says must NOT be duplicated into the history.
        Dropping it by request id also drops the mixed-scope substitution
        problem: the clause the RAG is asked travels in ``question``.
        """
        return [
            {"role": message["role"], "content": message["content"]}
            for message in messages
            if message["request_id"] != request_id
        ]

    @staticmethod
    def _scope_rejection_result() -> TurnResult:
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
