"""The chat ↔ RAG answer contract, as code both sides can run.

Chat and the RAG live in two environments that never meet: the RAG is a
separate 사내 repository delivered as ``_rag/skewnono_rag/``, and its
dependencies (faiss, torch, langgraph) cannot be installed at home. Until this
module existed, the agreement between them was prose — seven letters under
``chat/docs/``, relayed by a human — and every mismatch first surfaced as a
failure during office verification.

This module IS the agreement. It is executed by both sides:

* **chat** calls :func:`validate_answer` on every office turn
  (``answer/providers/rag.py``), so a drifting RAG produces a 503 that names
  the field rather than a silently degraded answer.
* **the RAG side** runs it directly in the office runtime::

      python -m scripts.verify.check_answer_contract          # 계약 출력 + 자체 검사
      python -m scripts.verify.check_answer_contract --live   # 실제 agent_query 1회 호출

  The first form needs no index and no chat process — it prints the call
  shape, the exception mapping and the field rules, then checks the golden
  payload against the validator. The second imports the co-located RAG,
  inspects ``agent_query``'s signature, calls it once and validates the
  result field by field.

Deliberately dependency-free (stdlib plus this feature's own contracts), so it
imports in the RAG's environment as readily as in chat's.

Precedence, so the three places do not compete silently:

* **This file wins on executable facts** — required keys, value shapes, the
  call signature, the exception mapping.
* ``docs/datatables/hitachi/chat_rag_contract.txt`` **wins on meaning** —
  what makes a ``source_id`` stable, what a ``snippet`` is allowed to contain,
  that the AccessScope filter must run over the whole candidate pool before
  the five-row cut rather than after it. None of that is checkable here.
* The letters in ``chat/docs/`` are the negotiation, not the agreement.

**Tolerance is the thing this module removes.** The rule is: a required key
must be PRESENT; its value may be empty. ``tool_traces: []`` is a normal turn
that used no tool; a missing ``tool_traces`` is drift, and it used to arrive
as an empty list and cost the UI a feature with nothing raised anywhere. The
one agreed exception is the token counts, which the RAG may omit entirely
(agreed 2026-08-31, 건의 (e)).
"""

from __future__ import annotations

import inspect
from typing import Any, Mapping, TypedDict

from back_dev_home.chat.contracts import (
    Evidence,
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
    ToolTrace,
)

__all__ = [
    "AnswerResult",
    "CONTRACT_VERSION",
    "ContractViolation",
    "CALL_TARGET",
    "EXCEPTION_MAP",
    "RESULT_LIMIT",
    "validate_answer",
    "validate_signature",
    "golden_answer",
    "golden_call",
    "main",
]


# Bumped whenever a rule here changes, and carried in every violation message
# so an office failure log says which contract it ran rather than leaving that
# to be matched by hand. A date rather than semver: two parties and one
# function, and this repo already dates its provenance marks.
CONTRACT_VERSION = "2026-09-01"


class AnswerResult(TypedDict):
    """What one turn returns, after validation and normalization.

    Mirrors what ``agent_query`` gives back, with this module's rules already
    applied: sources capped, optional fields defaulted, ``rewrite`` collapsed
    to None when it merely repeated the question.
    """

    content: str
    sources: list[Evidence]
    follow_ups: list[str]
    rewrite: str | None
    tool_traces: list[ToolTrace]
    prompt_tokens: int | None
    completion_tokens: int | None

# The one entry point. Named here so the letter, the runner and the adapter
# cannot disagree about it.
CALL_TARGET = "skewnono_rag.retrieve.agent.agent_query"

# What the RAG raises → what chat raises → what the SPA gets. Any exception
# outside this table is a 503. Pinned by test_answer_rag.py against the real
# adapter, so this stays a declaration the code honours rather than a comment.
EXCEPTION_MAP: dict[type[BaseException], tuple[type[Exception], int]] = {
    TimeoutError: (KnowledgeTimeout, 504),
    PermissionError: (KnowledgeDenied, 403),
}

# The citation cap. Application-owned: chat decides how many rows the answer
# may cite, and neither the model nor the RAG can raise it — the same rule
# docs/datatables/hitachi/chat_rag_contract.txt states. Over-long lists are
# truncated here, not rejected: sending six is not a contract breach.
RESULT_LIMIT = 5

_REQUIRED_ANSWER_KEYS = ("content", "sources", "follow_ups", "rewrite", "tool_traces")
_OPTIONAL_ANSWER_KEYS = ("prompt_tokens", "completion_tokens")

_REQUIRED_SOURCE_KEYS = ("source_id", "source_type", "title", "snippet")
_OPTIONAL_SOURCE_KEYS = (
    "revision",
    "occurred_at",
    "section",
    "page",
    "region",
    "locator",
    "figure_id",
    "score",
)
_SOURCE_TYPES = frozenset({"manual", "meeting", "email", "report"})

_TRACE_KEYS = ("tool_name", "query", "result_count", "duration_ms", "status")

# The call chat actually makes: question positional, everything else keyword.
_CALL_KEYWORDS = ("messages", "scope", "timeout")


class ContractViolation(KnowledgeUnavailable):
    """The RAG answered, but not in the agreed shape.

    Subclasses ``KnowledgeUnavailable`` on purpose: ``routes.py`` already
    turns that into a 503, so a violation needs no new translation while
    still being catchable on its own.
    """


def _fail(detail: str) -> ContractViolation:
    return ContractViolation(f"[answer contract {CONTRACT_VERSION}] {detail}")


def validate_answer(raw: Any, *, question: str) -> AnswerResult:
    """Check one ``agent_query`` return value and normalize it.

    Validation and normalization are one function because the normalization
    rules ARE contract terms — the five-row cap, ``rewrite`` collapsing to
    None when it equals the question, optional fields defaulting to None.
    Splitting them would put the same rules in two places, which is the drift
    this module exists to stop.
    """
    if not isinstance(raw, Mapping):
        raise _fail(f"{CALL_TARGET} must return a mapping, got {type(raw).__name__}.")

    missing = [key for key in _REQUIRED_ANSWER_KEYS if key not in raw]
    if missing:
        raise _fail(
            f"{CALL_TARGET} returned no {', '.join(missing)}. Required keys must be "
            f"present; an empty value is fine (tool_traces=[] is a turn that used "
            f"no tool). Optional keys: {', '.join(_OPTIONAL_ANSWER_KEYS)}."
        )

    content = raw["content"]
    if not isinstance(content, str) or not content.strip():
        raise _fail(
            "content must be a nonempty string. 'no evidence found' is an answer "
            "and must be written as one. chat reports an empty content as 503."
        )

    sources = raw["sources"] or []
    if not isinstance(sources, list):
        raise _fail(f"sources must be a list, got {type(sources).__name__}.")

    traces = raw["tool_traces"] or []
    if not isinstance(traces, list):
        raise _fail(f"tool_traces must be a list, got {type(traces).__name__}.")
    for index, trace in enumerate(traces):
        if not isinstance(trace, Mapping):
            raise _fail(f"tool_traces[{index}] must be a mapping.")
        absent = [key for key in _TRACE_KEYS if key not in trace]
        if absent:
            raise _fail(
                f"tool_traces[{index}] is missing {', '.join(absent)}. "
                f"Expected keys: {', '.join(_TRACE_KEYS)}."
            )

    follow_ups = raw["follow_ups"] or []
    if not isinstance(follow_ups, list):
        raise _fail(f"follow_ups must be a list, got {type(follow_ups).__name__}.")

    rewrite = raw["rewrite"] or None
    if rewrite is not None and not isinstance(rewrite, str):
        raise _fail(f"rewrite must be a string or None, got {type(rewrite).__name__}.")
    if rewrite == question:
        # Agreed 2026-08-31 (건의 c): a rewrite equal to the question is no
        # rewrite, and the SPA must not show the user their own words back.
        rewrite = None

    return {
        "content": content.strip(),
        "sources": [
            _to_evidence(hit, index) for index, hit in enumerate(sources[:RESULT_LIMIT])
        ],
        "follow_ups": [str(item) for item in follow_ups],
        "rewrite": rewrite,
        "tool_traces": [dict(trace) for trace in traces],
        # The one agreed-optional pair: absent and None are both fine.
        "prompt_tokens": raw.get("prompt_tokens"),
        "completion_tokens": raw.get("completion_tokens"),
    }


def _to_evidence(hit: Any, index: int) -> Evidence:
    if not isinstance(hit, Mapping):
        raise _fail(f"sources[{index}] must be a mapping, got {type(hit).__name__}.")
    for key in _REQUIRED_SOURCE_KEYS:
        if not hit.get(key):
            raise _fail(
                f"sources[{index}] is missing {key!r}. Required on every citation: "
                f"{', '.join(_REQUIRED_SOURCE_KEYS)}."
            )
    source_type = hit["source_type"]
    if source_type not in _SOURCE_TYPES:
        raise _fail(
            f"sources[{index}].source_type is {source_type!r}; expected one of "
            f"{', '.join(sorted(_SOURCE_TYPES))}. The search function stamps it: "
            "a value carried inside the raw hit is not trusted."
        )
    evidence: dict[str, Any] = {key: hit[key] for key in _REQUIRED_SOURCE_KEYS}
    for key in _OPTIONAL_SOURCE_KEYS:
        evidence[key] = hit.get(key)
    return evidence  # type: ignore[return-value]


def validate_signature(func: Any) -> list[str]:
    """Problems with ``agent_query``'s signature; empty list when it fits.

    Chat calls ``agent_query("질문", messages=[...], scope={...}, timeout=…)``
    — question positional, the rest keyword. A signature that cannot accept
    that raises ``TypeError`` at the office and nowhere else, which is exactly
    the class of failure this module exists to move earlier.
    """
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return []  # not introspectable; the live call is the only check left

    problems: list[str] = []
    parameters = signature.parameters
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    positional = [
        parameter
        for parameter in parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if not positional:
        problems.append("no positional parameter for `question`")

    for keyword in _CALL_KEYWORDS:
        parameter = parameters.get(keyword)
        if parameter is None:
            if not accepts_kwargs:
                problems.append(f"cannot be called with `{keyword}=`")
        elif parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            problems.append(f"`{keyword}` is positional-only; chat passes it by name")
    return problems


def golden_call() -> dict[str, Any]:
    """The call chat makes, as data. ``timeout`` is the WHOLE-turn budget.

    ``timeout`` is read from the running configuration rather than written as
    a literal: the default has already moved once (180 -> 240 on 2026-09-01),
    and a number frozen here would have gone on telling the office a figure
    chat no longer sends. Everything else is an example; this one is a fact.
    """
    from back_dev_home.chat.config import get_answer_timeout

    return {
        "question": "GT2000 얼라인 알람 리셋 절차 알려줘",
        "messages": [
            {"role": "user", "content": "얼라인 알람이 자꾸 뜹니다"},
            {"role": "assistant", "content": "어느 장비인지 알려주시겠습니까?"},
        ],
        "scope": {"user_id": "2067928", "groups": [], "fabs": []},
        "timeout": get_answer_timeout(),
    }


def golden_answer() -> dict[str, Any]:
    """A return value that satisfies the contract — the shape to match.

    Two citations on purpose: one figure chunk and one text chunk. The
    text chunk's ``figure_id: None`` is the COMMON case at the office, and it
    is the one the SPA renders differently.
    """
    return {
        "content": (
            "GT2000 의 얼라인 알람은 스테이지 원점 재설정 후 리셋합니다. "
            "매뉴얼 4.2 절의 순서를 따르십시오."
        ),
        "sources": [
            {
                "source_id": "CG6300_1.HHTSEM_SYSTEM#c412",
                "source_type": "manual",
                "title": "CG6300 SYSTEM MANUAL",
                "snippet": "4.2 Alignment alarm reset: return the stage to origin.",
                "section": "4.2",
                "page": 100,
                "figure_id": "CG6300_1.HHTSEM_SYSTEM_p100_i0",
                "locator": "manual:CG6300_1.HHTSEM_SYSTEM#page=100",
                "score": 0.8421,
            },
            {
                "source_id": "GT2000_MAINT#c77",
                "source_type": "manual",
                "title": "GT2000 유지보수 지침",
                "snippet": "얼라인 알람 발생 시 원점 복귀를 먼저 수행합니다.",
                "section": "3.1",
                "page": 42,
                "figure_id": None,
                "locator": "manual:GT2000_MAINT#page=42",
                "score": 0.7734,
            },
        ],
        "follow_ups": [
            "스테이지 원점 재설정 절차를 자세히 알려줘",
            "같은 알람이 반복되면 무엇을 확인해야 하나요?",
            "Which other tools share this alignment sequence?",
        ],
        "rewrite": "GT2000 alignment alarm reset 얼라인 알람 리셋 절차",
        "tool_traces": [
            {
                "tool_name": "search_manuals",
                "query": "GT2000 alignment alarm reset",
                "result_count": 2,
                "duration_ms": 412,
                "status": "success",
            }
        ],
    }


def _report() -> list[str]:
    call = golden_call()
    lines = [
        f"chat <-> RAG answer contract {CONTRACT_VERSION}",
        "",
        f"  call       {CALL_TARGET}",
        f"             question positional; {', '.join(_CALL_KEYWORDS)} by keyword",
        f"  timeout    whole-turn budget in seconds (chat sends {call['timeout']!r})",
        f"  scope      {call['scope']!r}  (groups/fabs empty for now = unrestricted)",
        "",
        f"  required   {', '.join(_REQUIRED_ANSWER_KEYS)}",
        "             present, but the value may be empty ([] is a normal turn)",
        f"  optional   {', '.join(_OPTIONAL_ANSWER_KEYS)}  (omit or None both fine)",
        f"  citation   {', '.join(_REQUIRED_SOURCE_KEYS)} required; "
        f"{', '.join(_OPTIONAL_SOURCE_KEYS)} optional",
        f"             at most {RESULT_LIMIT} rows - chat truncates, it does not reject",
        f"  trace item {', '.join(_TRACE_KEYS)}",
        "",
        "  exceptions",
    ]
    for raised, (translated, status) in EXCEPTION_MAP.items():
        lines.append(
            f"             {raised.__name__:<16} -> {translated.__name__} -> HTTP {status}"
        )
    lines.append("             anything else    -> KnowledgeUnavailable -> HTTP 503")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Print the contract, check the golden payload, optionally call for real."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    live = "--live" in args
    if live:
        args.remove("--live")

    print("\n".join(_report()))
    print()

    try:
        validate_answer(golden_answer(), question=golden_call()["question"])
    except ContractViolation as violation:
        print(f"FAIL  golden payload does not satisfy its own validator: {violation}")
        return 1
    print("ok    golden payload validates")

    if not live:
        print()
        print("Add --live to call the co-located RAG once and validate the result.")
        return 0

    from back_dev_home.chat import rag

    try:
        module = rag.import_rag("retrieve.agent")
    except KnowledgeUnavailable as error:
        print(f"FAIL  {error}")
        return 1
    print(f"ok    imported {CALL_TARGET}")

    problems = validate_signature(module.agent_query)
    if problems:
        for problem in problems:
            print(f"FAIL  signature: {problem}")
        return 1
    print("ok    signature accepts chat's call")

    call = golden_call()
    if args:
        call["question"] = " ".join(args)
    print(f"...   calling agent_query({call['question']!r})")
    try:
        raw = module.agent_query(
            call["question"],
            messages=call["messages"],
            scope=call["scope"],
            timeout=call["timeout"],
        )
    except Exception as error:  # noqa: BLE001 — the runner reports, never crashes
        # isinstance, not an exact type lookup: the adapter's `except
        # TimeoutError` catches subclasses too, and a runner that KeyError'd on
        # one would print a traceback instead of the diagnosis (README rule 6).
        for raised, (translated, status) in EXCEPTION_MAP.items():
            if isinstance(error, raised):
                print(
                    f"ok    raised {type(error).__name__} -> "
                    f"{translated.__name__} -> {status}"
                )
                return 0
        print(f"FAIL  {type(error).__name__}: {error}  -> HTTP 503")
        return 1

    try:
        result = validate_answer(raw, question=call["question"])
    except ContractViolation as violation:
        print(f"FAIL  {violation}")
        return 1

    print("ok    result satisfies the contract")
    print(f"        content      {len(result['content'])} chars")
    print(f"        sources      {len(result['sources'])} (cap {RESULT_LIMIT})")
    print(f"        follow_ups   {len(result['follow_ups'])}")
    print(f"        rewrite      {'yes' if result['rewrite'] else 'none (unchanged)'}")
    print(f"        tool_traces  {len(result['tool_traces'])}")
    figure_less = sum(1 for hit in result["sources"] if hit["figure_id"] is None)
    print(f"        figure_id    {len(result['sources']) - figure_less} of "
          f"{len(result['sources'])} citations carry one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
