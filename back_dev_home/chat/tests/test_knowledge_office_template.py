"""Home coverage for the contract half of the office knowledge template.

``test_knowledge_office.py`` imports the gitignored ``providers.office`` copy
and therefore skips entirely at home — which leaves the tracked contract half
of ``office_example.py`` with no home coverage at all. The contract half is
byte-identical in both files, so exercising the template here pins the
behaviour the office copy inherits: candidate over-fetch, rerank ordering,
and the five-row cap that the application (not the adapter) owns.
"""

from __future__ import annotations

import pytest

from back_dev_home.chat.knowledge.contracts import KnowledgeUnavailable
from back_dev_home.chat.knowledge.providers import office_example as template


_SCOPE = {"user_id": "1234567", "groups": [], "fabs": []}


def _hit(source_id: str, score: float) -> dict:
    return {
        "source_id": source_id,
        "title": f"Manual {source_id}",
        "snippet": f"Synthetic snippet for {source_id}.",
        "revision": "R1",
        "occurred_at": None,
        "section": None,
        "page": 1,
        "region": None,
        "locator": f"manual:{source_id}#page=1",
        "figure_id": None,
        "score": score,
    }


@pytest.fixture
def seams(monkeypatch):
    """Patch the three seams the contract half calls and record what they were given.

    ``_config`` is the fourth OFFICE-TODO seam but is never patched here: the
    contract half (``_search`` / ``_rank_hits``) never calls it, so it has
    nothing to fake."""
    calls: dict = {}

    def fake_build_request(source_type, query, filters, scope, limit):
        calls["build_request_limit"] = limit
        return {"source_type": source_type, "query": query, "limit": limit}

    def fake_execute(source_type, request):
        return calls["hits"]

    def fake_rerank(source_type, query, hits):
        return calls["scores"]

    monkeypatch.setattr(template, "_build_request", fake_build_request)
    monkeypatch.setattr(template, "_execute", fake_execute)
    monkeypatch.setattr(template, "_rerank", fake_rerank)
    return calls


def test_candidate_pool_over_fetches_beyond_the_row_limit(seams, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_CANDIDATES", "31")
    seams["hits"] = [_hit("a", 1.0)]
    seams["scores"] = [1.0]

    template.search_manuals("alarm reset", None, _SCOPE, 5)

    assert seams["build_request_limit"] == 31


def test_rerank_reorders_and_replaces_the_score(seams):
    seams["hits"] = [_hit("a", 9.0), _hit("b", 8.0), _hit("c", 7.0)]
    seams["scores"] = [0.1, 0.9, 0.5]

    rows = template.search_manuals("alarm reset", None, _SCOPE, 5)

    assert [row["source_id"] for row in rows] == ["b", "c", "a"]
    assert [row["score"] for row in rows] == [0.9, 0.5, 0.1]


def test_ties_keep_the_backend_order(seams):
    seams["hits"] = [_hit("a", 1.0), _hit("b", 1.0)]
    seams["scores"] = [0.5, 0.5]

    rows = template.search_manuals("alarm reset", None, _SCOPE, 5)

    assert [row["source_id"] for row in rows] == ["a", "b"]


def test_the_five_row_cap_survives_a_large_candidate_pool(seams):
    seams["hits"] = [_hit(str(index), 1.0) for index in range(24)]
    seams["scores"] = [float(index) for index in range(24)]

    rows = template.search_manuals("alarm reset", None, _SCOPE, 5)

    assert len(rows) == 5
    assert [row["source_id"] for row in rows] == ["23", "22", "21", "20", "19"]


def test_a_rerank_score_count_mismatch_is_unavailable(seams):
    seams["hits"] = [_hit("a", 1.0), _hit("b", 1.0)]
    seams["scores"] = [0.5]

    with pytest.raises(KnowledgeUnavailable):
        template.search_manuals("alarm reset", None, _SCOPE, 5)


def test_a_non_numeric_rerank_score_is_unavailable(seams):
    seams["hits"] = [_hit("a", 1.0)]
    seams["scores"] = ["high"]

    with pytest.raises(KnowledgeUnavailable):
        template.search_manuals("alarm reset", None, _SCOPE, 5)


def test_a_nan_rerank_score_is_unavailable(seams):
    """NaN compares False against everything, so a stable sort would leave it
    wherever it landed and flask.jsonify would emit a bare NaN token that the
    SPA's JSON.parse cannot read on an otherwise-200 response."""
    seams["hits"] = [_hit("a", 1.0)]
    seams["scores"] = [float("nan")]

    with pytest.raises(KnowledgeUnavailable):
        template.search_manuals("alarm reset", None, _SCOPE, 5)


def test_an_infinite_rerank_score_is_unavailable(seams):
    seams["hits"] = [_hit("a", 1.0)]
    seams["scores"] = [float("inf")]

    with pytest.raises(KnowledgeUnavailable):
        template.search_manuals("alarm reset", None, _SCOPE, 5)


def test_a_blank_query_never_reaches_the_backend(seams):
    seams["hits"] = [_hit("a", 1.0)]
    seams["scores"] = [1.0]

    assert template.search_manuals("   ", None, _SCOPE, 5) == []
    assert "build_request_limit" not in seams


def test_empty_results_stay_empty(seams):
    seams["hits"] = []
    seams["scores"] = []

    assert template.search_manuals("alarm reset", None, _SCOPE, 5) == []


def test_an_unimplemented_rerank_seam_fails_loudly(monkeypatch):
    """Skipping the rerank silently would degrade quality without an error."""
    monkeypatch.setattr(
        template,
        "_build_request",
        lambda source_type, query, filters, scope, limit: {},
    )
    monkeypatch.setattr(template, "_execute", lambda source_type, request: [_hit("a", 1.0)])

    with pytest.raises(KnowledgeUnavailable):
        template.search_manuals("alarm reset", None, _SCOPE, 5)
