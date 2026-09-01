"""Home coverage for the RAG answer provider — the office path, run at home.

The provider is tracked (no gitignored copy), so this is the real code under
test with ``skewnono_rag`` faked: the ``agent_query`` call shape, the
three-way error translation, source normalization, and the five-row cap the
application owns.
"""

from __future__ import annotations

import sys
import types

import pytest

from back_dev_home.chat import config
from back_dev_home.chat.answer.providers import rag as template
from back_dev_home.chat.knowledge.contracts import (
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)


_SCOPE = {"user_id": "1234567", "groups": [], "fabs": []}


def _raw_source(source_id: str) -> dict:
    return {
        "source_id": source_id,
        "source_type": "manual",
        "title": f"Manual {source_id}",
        "snippet": f"Snippet for {source_id}.",
        "locator": f"manual:{source_id}#page=1",
    }


@pytest.fixture
def rag_module(tmp_path, monkeypatch):
    """A fake co-located ``skewnono_rag.retrieve.agent`` that records the call."""
    (tmp_path / "skewnono_rag" / "index").mkdir(parents=True)
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "path", list(sys.path))
    calls: dict = {}

    agent = types.ModuleType("skewnono_rag.retrieve.agent")

    def agent_query(question, *, messages, scope, timeout):
        calls["call"] = {
            "question": question,
            "messages": messages,
            "scope": scope,
            "timeout": timeout,
        }
        if "raise" in calls:
            raise calls["raise"]
        return calls.get(
            "reply",
            {
                "content": "답변입니다.",
                "sources": [_raw_source("CG6300_1")],
                "follow_ups": ["다음 질문 1", "다음 질문 2", "다음 질문 3"],
                "rewrite": None,
                "tool_traces": [],
            },
        )

    agent.agent_query = agent_query
    monkeypatch.setitem(sys.modules, "skewnono_rag.retrieve.agent", agent)
    return calls


def test_agent_query_receives_the_agreed_call_shape(rag_module):
    history = [{"role": "user", "content": "이전 질문"}]

    template.answer_question("현재 질문", history, _SCOPE)

    call = rag_module["call"]
    assert call["question"] == "현재 질문"
    assert call["messages"] == history  # the current question is NOT in history
    assert call["scope"] == dict(_SCOPE)
    # What matters here is that the CONFIGURED budget reaches the RAG, not
    # what today's default happens to be — test_config pins the number.
    assert call["timeout"] == pytest.approx(config.get_answer_timeout())


def test_sources_are_normalized_and_capped_at_five(rag_module):
    rag_module["reply"] = {
        "content": "답변",
        "sources": [_raw_source(f"S{i}") for i in range(8)],
        "follow_ups": [],
        "rewrite": "현재 질문",  # same as the question -> None
    }

    result = template.answer_question("현재 질문", [], _SCOPE)

    assert len(result["sources"]) == 5
    first = result["sources"][0]
    assert first["source_type"] == "manual"
    assert first["page"] is None and first["figure_id"] is None
    assert result["rewrite"] is None
    assert result["tool_traces"] == []
    assert result["prompt_tokens"] is None


def test_empty_content_is_unavailable(rag_module):
    rag_module["reply"] = {"content": "  ", "sources": [], "follow_ups": []}

    with pytest.raises(KnowledgeUnavailable):
        template.answer_question("q", [], _SCOPE)


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (TimeoutError("deadline"), KnowledgeTimeout),
        (PermissionError("denied"), KnowledgeDenied),
        (ValueError("boom"), KnowledgeUnavailable),
    ],
)
def test_failures_translate_to_the_three_knowledge_errors(
    rag_module, raised, expected
):
    rag_module["raise"] = raised

    with pytest.raises(expected):
        template.answer_question("q", [], _SCOPE)


def test_no_checkout_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))

    with pytest.raises(KnowledgeUnavailable):
        template.answer_question("q", [], _SCOPE)
