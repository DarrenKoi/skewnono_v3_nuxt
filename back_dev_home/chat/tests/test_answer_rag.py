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
from back_dev_home.chat.answer import contract
from back_dev_home.chat.answer.providers import rag as template
from back_dev_home.chat.contracts import (
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
        return calls.get("reply", contract.golden_answer())

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
        "tool_traces": [],
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
    rag_module["reply"] = {
        "content": "  ",
        "sources": [],
        "follow_ups": [],
        "rewrite": None,
        "tool_traces": [],
    }

    with pytest.raises(KnowledgeUnavailable):
        template.answer_question("q", [], _SCOPE)


def test_a_missing_required_key_is_a_violation_that_names_it(rag_module):
    """The drift this adapter used to absorb silently.

    ``tool_traces`` disappearing produced an empty list and a UI quietly
    missing a feature. It is now a 503 whose message says which key.
    """
    reply = contract.golden_answer()
    del reply["tool_traces"]
    rag_module["reply"] = reply

    with pytest.raises(contract.ContractViolation, match="tool_traces"):
        template.answer_question("현재 질문", [], _SCOPE)


def test_the_office_runner_and_this_adapter_agree_on_the_exception_table(rag_module):
    """``contract.EXCEPTION_MAP`` is what the RAG side is told; pin it here.

    The runner prints that table in the office runtime. If this adapter stops
    honouring a row, the two environments are being told different things —
    which is the whole failure mode this contract module exists to end.
    """
    for raised, (translated, _status) in contract.EXCEPTION_MAP.items():
        rag_module["raise"] = raised("사무실")

        with pytest.raises(translated):
            template.answer_question("q", [], _SCOPE)

        # Subclasses too: `except TimeoutError` is isinstance-based, so the
        # table has to be read that way on both sides.
        subclass = type(f"Office{raised.__name__}", (raised,), {})
        rag_module["raise"] = subclass("사무실")

        with pytest.raises(translated):
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
