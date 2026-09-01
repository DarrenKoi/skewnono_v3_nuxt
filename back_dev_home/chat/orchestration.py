"""Application-owned orchestration for persisted chat turns.

A turn is a **resource**, not a request. ``send_message`` classifies scope,
reserves the assistant row as ``pending`` and hands the answer to a background
worker; the SPA polls the thread until the row settles to ``done`` or
``failed``. The HTTP request is over in milliseconds.

Why the turn stopped being a request (2026-09-01): one answer may take the
whole budget, and uWSGI serves ``processes=4 x threads=4`` — sixteen slots for
the entire app. A turn holding one of them for four minutes cost 1/16th of the
site's capacity to display a spinner, and an overrun took the WHOLE worker
with it when harakiri fired, killing the three unrelated requests sharing it
(``wsgi.ini`` says so in its own comment). None of that was buying the user
anything: the RAG reports its tool traces with the answer, so there was
nothing to stream, and a reload lost the turn outright because the assistant
row was only written at the end.

The machinery was already here — ``request_id`` is a canonical UUID,
``append_user_message`` persists before the answer exists, and
``get_message_by_request`` replays. The store already modelled a turn with a
pending state; only the HTTP shape did not.

A scope rejection is answered inline. It costs no time, and making the SPA
poll for a verdict that was ready before the response was written would be a
round trip bought with nothing.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from back_dev_home.chat import conversation_log
from back_dev_home.chat import store as chat_store
from back_dev_home.chat.answer import data as answer_data
from back_dev_home.chat.answer.contract import AnswerResult
from back_dev_home.chat.contracts import (
    AccessScope,
    KnowledgeDenied,
    KnowledgeTimeout,
    Message,
    TurnResult,
)
from back_dev_home.chat.scope import policy as scope_policy
from back_dev_home.chat.scope.contracts import ScopeDecision, ScopeUnavailable


SCOPE_REFUSAL = (
    "이 채팅은 장비 매뉴얼, E-beam 계측, 팀 회의·이메일·보고서 관련 질문을 "
    "지원합니다. 해당 범위의 질문으로 다시 요청해 주세요."
)
MIXED_SCOPE_NOTICE = (
    "지원 범위를 벗어난 부분은 제외하고, 지원되는 업무 관련 질문에만 답변했습니다."
)

# Failure -> the code the SPA reads. Deliberately the strings routes.py already
# puts in an error body: a turn that fails inside the worker and one that fails
# before the response is written must not speak two vocabularies.
_FAILURE_CODES: tuple[tuple[type[Exception], str], ...] = (
    (KnowledgeDenied, "runtime_denied"),
    (KnowledgeTimeout, "gateway_timeout"),
)
_DEFAULT_FAILURE_CODE = "runtime_unavailable"


class ThreadNotFound(LookupError):
    """Raised when a thread is absent or is not owned by the caller."""


def _spawn_daemon(run: Callable[[], None]) -> None:
    """Run the turn off the request thread.

    A daemon thread rather than a queue consumed by an elected worker: the
    poll may land on any of the four uWSGI processes and reads the answer from
    SQLite either way, so there is nothing to route. Funnelling every turn
    through one elected worker would build a worse bottleneck than the one
    being removed.
    """
    threading.Thread(target=run, name="chat-turn", daemon=True).start()


class ChatOrchestrator:
    """Start a turn, hand it to a worker, and let the store carry the state."""

    def __init__(
        self,
        store: Any = chat_store,
        scope_classifier: Callable[[str], ScopeDecision] = scope_policy.classify,
        answerer: Callable[
            [str, list[dict], AccessScope], AnswerResult
        ] = answer_data.answer_question,
        *,
        conversation_recorder: Callable[..., None] = conversation_log.record_turn,
        spawn: Callable[[Callable[[], None]], None] = _spawn_daemon,
    ) -> None:
        self._store = store
        self._scope_classifier = scope_classifier
        self._answerer = answerer
        self._conversation_recorder = conversation_recorder
        self._spawn = spawn

    def send_message(
        self,
        user_id: str,
        thread_id: str,
        content: str,
        request_id: str,
    ) -> Message:
        """Start the turn for this request id and return it as it now stands.

        The result is ``pending`` when a worker was started here, and settled
        when the answer already existed or the scope gate refused. Callers
        distinguish the two by ``status``, never by which branch ran.
        """
        thread = self._store.get_thread(user_id, thread_id)
        if thread is None:
            raise ThreadNotFound("thread not found")

        settled = self._store.get_message_by_request(
            thread_id, request_id, "assistant"
        )
        if settled is not None and settled["status"] == "done":
            return settled

        user_message = self._store.append_user_message(thread_id, content, request_id)
        decision = self._scope_classifier(user_message["content"])
        if decision["status"] == "mixed" and not (
            decision["supported_query"] or ""
        ).strip():
            raise ScopeUnavailable(
                "A mixed scope decision must include a nonempty supported_query."
            )
        self._store.set_scope_decision(thread_id, request_id, decision)

        assistant, mine = self._store.begin_turn(thread_id, request_id)
        if not mine:
            # Another worker owns this turn — a retried POST joins it rather
            # than asking the RAG the same question a second time.
            return assistant

        if decision["status"] in {"out_of_scope", "unsafe"}:
            assistant = self._store.complete_turn(
                thread_id, request_id, self._scope_rejection_result()
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
        access_scope: AccessScope = {"user_id": user_id, "groups": [], "fabs": []}

        self._spawn(
            lambda: self._run_turn(
                user_id=user_id,
                thread_id=thread_id,
                request_id=request_id,
                question=question,
                history=history,
                access_scope=access_scope,
                decision=decision,
                user_content=user_message["content"],
            )
        )
        return assistant

    def _run_turn(
        self,
        *,
        user_id: str,
        thread_id: str,
        request_id: str,
        question: str,
        history: list[dict],
        access_scope: AccessScope,
        decision: ScopeDecision,
        user_content: str,
    ) -> None:
        """The whole answer, off the request thread. Never raises.

        Nothing is waiting on this call, so an exception escaping it would be
        a turn stuck at ``pending`` until the staleness clock expired — a
        four-minute wait for a failure the store could have recorded now.
        """
        started = time.perf_counter()
        try:
            answer = self._answerer(question, history, access_scope)
        except Exception as error:  # noqa: BLE001 — recorded on the row, not raised
            self._store.fail_turn(
                thread_id, request_id, _failure_code(error), str(error)
            )
            return

        try:
            result = self._turn_result(answer, started)
            if decision["status"] == "mixed":
                result["content"] = f"{MIXED_SCOPE_NOTICE}\n\n{result['content']}"
            assistant = self._store.complete_turn(thread_id, request_id, result)
        except Exception:
            logging.getLogger("skewnono.chat").exception(
                "failed to persist a completed chat turn"
            )
            self._store.fail_turn(
                thread_id,
                request_id,
                _DEFAULT_FAILURE_CODE,
                "답변을 저장하지 못했습니다.",
            )
            return

        self._record_conversation(
            user_id,
            user_content,
            assistant,
            decision,
            tool_call_count=len(result["tool_traces"]),
        )

    @staticmethod
    def _turn_result(answer: AnswerResult, started: float) -> TurnResult:
        """Wrap what the RAG returned in what the store persists.

        ``model`` is None on purpose: the RAG picks and calls its own model
        and does not report which. ``latency_ms`` is measured on the worker —
        it is how long the answer took to make, which is the worker's to know.
        Measuring it where the SPA finally sees the answer would fold the
        polling interval into the metric.
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
        # succeeded; a recorder failure costs the record, never the answer.
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
        of the same request id joins it instead of re-asking), which is exactly
        the message the contract says must NOT be duplicated into the history.

        Unsettled assistant rows are dropped too, and by status rather than by
        request id: a turn reserved a moment ago is this turn (the request-id
        filter would have caught it), but an EARLIER turn that failed leaves a
        row with an empty content and a request id of its own. Sending that
        would tell the RAG the conversation contains a blank reply, and it
        would do so only in the one situation where the user is already having
        a bad time.
        """
        return [
            {"role": message["role"], "content": message["content"]}
            for message in messages
            if message["request_id"] != request_id
            and (message["role"] != "assistant" or message["status"] == "done")
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


def _failure_code(error: BaseException) -> str:
    for kind, code in _FAILURE_CODES:
        if isinstance(error, kind):
            return code
    return _DEFAULT_FAILURE_CODE


orchestrator = ChatOrchestrator()
