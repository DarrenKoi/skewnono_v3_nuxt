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

    def get_message_by_request(self, thread_id, request_id, role):
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

    def append_user_message(self, thread_id, content, request_id):
        existing = self.get_message_by_request(thread_id, request_id, "user")
        if existing is not None:
            return existing
        message = self._message(
            message_id=f"user-{len(self.thread['messages'])}",
            role="user",
            content=content,
            request_id=request_id,
        )
        self.thread["messages"].append(message)
        return message

    def set_scope_decision(self, thread_id, request_id, decision):
        message = self.get_message_by_request(thread_id, request_id, "user")
        message["scope_status"] = decision["status"]
        message["scope_reason_code"] = decision["reason_code"]
        return message

    def complete_turn(self, thread_id, request_id, result):
        existing = self.get_message_by_request(thread_id, request_id, "assistant")
        if existing is not None:
            return existing
        user = self.get_message_by_request(thread_id, request_id, "user")
        message = self._message(
            message_id=f"assistant-{len(self.thread['messages'])}",
            role="assistant",
            content=result["content"],
            request_id=request_id,
        )
        message.update(
            {
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
        self.thread["messages"].append(message)
        return message

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
    return ChatOrchestrator(store, lambda query: dict(decision), answerer)


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


def test_answer_failure_keeps_only_the_original_user_message(
    orchestrator, fake_store, answerer
):
    answerer.error = KnowledgeTimeout("slow")

    with pytest.raises(KnowledgeTimeout):
        orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert [message["role"] for message in fake_store.thread["messages"]] == ["user"]
    assert fake_store.thread["messages"][0]["content"] == "alarm"


def test_an_unavailable_rag_leaves_the_turn_retryable(orchestrator, fake_store, answerer):
    answerer.error = KnowledgeUnavailable("no checkout")

    with pytest.raises(KnowledgeUnavailable):
        orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert [message["role"] for message in fake_store.thread["messages"]] == ["user"]


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

    assistant = orchestrator.send_message(
        "u1", "t1", "alarm reset and movie recommendations", REQUEST_ID
    )

    assert assistant["content"] == (
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


def test_bundled_rewrite_and_follow_ups_are_persisted(orchestrator):
    """They arrive inside the answer; the orchestrator makes no calls of its own."""
    assistant = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert assistant["rewrite"] == "확장된 질문"
    assert assistant["follow_ups"] == ["질문 1", "질문 2", "질문 3"]


def test_the_answer_names_no_model(orchestrator):
    """Chat has no LLM: the RAG picks its own and does not report which."""
    assistant = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert assistant["model"] is None
    assert assistant["runtime"] == "rag"


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
    )

    with caplog.at_level("ERROR", logger="skewnono.chat"):
        assistant = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert assistant["content"] == "answer"
    assert "record chat conversation" in caplog.text
