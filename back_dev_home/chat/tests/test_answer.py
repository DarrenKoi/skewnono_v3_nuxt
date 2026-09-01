"""The answer seam: one call answers a whole turn (agreed contract 2026-08-31).

Dispatcher owns provider selection and the history cap. Selection has no env
knob: a usable ``_rag`` checkout picks the RAG provider, its absence picks the
mock, which stands in for ``agent_query`` at home with the same result shape.
"""

from __future__ import annotations

import pytest

from back_dev_home.chat import rag
from back_dev_home.chat.answer import contract, data


_SCOPE = {"user_id": "1234567", "groups": [], "fabs": []}


def _answer(question="alignment 오차 보정 방법", messages=()):
    return data.answer_question(question, list(messages), _SCOPE)


@pytest.fixture(autouse=True)
def _no_rag_checkout(monkeypatch):
    """Home: no checkout, so the dispatcher must land on the mock."""
    monkeypatch.setattr(rag, "rag_ready", lambda: False)


def test_mock_answer_satisfies_the_office_contract():
    """Home and office are held to one shape by one validator.

    Hand-rolled shape assertions used to live here, which meant the mock was
    checked against a second reading of the contract. Both paths are pinned
    because both are contractual: an answer with citations, and the honest
    "no evidence found" answer — which is the one the default question
    actually produces, a fact the old ``len(sources) <= 5`` assertion could
    not distinguish from a working search.
    """
    found = "정비 공지 계측 서비스"
    result = contract.validate_answer(_answer(found), question=found)

    assert result["sources"], "the mock must find its own fixtures"
    # All four source types, not manuals only: the office agent reaches every
    # one, and only the non-manual fixtures produce a figure-less citation.
    assert {source["source_type"] for source in result["sources"]} <= {
        "manual", "meeting", "email", "report"
    }
    assert [trace["tool_name"] for trace in result["tool_traces"]] == [
        "search_manuals",
        "search_meeting_summaries",
        "search_emails",
        "search_reports",
    ]

    empty = "alignment 오차 보정 방법"
    no_hits = contract.validate_answer(_answer(empty), question=empty)

    assert no_hits["sources"] == []
    assert no_hits["content"].strip(), "a no-evidence turn is still an answer"
    assert 3 <= len(no_hits["follow_ups"]) <= 5


def test_history_is_capped_before_the_provider_sees_it(monkeypatch):
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


def test_a_usable_checkout_selects_the_rag_provider(monkeypatch):
    """The whole switch: readiness, not configuration."""
    monkeypatch.setattr(rag, "rag_ready", lambda: True)

    from back_dev_home.chat.answer.providers import rag as rag_provider

    assert data._provider() is rag_provider


def test_no_checkout_selects_the_mock_provider():
    from back_dev_home.chat.answer.providers import mock as mock_provider

    assert data._provider() is mock_provider


def test_a_figure_less_citation_is_reachable_at_home():
    """The office's COMMON case: text and table chunks carry no figure_id.

    Only the non-manual fixtures have ``figure_id: None``, so while this mock
    searched manuals alone the state could not occur at home — and the UI path
    for a citation with no image was the one path no home session could see.
    """
    result = _answer("정비 공지 계측 서비스")

    assert result["sources"], "the open email fixture must be reachable"
    assert any(source["figure_id"] is None for source in result["sources"])


def test_sources_from_different_tools_share_one_ranking():
    """Merged hits are ordered by score across tools, not tool by tool.

    Each search sorts within its own source, so concatenating them would put a
    weak manual above a strong report purely because manuals are searched
    first — and the top 5 cap would then drop the better evidence.
    """
    result = _answer("계측 서비스 공지 측정 tat 시나리오")

    scores = [float(source["score"] or 0) for source in result["sources"]]
    assert scores == sorted(scores, reverse=True)
    assert len({source["source_type"] for source in result["sources"]}) > 1
