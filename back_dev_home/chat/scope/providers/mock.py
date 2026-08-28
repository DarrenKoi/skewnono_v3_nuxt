"""Synthetic deterministic scope policy, not a production classifier.

Same engine as the office provider (``scope/keyword_policy.py``) with a
deliberately small English vocabulary, so home tests read plainly. The office
template carries the real domain markers in Korean and English.
"""

from __future__ import annotations

from back_dev_home.chat.scope import keyword_policy
from back_dev_home.chat.scope.contracts import ScopeDecision


_UNSAFE_MARKERS = ("ignore access", "reveal api key", "bypass permission")
_IN_SCOPE_MARKERS = (
    "e-beam", "ebeam", "metrology", "measurement", "tool", "alarm", "manual",
    "meeting", "email", "report", "tat",
)
_OUT_OF_SCOPE_MARKERS = ("movie", "shopping", "dating", "game")


def classify(query: str) -> ScopeDecision:
    """Return a deterministic scaffold-only decision for *query*."""
    return keyword_policy.classify(
        query,
        in_scope=_IN_SCOPE_MARKERS,
        out_of_scope=_OUT_OF_SCOPE_MARKERS,
        unsafe=_UNSAFE_MARKERS,
    )
