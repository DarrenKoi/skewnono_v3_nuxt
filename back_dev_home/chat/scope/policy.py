"""Which questions this chat answers — one marker policy, everywhere.

The vocabulary is the RAG side's domain markers in Korean and English
(handoff ``docs/datatables/chat/chat_office_adapter_handoff.txt``, 2026-08-27),
and it is the same at home and at the office: scope is a product decision
about what SKEWNONO chat is for, not a fact about which machine is running.
There was a mock/office split here; it only ever meant "home refuses Korean
questions the office accepts", which is a difference no test wanted.

A marker policy rather than a model call, per the same handoff: the domain is
narrow and a false refusal costs more than letting a borderline question reach
retrieval, where empty evidence already produces an honest "no evidence found".

Every English marker has its Korean counterpart because users mix the two in
one question ("얼라인 alarm 리셋") — an English-only list would refuse Korean
questions the index answers fine. ``unsafe`` covers instructions to ignore
access control, reveal credentials or bypass permissions; that decision wins
over any in-scope marker beside it.

Substring matching on the lowercased query, deliberately: it errs toward
``in_scope``, and answering a borderline work question beats refusing it.
"""

from __future__ import annotations

import re

from back_dev_home.chat.scope.contracts import ScopeDecision

# Clause boundaries for mixed queries — punctuation, or a conjunction with
# spaces on both sides in either language. Korean particles that attach to
# the preceding word (``-하고``) are not split; the compact fallback below
# covers a query with no splittable boundary.
_CLAUSE_BOUNDARY = re.compile(
    r"(?:[,;.!?]+|\s+(?:and|but|or|그리고|및|또는)\s+)", re.IGNORECASE
)


def _contains_any(query: str, markers: tuple[str, ...]) -> bool:
    return any(marker in query for marker in markers)


def _supported_clause(
    query: str,
    in_scope: tuple[str, ...],
    out_of_scope: tuple[str, ...],
) -> str:
    supported: list[str] = []
    for clause in _CLAUSE_BOUNDARY.split(query):
        normalized = clause.lower()
        if _contains_any(normalized, in_scope) and not _contains_any(
            normalized, out_of_scope
        ):
            supported.append(clause.strip())
    if supported:
        return " ".join(supported).strip()

    # A compact query may put both topics in one unsplittable clause. Returning
    # only the matched domain terms stays fail-closed and never forwards the
    # original mixed request to retrieval.
    return " ".join(marker for marker in in_scope if marker in query.lower()).strip()


def _decide(
    query: str,
    *,
    in_scope: tuple[str, ...],
    out_of_scope: tuple[str, ...],
    unsafe: tuple[str, ...],
) -> ScopeDecision:
    normalized = query.lower()
    if _contains_any(normalized, unsafe):
        return {
            "status": "unsafe",
            "reason_code": "unsafe_instruction",
            "supported_query": None,
        }

    has_in_scope = _contains_any(normalized, in_scope)
    has_out_of_scope = _contains_any(normalized, out_of_scope)
    if has_in_scope and has_out_of_scope:
        return {
            "status": "mixed",
            "reason_code": "mixed_scope",
            "supported_query": _supported_clause(query, in_scope, out_of_scope) or None,
        }
    if has_in_scope:
        return {
            "status": "in_scope",
            "reason_code": "supported_domain",
            "supported_query": query,
        }
    return {
        "status": "out_of_scope",
        "reason_code": "unsupported_domain",
        "supported_query": None,
    }


_UNSAFE_MARKERS = (
    "ignore access", "reveal api key", "reveal the api key", "bypass permission",
    "권한 우회", "권한을 우회", "접근 제어 무시", "접근 권한 무시", "api 키 보여",
    "api 키 알려", "비밀번호 알려", "인증 우회",
)

# The handoff's marker list (EN), each paired with its Korean counterpart.
# Keep the handoff set intact — test_vocabulary_covers_every_handoff_marker
# pins it.
_IN_SCOPE_MARKERS = (
    # equipment / domain
    "ebeam", "e-beam", "이빔", "전자빔", "metrology", "계측", "measurement", "측정",
    "tool", "장비", "alarm", "알람", "manual", "매뉴얼", "recipe", "레시피",
    "error", "에러", "오류", "cd-sem", "cdsem", "sem", "calibration", "캘리브레이션",
    "교정", "optics", "광학", "vacuum", "진공", "stage", "스테이지", "wafer", "웨이퍼",
    "idp", "amp", "hitachi", "히타치", "gt2000", "cg6300", "align", "얼라인", "정렬",
    "beam", "빔", "focus", "초점", "포커스", "magnification", "배율",
    # the other knowledge sources
    "meeting", "회의", "email", "메일", "report", "보고서", "리포트", "tat",
)

_OUT_OF_SCOPE_MARKERS = (
    "movie", "영화", "shopping", "쇼핑", "dating", "데이트", "game", "게임",
    "주식", "stock tip", "날씨", "weather", "맛집", "restaurant", "여행", "travel",
    "로또", "lottery",
)


def classify(query: str) -> ScopeDecision:
    """Classify one chat query against the domain vocabulary."""
    return _decide(
        query,
        in_scope=_IN_SCOPE_MARKERS,
        out_of_scope=_OUT_OF_SCOPE_MARKERS,
        unsafe=_UNSAFE_MARKERS,
    )
