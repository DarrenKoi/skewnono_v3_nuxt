"""Behavioral contract tests for the chat knowledge-provider seam."""

import pytest

from back_dev_home.chat import figures
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
    assert rows[0]["section"] == "Alarm recovery"


def test_manual_rows_carry_only_what_the_office_index_returns(monkeypatch):
    """Catches the mock re-growing fields the office manual search never emits.

    The office ``search_manuals()`` returns source_id/title/snippet/section/
    page/figure_id/score (office 확인 2026-08-27) — no revision (manuals are
    not revised), no occurred_at, no region, no locator. A mock that fills
    them teaches the SPA a label format the office can never produce.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_manuals("alarm reset", {}, METROLOGY_USER, 5)

    assert rows
    for row in rows:
        assert row["revision"] is None
        assert row["occurred_at"] is None
        assert row["region"] is None
        assert row["locator"] is None


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


@pytest.mark.parametrize("query", ["alarm reset", "알람 리셋", "얼라인 alarm 리셋"])
def test_manual_search_answers_korean_and_english_alike(monkeypatch, query):
    """Catches a tokenizer that drops Hangul and reports 'no results'.

    A Korean question must not be answerable only because it happens to
    contain an English word. The failure this pins is silent: an empty token
    set short-circuits to [], which is indistinguishable from a real miss.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_manuals(query, {}, METROLOGY_USER, 5)

    assert rows
    assert rows[0]["source_id"] == "manual-alarm-r2-p12"


def test_figure_bearing_evidence_carries_an_opaque_figure_id(monkeypatch):
    """Catches figure_id being dropped, or carrying a storage key/path."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    row = data.search_manuals("alarm reset", {}, METROLOGY_USER, 5)[0]

    figure_id = row["figure_id"]
    assert figure_id == "SYN6300_1.EBEAM_ALARM_p12_i0"
    assert "/" not in figure_id and not figure_id.endswith(".webp")


def test_mock_figure_ids_are_servable_by_the_figure_route(monkeypatch):
    """Catches the mock drifting from what the serving route will accept.

    Asserted against the route's own validator rather than a copy of the
    pattern: a mock whose ids the route rejects renders no figure at home and
    would send someone hunting through the frontend for a backend disagreement.
    The office id shape carries a dot (``CG6300_1.HHTSEM_SYSTEM_p100_i0``),
    which is the property the fixtures exist to reproduce.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_manuals("alarm calibration optics", {}, METROLOGY_USER, 5)
    figure_ids = [row["figure_id"] for row in rows if row["figure_id"]]

    assert figure_ids
    for figure_id in figure_ids:
        assert "." in figure_id, figure_id
        assert figures.is_valid_figure_id(figure_id), figure_id


def test_text_evidence_reports_no_figure(monkeypatch):
    """Catches a provider inventing a figure for text-only evidence."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rows = data.search_emails("maintenance", None, METROLOGY_USER, 5)

    assert rows
    assert all(row["figure_id"] is None for row in rows)


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


from back_dev_home.chat.knowledge.data import available_sources

_ALL = ("manual", "meeting", "email", "report")


def test_available_sources_is_every_source_at_home(monkeypatch):
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", raising=False)
    assert available_sources() == _ALL


def test_available_sources_defaults_to_manual_at_the_office(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", raising=False)
    assert available_sources() == ("manual",)


def test_available_sources_reads_the_office_source_list(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", "email, manual")
    assert available_sources() == ("manual", "email")


def test_available_sources_rejects_an_unknown_source(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", "manual,wiki")
    with pytest.raises(ValueError):
        available_sources()


def test_available_sources_rejects_an_empty_source_list(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", "  ,  ")
    with pytest.raises(ValueError):
        available_sources()


def test_available_sources_does_not_import_the_office_module(monkeypatch):
    """Listing sources must not require the gitignored office.py to exist."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.delenv("SKEWNONO_CHAT_KNOWLEDGE_SOURCES", raising=False)
    assert available_sources() == ("manual",)


def test_mock_rewrite_expands_acronyms_bilingually(monkeypatch):
    """Stands in for the office LLM rewrite: acronyms expanded, KR/EN paired."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")

    rewritten = data.rewrite_query("CD-SEM 얼라인 alarm 리셋")

    assert rewritten.startswith("CD-SEM 얼라인 alarm 리셋")
    assert "critical dimension" in rewritten.lower()
    assert "알람" in rewritten
    assert "reset" in rewritten.lower()
    assert data.rewrite_query("hello") == "hello"


def test_mock_follow_ups_derive_from_the_cited_sources(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "mock")
    sources = data.search_manuals("alarm reset", {}, METROLOGY_USER, 5)

    follow_ups = data.generate_follow_ups("alarm reset", "Use the reset procedure.", sources)

    assert 3 <= len(follow_ups) <= 5
    assert len(set(follow_ups)) == len(follow_ups)
    assert all(isinstance(item, str) and item.strip() for item in follow_ups)
    assert sources[0]["title"] in follow_ups[0]
    assert data.generate_follow_ups("q", "a", []) == data.generate_follow_ups("q", "a", [])


def test_rewrite_and_follow_ups_route_to_the_office_provider(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_PROVIDER", "office")
    monkeypatch.setattr(data, "_OFFICE_MODULE", "back_dev_home.chat.knowledge.providers.definitely_missing")

    with pytest.raises(KnowledgeUnavailable):
        data.rewrite_query("q")
    with pytest.raises(KnowledgeUnavailable):
        data.generate_follow_ups("q", "a", [])
