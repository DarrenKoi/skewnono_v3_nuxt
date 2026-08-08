"""Contract for the shared wildcard builders.

These assert the two properties the feature-level tests depend on but state
only indirectly: that caller text cannot smuggle in wildcard operators, and
that matching is case-insensitive so office results match the mocks'
``needle.lower() in haystack.lower()``.
"""

from back_dev_home._core.opensearch import escape_wildcard_literal, wildcard_clause


def test_escape_neutralizes_wildcard_operators():
    assert escape_wildcard_literal("A*B?C") == "A\\*B\\?C"


def test_escape_handles_backslashes_before_the_operators():
    """Order matters: escaping `*` first, then `\\`, would double-escape the
    backslashes the `*` pass had just inserted, turning `*` back into a live
    operator preceded by a literal backslash."""
    assert escape_wildcard_literal("a\\*b") == "a\\\\\\*b"


def test_clause_wraps_the_escaped_term_in_substring_stars():
    clause = wildcard_clause("path", "  /api/sem  ")

    assert clause["wildcard"]["path"]["value"] == "*/api/sem*"


def test_clause_is_case_insensitive_by_default():
    assert wildcard_clause("path", "x")["wildcard"]["path"]["case_insensitive"] is True


def test_clause_skips_scoring_because_it_is_a_pure_filter():
    assert wildcard_clause("path", "x")["wildcard"]["path"]["rewrite"] == "constant_score"
