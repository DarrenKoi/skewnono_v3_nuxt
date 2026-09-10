"""Shared OpenSearch clause builders.

Every substring filter we send to OpenSearch has to answer the same two
questions, and getting either wrong is a silent home↔office divergence rather
than an error:

1. **Is the caller's text escaped?** A user typing ``*`` into a search box means
   a literal asterisk. Interpolated straight into a ``wildcard`` pattern it
   becomes a match-anything operator, so the office returns rows the home mock
   (a plain Python substring test) never would.
2. **Is the match case-insensitive?** The mocks compare ``needle.lower() in
   haystack.lower()``. A bare ``wildcard`` clause is case-SENSITIVE, so the same
   query silently returns fewer rows at the office than at home.

``meas_hist`` already answered both correctly; this module is that answer moved
somewhere the other features can reach it.
"""

from __future__ import annotations

from typing import Any


def escape_wildcard_literal(value: str) -> str:
    """Neutralize the wildcard operators inside caller-supplied text.

    The backslash must be escaped FIRST — doing it after ``*``/``?`` would
    double-escape the backslashes this function just inserted.
    """
    return value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")


def wildcard_clause(
    field: str,
    term: str,
    *,
    case_insensitive: bool = True,
) -> dict[str, Any]:
    """A ``*term*`` substring clause matching what the mocks do in memory.

    ``rewrite: constant_score`` skips scoring — these are pure filters, and the
    relevance score is discarded anyway.
    """
    return {
        "wildcard": {
            field: {
                "value": f"*{escape_wildcard_literal(term.strip())}*",
                "case_insensitive": case_insensitive,
                "rewrite": "constant_score",
            }
        }
    }
