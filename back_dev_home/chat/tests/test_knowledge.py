"""Behavioral contract tests for the chat knowledge-provider seam."""

import pytest

from back_dev_home.chat.knowledge import data
from back_dev_home.chat.knowledge.contracts import KnowledgeUnavailable


METROLOGY_USER = {"user_id": "u1", "groups": ["metrology"], "fabs": []}
UNADDRESSED_USER = {"user_id": "u2", "groups": [], "fabs": []}


def test_manual_search_returns_page_provenance(monkeypatch):
    """Catches a manual adapter that loses its page-level evidence fields."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_manuals("alarm reset", {}, METROLOGY_USER, 5)

    assert rows[0]["source_type"] == "manual"
    assert rows[0]["page"] == 12
    assert rows[0]["revision"] == "R2"


@pytest.mark.parametrize(
    ("search", "query", "source_type"),
    [
        (data.search_manuals, "alarm reset", "manual"),
        (data.search_meeting_summaries, "process decision", "meeting"),
        (data.search_emails, "maintenance", "email"),
        (data.search_reports, "measurement", "report"),
    ],
)
def test_source_search_routes_to_its_own_fixture(monkeypatch, search, query, source_type):
    """Catches a public source search routed to the wrong provider dataset."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = search(query, None, METROLOGY_USER, 5)

    assert rows
    assert {row["source_type"] for row in rows} == {source_type}


def test_email_search_hides_unaddressed_fixture(monkeypatch):
    """Catches a provider that returns a user-restricted email to another user."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_emails("maintenance", None, UNADDRESSED_USER, 5)

    assert all(row["source_id"] != "email-private-u1" for row in rows)


def test_search_removes_private_fixture_metadata(monkeypatch):
    """Catches accidental exposure of access rules or search-only fixture text."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    row = data.search_manuals("alarm reset", {}, METROLOGY_USER, 5)[0]

    assert "access" not in row
    assert "search_text" not in row


def test_report_search_orders_tied_scores_by_source_id(monkeypatch):
    """Catches nondeterministic ordering when lexical scores are tied."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_reports("measurement", None, METROLOGY_USER, 5)

    assert [row["source_id"] for row in rows] == [
        "report-measurement-a",
        "report-measurement-b",
        "report-measurement-c",
    ]


def test_limit_is_clamped_to_five(monkeypatch):
    """Catches an unbounded public search request."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_reports("measurement", None, METROLOGY_USER, 99)

    assert len(rows) <= 5


def test_limit_is_clamped_to_at_least_one(monkeypatch):
    """Catches a zero limit that bypasses the public lower boundary."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_reports("measurement", None, METROLOGY_USER, 0)

    assert len(rows) == 1


def test_office_provider_does_not_fall_back_to_mock(monkeypatch):
    """Catches office mode silently exposing mock fixture results."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")

    with pytest.raises(KnowledgeUnavailable, match="office"):
        data.search_manuals("alarm reset", {}, METROLOGY_USER, 5)
