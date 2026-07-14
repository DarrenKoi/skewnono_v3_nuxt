"""OpenSearch contract for Skewvoir's uncategorized ``q`` fallback.

Home search evaluates the same field allowlist in memory. The office data
adapter should index ``build_search_all_value(row)`` into a field mapped with
``SEARCH_ALL_MAPPING`` and add ``build_q_fallback_clause(q)`` to its bool query.

Why a dedicated field: leading ``*term*`` queries on ordinary keyword fields
are expensive and may be disabled by ``search.allow_expensive_queries``. The
OpenSearch ``wildcard`` field type is specifically indexed for arbitrary
substring and regular-expression matching.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SEARCH_ALL_FIELD = "search_all"
SEARCH_ALL_MAPPING: dict[str, str] = {"type": "wildcard"}

# This fixed allowlist is the cross-phase search contract. Do not use dynamic
# ``*`` field expansion: new numeric or operational fields must not silently
# become searchable and broaden results.
SEARCHABLE_SOURCE_FIELDS = (
    "fac_id",
    "fab_name",
    "vendor_nm",
    "eqp_id",
    "eqp_model_cd",
    "lot_cd",
    "lot_id",
    "class_name",
    "recipe_name",
    "full_name",
    "msr",
    "idp_name",
    "idw_name",
)


def build_search_all_value(row: Mapping[str, Any]) -> str:
    """Create the denormalized value stored in the office wildcard field."""
    return " ".join(
        str(row[field]).strip()
        for field in SEARCHABLE_SOURCE_FIELDS
        if row.get(field) is not None and str(row[field]).strip()
    )


def _escape_wildcard_literal(value: str) -> str:
    """Treat user ``*``/``?`` characters literally inside our wildcard."""
    return value.replace("\\", "\\\\").replace("*", "\\*").replace("?", "\\?")


def build_q_fallback_clause(terms: Sequence[str]) -> dict[str, Any] | None:
    """Build the OR-across-terms clause used by the office data adapter."""
    patterns = [
        f"*{_escape_wildcard_literal(term.strip())}*"
        for term in terms
        if term.strip()
    ]
    if not patterns:
        return None

    return {
        "bool": {
            "should": [
                {
                    "wildcard": {
                        SEARCH_ALL_FIELD: {
                            "value": pattern,
                            "case_insensitive": True,
                            "rewrite": "constant_score",
                        }
                    }
                }
                for pattern in patterns
            ],
            "minimum_should_match": 1,
        }
    }
