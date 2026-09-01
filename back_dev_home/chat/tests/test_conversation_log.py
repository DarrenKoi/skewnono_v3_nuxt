"""Conversation logging: document schema, emission, and turn-level wiring."""

import logging

import pytest

from back_dev_home.chat import conversation_log
from back_dev_home.chat.conversation_log import (
    CONTENT_LIMIT,
    ChatConversationHandler,
    build_turn_document,
    install_chat_conversation_logging,
    record_turn,
)
from back_dev_home.chat.contracts import KnowledgeTimeout
from back_dev_home.chat.orchestration import ChatOrchestrator
from back_dev_home.chat.tests.test_orchestration import (
    REQUEST_ID,
    SECOND_REQUEST_ID,
    FakeAnswerer,
    FakeStore,
)
from ops_index_mgmt.skewnono_chat_logging import CHAT_MAPPING_PROPERTIES

# Fields the handler envelope stamps on every document; the rest must come
# from build_turn_document. Together they must equal the index mapping.
ENVELOPE_FIELDS = {"event_id", "@timestamp", "service", "deployment", "host"}


def _assistant(**overrides):
    message = {
        "id": "assistant-1",
        "thread_id": "t1",
        "request_id": REQUEST_ID,
        "role": "assistant",
        "content": "answer",
        "model": None,
        "runtime": "rag",
        "scope_status": "in_scope",
        "prompt_tokens": 3,
        "completion_tokens": 1,
        "latency_ms": 7,
        "sources": [],
        "feedback": None,
        "status": "done",
        "error_code": None,
        "error_message": None,
        "created_at": "2026-08-04T00:00:00+00:00",
    }
    message.update(overrides)
    return message


def _decision(**overrides):
    decision = {
        "status": "in_scope",
        "reason_code": "supported_domain",
    }
    decision.update(overrides)
    return decision


def _document(**overrides):
    kwargs = {
        "user_id": "u1",
        "user_content": "alarm",
        "assistant": _assistant(),
        "decision": _decision(),
        "tool_call_count": 0,
    }
    kwargs.update(overrides)
    return build_turn_document(**kwargs)


class RecordingRecorder:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error


def _orchestrator(store, answerer, recorder, classify=None):
    return ChatOrchestrator(
        store,
        classify or (lambda query: _decision()),
        answerer,
        conversation_recorder=recorder,
        # Inline, so an assertion about what was recorded runs after the turn
        # it describes. In production the worker is a daemon thread.
        spawn=lambda run: run(),
    )


# -- document schema ---------------------------------------------------


def test_document_fields_and_mapping_agree_exactly():
    # The index mapping is dynamic:false, so a field missing from
    # CHAT_MAPPING_PROPERTIES is silently unsearchable and a mapped field the
    # builder never emits is dead weight. Keep the three places in lockstep.
    document = _document()
    assert set(document) | ENVELOPE_FIELDS == set(CHAT_MAPPING_PROPERTIES)


def test_document_carries_turn_identity_and_content():
    sources = [
        {"source_id": "manual-1", "source_type": "manual"},
        {"source_id": "report-9", "source_type": "report"},
    ]
    document = _document(
        assistant=_assistant(sources=sources),
        tool_call_count=2,
    )
    assert document["user_id"] == "u1"
    assert document["thread_id"] == "t1"
    assert document["request_id"] == REQUEST_ID
    assert document["message_id"] == "assistant-1"
    assert document["user_content"] == "alarm"
    assert document["assistant_content"] == "answer"
    assert document["scope_status"] == "in_scope"
    assert document["scope_reason_code"] == "supported_domain"
    assert document["source_count"] == 2
    assert document["source_ids"] == ["manual-1", "report-9"]
    assert document["tool_call_count"] == 2


def test_document_bounds_both_content_fields():
    long_text = "x" * (CONTENT_LIMIT + 500)
    document = _document(
        user_content=long_text,
        assistant=_assistant(content=long_text),
    )
    assert len(document["user_content"]) == CONTENT_LIMIT
    assert len(document["assistant_content"]) == CONTENT_LIMIT


def test_scope_rejection_is_recorded_as_its_own_runtime():
    document = _document(
        assistant=_assistant(model=None, runtime="scope_rejection"),
        decision=_decision(status="out_of_scope", reason_code="unsupported"),
    )
    assert document["model"] is None
    assert document["runtime"] == "scope_rejection"
    assert document["scope_reason_code"] == "unsupported"


# -- emission ----------------------------------------------------------


class CapturingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def captured_records():
    handler = CapturingHandler()
    conversation_log.logger.addHandler(handler)
    conversation_log.logger.setLevel(logging.INFO)
    yield handler.records
    conversation_log.logger.removeHandler(handler)


def test_record_turn_emits_one_conversation_record(captured_records):
    record_turn(
        user_id="u1",
        user_content="alarm",
        assistant=_assistant(),
        decision=_decision(),
        tool_call_count=1,
    )
    assert len(captured_records) == 1
    conversation = captured_records[0].conversation
    assert conversation["user_content"] == "alarm"
    assert conversation["tool_call_count"] == 1


def test_conversation_logger_never_propagates_to_root():
    # At the office, root carries the activity-index handler; a propagating
    # conversation record would put a junk row per turn in skewnono_logging.
    assert conversation_log.logger.propagate is False


# -- handler document conversion ---------------------------------------


@pytest.fixture
def handler():
    instance = ChatConversationHandler(
        client_factory=lambda: None,
        deployment="local",
        index="skewnono_chat_logging_local",
        uuid_factory=lambda: "event-1",
        host="test-host",
    )
    yield instance
    instance.close()


def _log_record(**extra):
    record = logging.LogRecord(
        name=conversation_log.CONVERSATION_LOGGER_NAME,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="chat turn",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_handler_wraps_payload_in_envelope(handler):
    doc = handler._record_to_doc(_log_record(conversation=_document()))
    assert doc["event_id"] == "event-1"
    assert doc["service"] == "skewnono"
    assert doc["deployment"] == "local"
    assert doc["host"] == "test-host"
    assert doc["user_content"] == "alarm"
    assert set(doc) <= set(CHAT_MAPPING_PROPERTIES)


def test_handler_omits_none_values(handler):
    document = _document(
        assistant=_assistant(prompt_tokens=None, completion_tokens=None)
    )
    doc = handler._record_to_doc(_log_record(conversation=document))
    assert "prompt_tokens" not in doc
    assert "completion_tokens" not in doc


def test_handler_rejects_records_without_payload(handler):
    with pytest.raises(TypeError):
        handler._record_to_doc(_log_record())


# -- orchestrator wiring -----------------------------------------------


def test_completed_turn_records_one_conversation():
    recorder = RecordingRecorder()
    orchestrator = _orchestrator(FakeStore(), FakeAnswerer(), recorder)

    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["user_id"] == "u1"
    assert call["user_content"] == "alarm"
    # The SETTLED row, not the pending one the POST returned: the record is
    # written by the worker, after the answer exists.
    assert call["assistant"]["content"] == "answer"
    assert call["assistant"]["status"] == "done"
    assert call["tool_call_count"] == 0


def test_replayed_request_is_not_recorded_again():
    recorder = RecordingRecorder()
    orchestrator = _orchestrator(FakeStore(), FakeAnswerer(), recorder)

    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)
    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)
    orchestrator.send_message("u1", "t1", "alarm", SECOND_REQUEST_ID)

    assert len(recorder.calls) == 2


def test_answer_failure_records_nothing():
    """A failed turn is not a conversation. It is recorded on its own row."""
    recorder = RecordingRecorder()
    answerer = FakeAnswerer()
    answerer.error = KnowledgeTimeout("slow")
    store = FakeStore()
    orchestrator = _orchestrator(store, answerer, recorder)

    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    assert recorder.calls == []
    assert store.get_message_by_request("t1", REQUEST_ID, "assistant")[
        "status"
    ] == "failed"


def test_scope_rejection_is_recorded_with_decision():
    recorder = RecordingRecorder()
    orchestrator = _orchestrator(
        FakeStore(),
        FakeAnswerer(),
        recorder,
        classify=lambda query: _decision(
            status="out_of_scope", reason_code="unsupported"
        ),
    )

    orchestrator.send_message("u1", "t1", "movie", REQUEST_ID)

    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["decision"]["status"] == "out_of_scope"
    assert call["tool_call_count"] == 0


def test_recorder_failure_never_breaks_the_turn():
    recorder = RecordingRecorder(error=RuntimeError("shipper down"))
    store = FakeStore()
    orchestrator = _orchestrator(store, FakeAnswerer(), recorder)

    orchestrator.send_message("u1", "t1", "alarm", REQUEST_ID)

    settled = store.get_message_by_request("t1", REQUEST_ID, "assistant")
    assert settled["content"] == "answer"
    assert settled["status"] == "done"
    assert len(recorder.calls) == 1


# -- install gating ----------------------------------------------------


def test_install_is_a_noop_outside_office_mode(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    assert install_chat_conversation_logging() is None


def test_install_is_a_noop_when_disabled(monkeypatch):
    monkeypatch.setenv("OPENSEARCH_LOGGING_DISABLED", "1")
    assert install_chat_conversation_logging() is None


def test_install_requires_a_password_even_with_explicit_target(monkeypatch):
    from back_dev_home._logging.target import resolve_chat_conversation_target

    monkeypatch.delenv("OPENSEARCH_PASSWORD", raising=False)
    target = resolve_chat_conversation_target({"SKEWNONO_LOG_ENV": "local"})
    assert target.alias == "skewnono_chat_logging_local"
    assert install_chat_conversation_logging(target=target) is None
