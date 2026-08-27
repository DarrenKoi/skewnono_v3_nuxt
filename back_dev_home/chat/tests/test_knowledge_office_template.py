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


# The exact mapping the office RAG's ``search_manuals()`` returns per hit
# (office 확인 2026-08-27). Note what is NOT here: revision, occurred_at,
# region, locator. And what is: ``element_type``, an index-internal label.
_OFFICE_MANUAL_HIT = {
    "source_id": "CG6300_1.HHTSEM_SYSTEM#p100#c3",
    "title": "CG6300 System Manual",
    "snippet": "Synthetic snippet standing in for the approved evidence.",
    "section": "3.2 Alignment",
    "page": 100,
    "figure_id": "CG6300_1.HHTSEM_SYSTEM_p100_i0",
    "score": 0.83,
    "element_type": "figure_caption",
}


def test_the_office_manual_hit_shape_maps_without_the_absent_fields(seams):
    """Catches the contract half rejecting the office's real hit.

    ``_to_evidence`` reads the optional keys with ``.get``, so a hit that
    simply lacks revision/occurred_at/region/locator maps to ``None`` for
    each — the office copy does not have to pad them in.
    """
    seams["hits"] = [dict(_OFFICE_MANUAL_HIT)]
    seams["scores"] = [0.91]

    rows = template.search_manuals("alignment", None, _SCOPE, 5)

    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == _OFFICE_MANUAL_HIT["source_id"]
    assert row["figure_id"] == "CG6300_1.HHTSEM_SYSTEM_p100_i0"
    assert row["page"] == 100
    assert row["section"] == "3.2 Alignment"
    for absent in ("revision", "occurred_at", "region", "locator"):
        assert row[absent] is None


def test_element_type_stays_behind_the_seam(seams):
    """Catches ``element_type`` leaking into Evidence.

    The index carries it on every chunk and the office search returns it,
    but it is a retrieval-internal label (one enum with four axes pressed
    into it — see chat_rag_contract.txt) and not part of the Evidence
    contract the SPA renders. ``figure_id`` is the signal that crosses.
    """
    seams["hits"] = [dict(_OFFICE_MANUAL_HIT)]
    seams["scores"] = [0.91]

    rows = template.search_manuals("alignment", None, _SCOPE, 5)

    assert "element_type" not in rows[0]
    assert set(rows[0]) == {
        "source_id", "source_type", "title", "snippet", "revision",
        "occurred_at", "section", "page", "region", "locator", "figure_id",
        "score",
    }
