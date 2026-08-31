import pytest

from back_dev_home.chat.orchestration import (
    ChatOrchestrator,
    ModelDoesNotSupportTools,
    ThreadNotFound,
)
from back_dev_home.chat.knowledge.contracts import KnowledgeUnavailable
from back_dev_home.chat.runtime.contracts import RuntimeTimeout
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
            "model": "m1",
            "system_prompt": "Be concise",
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


class FakeRuntime:
    def __init__(self):
        self.calls = 0
        self.requests = []
        self.error = None

    def __call__(self, request):
        self.calls += 1
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return {
            "content": "answer",
            "runtime": "direct",
            "model": request["model"],
            "prompt_tokens": 3,
            "completion_tokens": 1,
            "latency_ms": 7,
            "sources": [],
            "tool_traces": [],
        }


@pytest.fixture
def fake_store():
    return FakeStore()


@pytest.fixture
def fake_runtime():
    return FakeRuntime()


@pytest.fixture
def scope_decision():
    return {
        "status": "in_scope",
        "reason_code": "supported_domain",
        "supported_query": "alarm",
    }


@pytest.fixture
def orchestrator(fake_store, fake_runtime, scope_decision):
    return ChatOrchestrator(
        fake_store,
        lambda query: dict(scope_decision),
        fake_runtime,
        lambda model_id: {"id": model_id, "supports_tools": True},
        runtime_name_finder=lambda: "direct",
    )


def test_completed_request_is_replayed_without_runtime(orchestrator, fake_runtime):
    first = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)
    second = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert second["id"] == first["id"]
    assert fake_runtime.calls == 1


def test_same_text_with_new_request_id_runs_a_new_turn(orchestrator, fake_runtime):
    first = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)
    second = orchestrator.send_message("u1", "t1", "alarm", SECOND_REQUEST_ID)

    assert second["id"] != first["id"]
    assert fake_runtime.calls == 2


@pytest.mark.parametrize("status", ["out_of_scope", "unsafe"])
def test_rejected_scope_persists_normal_assistant_without_runtime(
    fake_store, fake_runtime, status
):
    orchestrator = ChatOrchestrator(
        fake_store,
        lambda query: {
            "status": status,
            "reason_code": "unsupported",
            "supported_query": None,
        },
        fake_runtime,
        lambda model_id: {"id": model_id, "supports_tools": True},
        runtime_name_finder=lambda: "direct",
    )

    assistant = orchestrator.send_message("u1", "t1", "movie", REQUEST_ID)

    assert assistant["content"] == REFUSAL
    assert assistant["runtime"] == "scope_rejection"
    assert assistant["scope_status"] == status
    assert assistant["sources"] == []
    assert fake_runtime.calls == 0


def test_runtime_failure_keeps_only_the_original_user_message(
    orchestrator, fake_store, fake_runtime
):
    fake_runtime.error = RuntimeTimeout("slow")

    with pytest.raises(RuntimeTimeout):
        orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert [message["role"] for message in fake_store.thread["messages"]] == ["user"]
    assert fake_store.thread["messages"][0]["content"] == "alarm"


def test_mixed_scope_sends_supported_query_but_persists_original(
    fake_store, fake_runtime
):
    orchestrator = ChatOrchestrator(
        fake_store,
        lambda query: {
            "status": "mixed",
            "reason_code": "mixed_scope",
            "supported_query": "alarm reset",
        },
        fake_runtime,
        lambda model_id: {"id": model_id, "supports_tools": True},
        runtime_name_finder=lambda: "direct",
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
    assert fake_runtime.requests[0]["messages"][-1] == {
        "role": "user",
        "content": "alarm reset",
    }
    assert fake_runtime.requests[0]["scope_decision"]["status"] == "mixed"


def test_mixed_scope_without_supported_query_never_reaches_runtime(
    fake_store, fake_runtime
):
    orchestrator = ChatOrchestrator(
        fake_store,
        lambda query: {
            "status": "mixed",
            "reason_code": "mixed_scope",
            "supported_query": None,
        },
        fake_runtime,
        lambda model_id: {"id": model_id, "supports_tools": True},
        runtime_name_finder=lambda: "direct",
    )

    with pytest.raises(ScopeUnavailable, match="supported_query"):
        orchestrator.send_message(
            "u1", "t1", "movie recommendations and alarm reset", REQUEST_ID
        )

    assert fake_runtime.calls == 0


def test_runtime_receives_minimal_access_scope(orchestrator, fake_runtime):
    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert fake_runtime.requests[0]["access_scope"] == {
        "user_id": "u1",
        "groups": [],
        "fabs": [],
    }


def test_missing_or_unowned_thread_is_rejected(orchestrator, fake_store):
    with pytest.raises(ThreadNotFound):
        orchestrator.send_message("u2", "t1", "alarm", REQUEST_ID)

    assert fake_store.thread["messages"] == []


def test_agent_model_without_tool_support_is_rejected_before_persistence(
    fake_store, fake_runtime, scope_decision
):
    orchestrator = ChatOrchestrator(
        fake_store,
        lambda query: dict(scope_decision),
        fake_runtime,
        lambda model_id: {"id": model_id, "supports_tools": False},
        runtime_name_finder=lambda: "agent",
    )

    with pytest.raises(ModelDoesNotSupportTools):
        orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert fake_store.thread["messages"] == []
    assert fake_runtime.calls == 0


# ---------------------------------------------------------------------------
# Query rewrite (before the agent loop) and follow-ups (after the answer).
# Both are knowledge-provider calls the orchestrator makes only in agent mode.
# ---------------------------------------------------------------------------


class FakeRag:
    def __init__(self):
        self.rewrites = []
        self.follow_up_calls = []
        self.rewrite_error = None
        self.follow_up_error = None

    def rewrite(self, question):
        self.rewrites.append(question)
        if self.rewrite_error is not None:
            raise self.rewrite_error
        return f"{question} (expanded)"

    def follow_ups(self, question, answer, sources):
        self.follow_up_calls.append((question, answer, sources))
        if self.follow_up_error is not None:
            raise self.follow_up_error
        return ["다음 질문", "Next question"]


@pytest.fixture
def fake_rag():
    return FakeRag()


def _agent_orchestrator(fake_store, fake_runtime, fake_rag, decision):
    return ChatOrchestrator(
        fake_store,
        lambda query: dict(decision),
        fake_runtime,
        lambda model_id: {"id": model_id, "supports_tools": True},
        runtime_name_finder=lambda: "agent",
        query_rewriter=fake_rag.rewrite,
        follow_up_generator=fake_rag.follow_ups,
    )


def test_agent_mode_rewrites_once_and_hands_the_rewrite_to_the_runtime(
    fake_store, fake_runtime, fake_rag, scope_decision
):
    orchestrator = _agent_orchestrator(fake_store, fake_runtime, fake_rag, scope_decision)

    assistant = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert fake_rag.rewrites == ["alarm"]
    assert fake_runtime.requests[0]["rewrite"] == "alarm (expanded)"
    # The user's own words stay the user message; the rewrite is a hint.
    assert fake_runtime.requests[0]["messages"][-1] == {"role": "user", "content": "alarm"}
    assert assistant["rewrite"] == "alarm (expanded)"
    assert fake_store.thread["messages"][0]["content"] == "alarm"


def test_agent_mode_generates_follow_ups_from_the_answer_and_its_sources(
    fake_store, fake_runtime, fake_rag, scope_decision
):
    orchestrator = _agent_orchestrator(fake_store, fake_runtime, fake_rag, scope_decision)

    assistant = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert fake_rag.follow_up_calls == [("alarm", "answer", [])]
    assert assistant["follow_ups"] == ["다음 질문", "Next question"]


def test_mixed_scope_rewrites_the_supported_query_not_the_original(
    fake_store, fake_runtime, fake_rag
):
    orchestrator = _agent_orchestrator(
        fake_store, fake_runtime, fake_rag,
        {"status": "mixed", "reason_code": "mixed_scope", "supported_query": "alarm reset"},
    )

    orchestrator.send_message("u1", "t1", "alarm reset and a movie", REQUEST_ID)

    assert fake_rag.rewrites == ["alarm reset"]
    assert fake_rag.follow_up_calls[0][0] == "alarm reset"


def test_an_unchanged_rewrite_is_stored_as_none(
    fake_store, fake_runtime, fake_rag, scope_decision
):
    fake_rag.rewrite = lambda question: question
    orchestrator = _agent_orchestrator(fake_store, fake_runtime, fake_rag, scope_decision)

    assistant = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert assistant["rewrite"] is None
    assert fake_runtime.requests[0]["rewrite"] is None


def test_direct_mode_never_calls_the_rag(fake_store, fake_runtime, fake_rag, scope_decision):
    orchestrator = ChatOrchestrator(
        fake_store,
        lambda query: dict(scope_decision),
        fake_runtime,
        lambda model_id: {"id": model_id, "supports_tools": True},
        runtime_name_finder=lambda: "direct",
        query_rewriter=fake_rag.rewrite,
        follow_up_generator=fake_rag.follow_ups,
    )

    assistant = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert fake_rag.rewrites == [] and fake_rag.follow_up_calls == []
    assert assistant["rewrite"] is None
    assert assistant["follow_ups"] == []
    assert fake_runtime.requests[0]["rewrite"] is None


@pytest.mark.parametrize("status", ["out_of_scope", "unsafe"])
def test_rejected_scope_never_calls_the_rag(fake_store, fake_runtime, fake_rag, status):
    orchestrator = _agent_orchestrator(
        fake_store, fake_runtime, fake_rag,
        {"status": status, "reason_code": "unsupported", "supported_query": None},
    )

    assistant = orchestrator.send_message("u1", "t1", "movie", REQUEST_ID)

    assert fake_rag.rewrites == [] and fake_rag.follow_up_calls == []
    assert assistant["follow_ups"] == []


def test_rewrite_failure_keeps_only_the_user_message(
    fake_store, fake_runtime, fake_rag, scope_decision
):
    """A failed rewrite is a failed turn — running the raw question instead
    would look like a working answer of measurably worse recall."""
    fake_rag.rewrite_error = KnowledgeUnavailable("rag down")
    orchestrator = _agent_orchestrator(fake_store, fake_runtime, fake_rag, scope_decision)

    with pytest.raises(KnowledgeUnavailable):
        orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert [m["role"] for m in fake_store.thread["messages"]] == ["user"]
    assert fake_runtime.calls == 0


def test_follow_up_failure_costs_the_suggestions_not_the_answer(
    fake_store, fake_runtime, fake_rag, scope_decision, caplog
):
    fake_rag.follow_up_error = RuntimeError("rag down")
    orchestrator = _agent_orchestrator(fake_store, fake_runtime, fake_rag, scope_decision)

    with caplog.at_level("ERROR", logger="skewnono.chat"):
        assistant = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert assistant["content"] == "answer"
    assert assistant["follow_ups"] == []
    assert "follow-up" in caplog.text


class BundledRuntime(FakeRuntime):
    """A rag-runtime double: rewrite and follow-ups arrive inside the result."""

    def __call__(self, request):
        result = super().__call__(request)
        result["runtime"] = "rag"
        result["rewrite"] = "확장된 질문"
        result["follow_ups"] = ["질문 1", "질문 2", "질문 3"]
        return result


def _rag_orchestrator(fake_store, runtime, fake_rag, decision):
    return ChatOrchestrator(
        fake_store,
        lambda query: dict(decision),
        runtime,
        # No tool-capable model exists: the rag runtime must not require one.
        lambda model_id: {"id": model_id, "supports_tools": False},
        runtime_name_finder=lambda: "rag",
        query_rewriter=fake_rag.rewrite,
        follow_up_generator=fake_rag.follow_ups,
    )


def test_rag_runtime_keeps_bundled_rewrite_and_follow_ups(
    fake_store, fake_rag, scope_decision
):
    runtime = BundledRuntime()
    orchestrator = _rag_orchestrator(fake_store, runtime, fake_rag, scope_decision)

    message = orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert message["rewrite"] == "확장된 질문"
    assert message["follow_ups"] == ["질문 1", "질문 2", "질문 3"]
    # The orchestrator's own knowledge calls stay out of the rag path.
    assert fake_rag.rewrites == []
    assert fake_rag.follow_up_calls == []
    assert runtime.requests[0].get("rewrite") is None
