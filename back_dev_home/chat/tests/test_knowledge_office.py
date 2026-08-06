"""Fake-client contract tests for the gitignored chat knowledge office adapter.

At home ``knowledge/providers/office.py`` does not exist, so this module
skips. At the office, after ``cp office_example.py office.py``, it runs
against the real copy WITHOUT calling any live service: the backend seams
(``_build_request`` / ``_execute``) are monkeypatched with fakes.

The pre-written tests pin the contract half of the skeleton (validation,
limits, typed errors, no fallback). The OFFICE-TODO section at the bottom is
where the office implementation adds fake-raw-client tests for its own
``_build_request``/``_execute`` — query-time access filtering above all.
"""

from __future__ import annotations

import pytest

from back_dev_home.chat import config
from back_dev_home.chat.knowledge.contracts import (
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)

office = pytest.importorskip(
    "back_dev_home.chat.knowledge.providers.office",
    reason="knowledge/providers/office.py is an office-only gitignored copy",
)


_SCOPE = {"user_id": "1234567", "groups": [], "fabs": []}

_RAW_HIT = {
    "source_id": "manual-synthetic-r1-p3",
    "title": "Synthetic Office Manual",
    "snippet": "Synthetic snippet used only to exercise the mapping.",
    "revision": "R1",
    "occurred_at": None,
    "section": "Recovery",
    "page": 3,
    "region": "steps-1-2",
    "locator": "manual-synthetic-r1#page=3",
    "figure_id": "fig-synthetic-r1-p3",
    "score": 12.5,
}


def _passthrough_request(monkeypatch):
    monkeypatch.setattr(
        office,
        "_build_request",
        lambda source_type, query, filters, scope, limit: {
            "query": query,
            "limit": limit,
        },
    )


def _fake_execute(monkeypatch, hits):
    calls = []

    def fake(source_type, request):
        calls.append((source_type, request))
        return hits

    monkeypatch.setattr(office, "_execute", fake)
    return calls


@pytest.mark.parametrize(
    ("search", "source_type"),
    [
        (office.search_manuals, "manual"),
        (office.search_meeting_summaries, "meeting"),
        (office.search_emails, "email"),
        (office.search_reports, "report"),
    ],
)
def test_each_search_maps_raw_hits_and_stamps_source_type(
    monkeypatch, search, source_type
):
    """Catches a search function dropping fields or trusting hit source_type."""
    _passthrough_request(monkeypatch)
    _fake_execute(monkeypatch, [dict(_RAW_HIT, source_type="report")])
    monkeypatch.setattr(
        office,
        "_rerank",
        lambda source_type, query, hits: [hit["score"] for hit in hits],
    )

    rows = search("alarm reset", None, _SCOPE, 5)

    assert len(rows) == 1
    row = rows[0]
    assert row["source_type"] == source_type
    for key in (
        "source_id",
        "title",
        "snippet",
        "revision",
        "occurred_at",
        "section",
        "page",
        "region",
        "locator",
        "figure_id",
    ):
        assert row[key] == _RAW_HIT[key]
    assert row["score"] == pytest.approx(12.5)


def test_empty_results_stay_empty(monkeypatch):
    """Catches empty retrieval being padded from mock or another source."""
    _passthrough_request(monkeypatch)
    _fake_execute(monkeypatch, [])

    assert office.search_manuals("alarm", None, _SCOPE, 5) == []


def test_blank_query_short_circuits_without_backend_call(monkeypatch):
    """Catches blank queries reaching the office backend."""
    _passthrough_request(monkeypatch)
    calls = _fake_execute(monkeypatch, [dict(_RAW_HIT)])

    assert office.search_manuals("   ", None, _SCOPE, 5) == []
    assert calls == []


def test_limit_is_clamped_and_truncates_hits(monkeypatch):
    """Catches the adapter exceeding the application result cap."""
    _passthrough_request(monkeypatch)
    hits = [dict(_RAW_HIT, source_id=f"manual-synthetic-{i}") for i in range(9)]
    calls = _fake_execute(monkeypatch, hits)
    monkeypatch.setattr(
        office,
        "_rerank",
        lambda source_type, query, hits: [
            float(len(hits) - index) for index in range(len(hits))
        ],
    )

    rows = office.search_manuals("alarm", None, _SCOPE, 99)

    assert [row["source_id"] for row in rows] == [
        f"manual-synthetic-{i}" for i in range(5)
    ]
    assert calls[0][1]["limit"] == config.get_knowledge_candidate_pool()


def test_rerank_order_decides_the_final_order(monkeypatch):
    """The rerank score, not the backend's retrieval rank, decides the final order.

    backend 순위가 아니라 리랭크 점수가 최종 순서를 정한다.
    """
    _passthrough_request(monkeypatch)
    hits = [
        dict(_RAW_HIT, source_id="manual-b", score=1.0),
        dict(_RAW_HIT, source_id="manual-a", score=9.0),
    ]
    _fake_execute(monkeypatch, hits)
    monkeypatch.setattr(
        office,
        "_rerank",
        lambda source_type, query, hits: [
            float(len(hits) - index) for index in range(len(hits))
        ],
    )

    rows = office.search_manuals("alarm", None, _SCOPE, 5)

    assert [row["source_id"] for row in rows] == ["manual-b", "manual-a"]


@pytest.mark.parametrize(
    "broken",
    [
        {"source_id": ""},
        {"title": None},
        {"snippet": 7},
        {"page": 0},
        {"page": True},
        {"revision": 2},
        {"figure_id": 7},
    ],
)
def test_malformed_hits_raise_unavailable(monkeypatch, broken):
    """Catches schema drift being passed through as citations.

    ``score`` is deliberately not parametrized here: ``_rank_hits`` always
    overwrites a hit's ``score`` with the rerank score before ``_to_evidence``
    ever sees it, so a malformed raw ``score`` on the input hit can never
    reach the validation this test exercises. The non-numeric-rerank-score
    case lives in ``test_knowledge_office_template.py`` instead, against the
    contract half that actually produces the value.
    """
    _passthrough_request(monkeypatch)
    _fake_execute(monkeypatch, [dict(_RAW_HIT, **broken)])
    monkeypatch.setattr(
        office,
        "_rerank",
        lambda source_type, query, hits: [hit["score"] for hit in hits],
    )

    with pytest.raises(KnowledgeUnavailable):
        office.search_manuals("alarm", None, _SCOPE, 5)


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (KnowledgeDenied("denied"), KnowledgeDenied),
        (KnowledgeTimeout("slow"), KnowledgeTimeout),
        (KnowledgeUnavailable("down"), KnowledgeUnavailable),
        (TimeoutError("socket"), KnowledgeTimeout),
        (PermissionError("403"), KnowledgeDenied),
        (RuntimeError("mystery client failure"), KnowledgeUnavailable),
    ],
)
def test_backend_errors_become_typed_exceptions(monkeypatch, raised, expected):
    """Catches raw client exceptions or silent downgrades escaping the seam."""
    _passthrough_request(monkeypatch)

    def explode(source_type, request):
        raise raised

    monkeypatch.setattr(office, "_execute", explode)

    with pytest.raises(expected):
        office.search_emails("alarm", None, _SCOPE, 5)


# ---------------------------------------------------------------------------
# OFFICE-TODO — fake-raw-client tests for the office implementation.
#
# Implement these against the real _build_request/_execute with an injected
# fake client (never a live service). Assertions must not contain real source
# content, internal hostnames, index names, or credentials.
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="OFFICE-TODO: implement against the office _build_request")
def test_access_scope_is_embedded_in_the_backend_query():
    """The user_id/groups/fabs filter must be part of the query itself.

    OFFICE-TODO: call office._build_request with a scope and assert the
    generated backend request restricts results at query time. Post-search
    filtering is a contract violation — this test is the proof it is absent.
    """


@pytest.mark.skip(reason="OFFICE-TODO: implement against the office _execute")
def test_raw_backend_rows_normalize_to_the_documented_hit_shape():
    """OFFICE-TODO: feed a captured (de-identified) raw backend row through a
    fake client and assert _execute returns the normalized raw hit shape,
    including 1-based page numbers and None for absent provenance."""


@pytest.mark.skip(reason="OFFICE-TODO: implement against the office _translate_error")
def test_office_client_errors_map_to_typed_exceptions():
    """OFFICE-TODO: raise the office client library's real authorization and
    timeout exception types and assert they map to KnowledgeDenied and
    KnowledgeTimeout respectively."""
