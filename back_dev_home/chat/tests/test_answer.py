"""The answer seam: one call answers a whole turn (agreed contract 2026-08-31).

Dispatcher owns provider selection and the history cap; the mock answerer
stands in for the RAG's ``agent_query`` at home with the same result shape.
"""

from __future__ import annotations

import pytest

from back_dev_home.chat.answer import data
from back_dev_home.chat.knowledge.contracts import KnowledgeUnavailable


_SCOPE = {"user_id": "1234567", "groups": [], "fabs": []}


def _answer(question="alignment 오차 보정 방법", messages=()):
    return data.answer_question(question, list(messages), _SCOPE)


def test_mock_answer_has_the_agreed_shape(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_PROVIDER", "mock")

    result = _answer()

    assert isinstance(result["content"], str) and result["content"].strip()
    assert len(result["sources"]) <= 5
    for source in result["sources"]:
        assert source["source_type"] == "manual"
        assert source["source_id"] and source["title"] and source["snippet"]
    assert 3 <= len(result["follow_ups"]) <= 5
    assert all(isinstance(item, str) and item for item in result["follow_ups"])
    assert result["rewrite"] is None or result["rewrite"] != "alignment 오차 보정 방법"
    assert result["tool_traces"] and result["tool_traces"][0]["status"] in {
        "success",
        "empty",
    }
    assert result["prompt_tokens"] is None
    assert result["completion_tokens"] is None


def test_history_is_capped_before_the_provider_sees_it(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_PROVIDER", "mock")
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_MAX_HISTORY", "4")
    seen = {}

    from back_dev_home.chat.answer.providers import mock as mock_provider

    original = mock_provider.answer_question

    def spy(question, messages, scope):
        seen["messages"] = list(messages)
        return original(question, messages, scope)

    monkeypatch.setattr(mock_provider, "answer_question", spy)
    history = [{"role": "user", "content": f"turn {i}"} for i in range(10)]

    _answer(messages=history)

    assert seen["messages"] == history[-4:]


def test_missing_office_copy_is_unavailable_not_a_crash(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_PROVIDER", "office")

    with pytest.raises(KnowledgeUnavailable, match="office"):
        _answer()
