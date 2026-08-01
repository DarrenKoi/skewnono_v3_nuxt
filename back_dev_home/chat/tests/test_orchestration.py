import pytest

from back_dev_home.chat.orchestration import (
    ChatOrchestrator,
    ModelDoesNotSupportTools,
    ThreadNotFound,
)
from back_dev_home.chat.runtime.contracts import RuntimeTimeout


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
