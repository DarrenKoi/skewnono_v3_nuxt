"""One persisted turn: replay, scope, one answer call, persistence, logging.

The answer seam is faked here — what it returns is pinned by ``test_answer``
and ``test_answer_rag``. What this file guards is what the orchestrator does
around that call.
"""

import pytest

from back_dev_home.chat.contracts import KnowledgeTimeout, KnowledgeUnavailable
from back_dev_home.chat.orchestration import ChatOrchestrator, ThreadNotFound
from back_dev_home.chat.scope.contracts import ScopeUnavailable


REQUEST_ID = "64d35cd4-9e07-4be8-90a3-683f94c29408"
SECOND_REQUEST_ID = "5c5f790a-8fb7-4bed-9e14-d866dc102ffc"
REFUSAL = (
    "이 채팅은 장비 매뉴얼, E-beam 계측, 팀 회의·이메일·보고서 관련 질문을 "
    "지원합니다. 해당 범위의 질문으로 다시 요청해 주세요."
)


class FakeStore:
    def __init__(self):
        self.thread = {
            "id": "t1",
            "user_id": "u1",
            "title": "New chat",
            "messages": [],
        }

    def get_thread(self, user_id, thread_id):
        if user_id != self.thread["user_id"] or thread_id != self.thread["id"]:
            return None
        return self.thread

    def _find(self, thread_id, request_id, role):
        return next(
            (
                message
                for message in self.thread["messages"]
                if message["thread_id"] == thread_id
                and message["request_id"] == request_id
                and message["role"] == role
            ),
            None,
        )

    def get_message_by_request(self, thread_id, request_id, role):
        # A COPY, like the real store: rows come back hydrated from SQLite, so
        # a test must never pass because it happened to hold the same dict the
        # worker later mutated.
        found = self._find(thread_id, request_id, role)
        return None if found is None else dict(found)

    def append_user_message(self, thread_id, content, request_id):
        existing = self._find(thread_id, request_id, "user")
        if existing is not None:
            return dict(existing)
        message = self._message(
            message_id=f"user-{len(self.thread['messages'])}",
            role="user",
            content=content,
            request_id=request_id,
        )
        self.thread["messages"].append(message)
        return dict(message)

    def set_scope_decision(self, thread_id, request_id, decision):
        message = self._find(thread_id, request_id, "user")
        message["scope_status"] = decision["status"]
        message["scope_reason_code"] = decision["reason_code"]
        return dict(message)

    def begin_turn(self, thread_id, request_id):
        existing = self._find(thread_id, request_id, "assistant")
        if existing is not None:
            if existing["status"] != "failed":
                return dict(existing), False
            existing.update(
                status="pending", error_code=None, error_message=None, content=""
            )
            return dict(existing), True
        user = self._find(thread_id, request_id, "user")
        message = self._message(
            message_id=f"assistant-{len(self.thread['messages'])}",
            role="assistant",
            content="",
            request_id=request_id,
        )
        message.update(
            {
                "status": "pending",
                "scope_status": user["scope_status"],
                "scope_reason_code": user["scope_reason_code"],
            }
        )
        self.thread["messages"].append(message)
        return dict(message), True

    def fail_turn(self, thread_id, request_id, error_code, error_message):
        message = self._find(thread_id, request_id, "assistant")
        if message is None or message["status"] != "pending":
            return None if message is None else dict(message)
        message.update(
            status="failed", error_code=error_code, error_message=error_message
        )
        return dict(message)

    def complete_turn(self, thread_id, request_id, result):
        if self._find(thread_id, request_id, "assistant") is None:
            self.begin_turn(thread_id, request_id)
        message = self._find(thread_id, request_id, "assistant")
        if message["status"] == "done":
            return dict(message)
        user = self._find(thread_id, request_id, "user")
        message.update(
            {
                "status": "done",
                "error_code": None,
                "error_message": None,
                "content": result["content"],
                "model": result["model"],
                "runtime": result["runtime"],
                "scope_status": user["scope_status"],
                "scope_reason_code": user["scope_reason_code"],
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
                "latency_ms": result["latency_ms"],
                "sources": result["sources"],
                "rewrite": result.get("rewrite"),
                "follow_ups": list(result.get("follow_ups", [])),
            }
        )
        return dict(message)

    def _message(self, *, message_id, role, content, request_id):
        return {
            "id": message_id,
            "thread_id": self.thread["id"],
            "request_id": request_id,
            "role": role,
            "content": content,
            "model": None,
            "runtime": None,
            "scope_status": None,
            "scope_reason_code": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "latency_ms": None,
            "sources": [],
            "feedback": None,
            "status": "done",
            "error_code": None,
            "error_message": None,
            "created_at": "2026-08-02T00:00:00+00:00",
        }


class FakeAnswerer:
    """Stands in for the RAG: one call, the whole turn, suggestions included."""

    def __init__(self):
        self.calls = 0
        self.questions = []
        self.histories = []
        self.scopes = []
        self.error = None

    def __call__(self, question, messages, scope):
        self.calls += 1
        self.questions.append(question)
        self.histories.append(list(messages))
        self.scopes.append(scope)
        if self.error is not None:
            raise self.error
        return {
            "content": "answer",
            "sources": [],
            "follow_ups": ["질문 1", "질문 2", "질문 3"],
            "rewrite": "확장된 질문",
            "tool_traces": [],
            "prompt_tokens": 3,
            "completion_tokens": 1,
        }


@pytest.fixture
def fake_store():
    return FakeStore()


@pytest.fixture
def answerer():
    return FakeAnswerer()


@pytest.fixture
def scope_decision():
    return {
        "status": "in_scope",
        "reason_code": "supported_domain",
        "supported_query": "alarm",
    }


def _orchestrator(store, answerer, decision):
    # The worker runs inline so a test can assert on the settled row. What is
    # NOT faked away is that `send_message` returns the row as it stood when
    # the worker was handed the turn — pending. Tests read the outcome from
    # the store, the way a poll does.
    return ChatOrchestrator(
        store, lambda query: dict(decision), answerer, spawn=lambda run: run()
    )


def _settled(store, request_id=REQUEST_ID):
    """The assistant row after the worker finished — what a poll would see."""
    return store.get_message_by_request("t1", request_id, "assistant")


@pytest.fixture
def orchestrator(fake_store, answerer, scope_decision):
    return _orchestrator(fake_store, answerer, scope_decision)


def test_completed_request_is_replayed_without_asking_again(orchestrator, answerer):
    first = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)
    second = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert second["id"] == first["id"]
    assert answerer.calls == 1


def test_same_text_with_new_request_id_runs_a_new_turn(orchestrator, answerer):
    first = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)
    second = orchestrator.send_message("u1", "t1", "alarm", SECOND_REQUEST_ID)

    assert second["id"] != first["id"]
    assert answerer.calls == 2


@pytest.mark.parametrize("status", ["out_of_scope", "unsafe"])
def test_rejected_scope_persists_a_normal_assistant_turn_without_asking(
    fake_store, answerer, status
):
    orchestrator = _orchestrator(
        fake_store,
        answerer,
        {"status": status, "reason_code": "unsupported", "supported_query": None},
    )

    assistant = orchestrator.send_message("u1", "t1", "movie", REQUEST_ID)

    assert assistant["content"] == REFUSAL
    assert assistant["runtime"] == "scope_rejection"
    assert assistant["scope_status"] == status
    assert assistant["sources"] == []
    assert answerer.calls == 0


def test_answer_failure_lands_on_the_turn_not_on_the_request(
    orchestrator, fake_store, answerer
):
    """Nothing is waiting on the worker, so a failure has to be recorded.

    It is stored as a failed turn rather than as an assistant answer whose
    content happens to be an error sentence — the 30-day archive and the
    conversation index would otherwise count it as a turn the RAG answered.
    """
    answerer.error = KnowledgeTimeout("slow")

    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assistant = _settled(fake_store)
    assert assistant["status"] == "failed"
    assert assistant["error_code"] == "gateway_timeout"
    assert assistant["content"] == ""
    assert assistant["runtime"] is None
    assert fake_store.thread["messages"][0]["content"] == "alarm"


def test_an_unavailable_rag_leaves_the_turn_retryable(orchestrator, fake_store, answerer):
    """A failed turn is retaken in place by a POST with the same request id.

    The SPA's retry reuses the UUID (MIGRATION.md: a retry keeps it, a new
    question gets a new one), so a failed turn that refused to restart would
    leave the retry button doing nothing.
    """
    answerer.error = KnowledgeUnavailable("no checkout")
    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)
    assert _settled(fake_store)["error_code"] == "runtime_unavailable"

    answerer.error = None
    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    retried = _settled(fake_store)
    assert retried["status"] == "done"
    assert retried["content"] == "answer"
    assert [message["role"] for message in fake_store.thread["messages"]] == [
        "user", "assistant"
    ], "the retry reuses the reserved row rather than adding a second one"


def test_mixed_scope_asks_the_supported_clause_but_persists_the_original(
    fake_store, answerer
):
    orchestrator = _orchestrator(
        fake_store,
        answerer,
        {
            "status": "mixed",
            "reason_code": "mixed_scope",
            "supported_query": "alarm reset",
        },
    )

    orchestrator.send_message(
        "u1", "t1", "alarm reset and movie recommendations", REQUEST_ID
    )

    assert _settled(fake_store)["content"] == (
        "지원 범위를 벗어난 부분은 제외하고, 지원되는 업무 관련 질문에만 "
        "답변했습니다.\n\nanswer"
    )
    assert fake_store.thread["messages"][0]["content"] == (
        "alarm reset and movie recommendations"
    )
    assert answerer.questions == ["alarm reset"]


def test_mixed_scope_without_a_supported_query_never_reaches_the_rag(
    fake_store, answerer
):
    orchestrator = _orchestrator(
        fake_store,
        answerer,
        {"status": "mixed", "reason_code": "mixed_scope", "supported_query": None},
    )

    with pytest.raises(ScopeUnavailable, match="supported_query"):
        orchestrator.send_message(
            "u1", "t1", "movie recommendations and alarm reset", REQUEST_ID
        )

    assert answerer.calls == 0


def test_the_question_is_not_duplicated_into_the_history(orchestrator, answerer):
    """Agreed contract: the current turn travels in ``question``, alone."""
    orchestrator.send_message("u1", "t1", "첫 질문", REQUEST_ID)
    orchestrator.send_message("u1", "t1", "두 번째 질문", SECOND_REQUEST_ID)

    assert answerer.histories[0] == []
    assert answerer.histories[1] == [
        {"role": "user", "content": "첫 질문"},
        {"role": "assistant", "content": "answer"},
    ]
    assert answerer.questions[1] == "두 번째 질문"


def test_the_rag_receives_a_minimal_access_scope(orchestrator, answerer):
    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert answerer.scopes[0] == {"user_id": "u1", "groups": [], "fabs": []}


def test_bundled_rewrite_and_follow_ups_are_persisted(orchestrator, fake_store):
    """They arrive inside the answer; the orchestrator makes no calls of its own."""
    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assistant = _settled(fake_store)
    assert assistant["rewrite"] == "확장된 질문"
    assert assistant["follow_ups"] == ["질문 1", "질문 2", "질문 3"]


def test_the_answer_names_no_model(orchestrator, fake_store):
    """Chat has no LLM: the RAG picks its own and does not report which."""
    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assistant = _settled(fake_store)
    assert assistant["model"] is None
    assert assistant["runtime"] == "rag"


def test_send_message_hands_back_a_pending_turn(fake_store, answerer, scope_decision):
    """The POST answers with the reserved row, not with the answer.

    Pinned with a worker that never runs, because the whole point is that the
    request is over before the answer exists — a fixture that runs the worker
    inline would let this pass even if the route waited.
    """
    never = ChatOrchestrator(
        fake_store,
        lambda query: dict(scope_decision),
        answerer,
        spawn=lambda run: None,
    )

    assistant = never.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert assistant["status"] == "pending"
    assert assistant["content"] == ""
    assert answerer.calls == 0


def test_missing_or_unowned_thread_is_rejected(orchestrator, fake_store):
    with pytest.raises(ThreadNotFound):
        orchestrator.send_message("u2", "t1", "alarm", REQUEST_ID)

    assert fake_store.thread["messages"] == []


def test_a_recorder_failure_costs_the_record_not_the_answer(
    fake_store, answerer, scope_decision, caplog
):
    def explode(**kwargs):
        raise RuntimeError("opensearch down")

    orchestrator = ChatOrchestrator(
        fake_store,
        lambda query: dict(scope_decision),
        answerer,
        conversation_recorder=explode,
        spawn=lambda run: run(),
    )

    with caplog.at_level("ERROR", logger="skewnono.chat"):
        orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert _settled(fake_store)["content"] == "answer"
    assert _settled(fake_store)["status"] == "done"
    assert "record chat conversation" in caplog.text


def test_an_earlier_failed_turn_is_not_sent_as_a_blank_reply(
    fake_store, answerer, scope_decision
):
    """History carries answers, not the holes where answers failed.

    A failed turn leaves a row with empty content and a request id of its own,
    so the current turn's request-id filter does not catch it. Forwarding it
    would tell the RAG the conversation contains a blank assistant message —
    and only ever in the situation where a turn has already gone wrong.
    """
    orchestrator = _orchestrator(fake_store, answerer, scope_decision)
    answerer.error = KnowledgeUnavailable("no checkout")
    orchestrator.send_message("u1", "t1", "첫 질문", REQUEST_ID)
    assert _settled(fake_store)["status"] == "failed"

    answerer.error = None
    orchestrator.send_message("u1", "t1", "두 번째 질문", SECOND_REQUEST_ID)

    assert answerer.histories[-1] == [{"role": "user", "content": "첫 질문"}]
