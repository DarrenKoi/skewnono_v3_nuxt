"""Marker-based scope policy shared by the mock and office scope providers.

One engine, two vocabularies: the mock passes a small English list so home
tests stay legible, the office passes the RAG side's domain markers in both
Korean and English. Sharing the engine is what keeps the two from drifting —
a fix to clause splitting or the fail-closed mixed handling lands in both.

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


def classify(
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
