"""The executable contract itself — the file both environments run.

The RAG side cannot run this suite (they own ``_rag/skewnono_rag/`` and
nothing else), but they run the module: ``python -m
back_dev_home.chat.answer.contract``. These tests are what keeps the thing
they run honest.
"""

from __future__ import annotations

import pytest

from back_dev_home.chat.answer import contract
from back_dev_home.chat.answer.contract import ContractViolation, validate_answer


_Q = "GT2000 얼라인 알람 리셋 절차 알려줘"


def _answer(**overrides):
    payload = contract.golden_answer()
    payload.update(overrides)
    return payload


def test_the_golden_payload_satisfies_its_own_validator():
    """The example the RAG side matches their output against must be valid.

    A golden payload that fails the validator would teach the office the
    wrong shape, which is worse than having no example at all.
    """
    result = validate_answer(contract.golden_answer(), question=_Q)

    assert result["content"]
    assert len(result["sources"]) == 2
    # One figure chunk and one text chunk: the figure-less citation is the
    # common office case and the one the SPA renders differently.
    assert [source["figure_id"] is None for source in result["sources"]] == [
        False,
        True,
    ]


@pytest.mark.parametrize(
    "key", ["content", "sources", "follow_ups", "rewrite", "tool_traces"]
)
def test_a_missing_required_key_names_itself(key):
    payload = contract.golden_answer()
    del payload[key]

    with pytest.raises(ContractViolation, match=key):
        validate_answer(payload, question=_Q)


def test_a_required_key_may_hold_an_empty_value():
    """Present-but-empty is a normal turn; absent is drift. That is the line."""
    result = validate_answer(
        _answer(sources=[], follow_ups=[], tool_traces=[], rewrite=None), question=_Q
    )

    assert result["sources"] == []
    assert result["tool_traces"] == []


def test_violations_carry_the_contract_version():
    """An office failure log must say which contract produced it."""
    with pytest.raises(ContractViolation, match=contract.CONTRACT_VERSION):
        validate_answer(_answer(content="   "), question=_Q)


def test_token_counts_stay_optional():
    """Agreed 2026-08-31 (건의 e): the RAG may omit them entirely."""
    payload = contract.golden_answer()
    assert "prompt_tokens" not in payload

    result = validate_answer(payload, question=_Q)

    assert result["prompt_tokens"] is None
    assert result["completion_tokens"] is None


def test_a_non_mapping_return_is_a_violation():
    with pytest.raises(ContractViolation, match="mapping"):
        validate_answer(["not", "a", "mapping"], question=_Q)


def test_empty_content_is_a_violation():
    """'No evidence found' is an answer and must be written as one."""
    with pytest.raises(ContractViolation, match="content"):
        validate_answer(_answer(content=" \n "), question=_Q)


def test_an_unknown_source_type_is_a_violation():
    payload = contract.golden_answer()
    payload["sources"][0]["source_type"] = "wiki"

    with pytest.raises(ContractViolation, match="source_type"):
        validate_answer(payload, question=_Q)


@pytest.mark.parametrize("key", ["source_id", "source_type", "title", "snippet"])
def test_a_citation_missing_a_required_field_names_it(key):
    payload = contract.golden_answer()
    del payload["sources"][0][key]

    with pytest.raises(ContractViolation, match=key):
        validate_answer(payload, question=_Q)


def test_optional_citation_fields_default_to_none():
    payload = _answer(
        sources=[{
            "source_id": "S1",
            "source_type": "meeting",
            "title": "주간 계측 회의",
            "snippet": "알람 이력 공유",
        }]
    )

    source = validate_answer(payload, question=_Q)["sources"][0]

    assert source["page"] is None
    assert source["figure_id"] is None
    assert source["locator"] is None


def test_a_trace_item_missing_a_key_names_it():
    payload = contract.golden_answer()
    del payload["tool_traces"][0]["result_count"]

    with pytest.raises(ContractViolation, match="result_count"):
        validate_answer(payload, question=_Q)


def test_over_long_source_lists_are_truncated_not_rejected():
    """The cap is chat's, and sending six is not a breach — it is six."""
    payload = _answer(sources=[
        {
            "source_id": f"S{index}",
            "source_type": "manual",
            "title": f"매뉴얼 {index}",
            "snippet": "근거",
        }
        for index in range(9)
    ])

    result = validate_answer(payload, question=_Q)

    assert len(result["sources"]) == contract.RESULT_LIMIT


def test_a_rewrite_equal_to_the_question_collapses_to_none():
    """Agreed 2026-08-31 (건의 c) — the SPA must not echo the user's words."""
    assert validate_answer(_answer(rewrite=_Q), question=_Q)["rewrite"] is None
    assert validate_answer(_answer(rewrite="다른 표현"), question=_Q)["rewrite"] == (
        "다른 표현"
    )


class _Signatures:
    @staticmethod
    def agreed(question, *, messages, scope, timeout):
        """What the contract says agent_query looks like."""

    @staticmethod
    def kwargs_only(question, **kwargs):
        """Also fine: chat passes the three by name."""

    @staticmethod
    def positional_only(question, messages, scope, timeout, /):
        """Rejects chat's call — everything after question is by name."""

    @staticmethod
    def no_timeout(question, *, messages, scope):
        """Cannot take the turn budget."""


def test_the_agreed_signature_passes():
    assert contract.validate_signature(_Signatures.agreed) == []
    assert contract.validate_signature(_Signatures.kwargs_only) == []


def test_a_positional_only_signature_is_reported():
    problems = contract.validate_signature(_Signatures.positional_only)

    assert problems and all("positional-only" in problem for problem in problems)


def test_a_signature_without_timeout_is_reported():
    problems = contract.validate_signature(_Signatures.no_timeout)

    assert problems == ["cannot be called with `timeout=`"]


def test_the_golden_call_carries_the_configured_budget():
    """Not a literal: the default moved 180 -> 240 once already.

    The runner prints this number to the office as "what chat sends", so a
    frozen copy here would quietly misinform them after the next change.
    """
    from back_dev_home.chat import config

    assert contract.golden_call()["timeout"] == config.get_answer_timeout()


def test_the_runner_reports_green_without_a_checkout(capsys):
    """What the RAG side sees before the index exists — no import, no index."""
    assert contract.main([]) == 0

    printed = capsys.readouterr().out
    assert contract.CONTRACT_VERSION in printed
    assert contract.CALL_TARGET in printed
    assert "golden payload validates" in printed
    # The exception table is part of the report: it is the half of the
    # contract a return-value validator cannot check.
    for raised, (translated, status) in contract.EXCEPTION_MAP.items():
        assert raised.__name__ in printed
        assert translated.__name__ in printed
        assert str(status) in printed
