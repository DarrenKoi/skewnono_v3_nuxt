"""Synthetic deterministic scope policy, not a production classifier."""

from __future__ import annotations

import re

from back_dev_home.chat.scope.contracts import ScopeDecision


_UNSAFE_MARKERS = ("ignore access", "reveal api key", "bypass permission")
_IN_SCOPE_MARKERS = (
    "e-beam", "ebeam", "metrology", "measurement", "tool", "alarm", "manual",
    "meeting", "email", "report", "tat",
)
_OUT_OF_SCOPE_MARKERS = ("movie", "shopping", "dating", "game")
_CLAUSE_BOUNDARY = re.compile(r"(?:[,;.!?]+|\s+(?:and|but|or)\s+)", re.IGNORECASE)


def _contains_any(query: str, markers: tuple[str, ...]) -> bool:
    return any(marker in query for marker in markers)


def _supported_clause(query: str) -> str:
    clauses = _CLAUSE_BOUNDARY.split(query)
    supported: list[str] = []
    for clause in clauses:
        if _contains_any(clause.lower(), _OUT_OF_SCOPE_MARKERS):
            break
        supported.append(clause)
    return " ".join(supported).strip()


def classify(query: str) -> ScopeDecision:
    """Return a deterministic scaffold-only decision for *query*."""
    normalized = query.lower()
    if _contains_any(normalized, _UNSAFE_MARKERS):
        return {
            "status": "unsafe",
            "reason_code": "unsafe_instruction",
            "supported_query": None,
        }

    has_in_scope = _contains_any(normalized, _IN_SCOPE_MARKERS)
    has_out_of_scope = _contains_any(normalized, _OUT_OF_SCOPE_MARKERS)
    if has_in_scope and has_out_of_scope:
        return {
            "status": "mixed",
            "reason_code": "mixed_scope",
            "supported_query": _supported_clause(query) or None,
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
