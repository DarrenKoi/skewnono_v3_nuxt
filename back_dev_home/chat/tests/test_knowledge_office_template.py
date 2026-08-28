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


def test_a_failing_rerank_seam_fails_loudly(monkeypatch):
    """Skipping the rerank silently would degrade quality without an error."""
    monkeypatch.setattr(
        template,
        "_build_request",
        lambda source_type, query, filters, scope, limit: {},
    )
    monkeypatch.setattr(template, "_execute", lambda source_type, request: [_hit("a", 1.0)])

    def broken(source_type, query, hits):
        raise RuntimeError("reranker down")

    monkeypatch.setattr(template, "_rerank", broken)

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


# ---------------------------------------------------------------------------
# The seams themselves. The template is the COMPLETE office implementation
# (the RAG is called in-process through ``chat/rag.py``), so office.py is a
# byte-identical copy and these tests run against both when the copy exists.
# The RAG package is never imported for real: ``skewnono_rag.retrieve.*`` is a fake
# planted in ``sys.modules``.
# ---------------------------------------------------------------------------

import importlib  # noqa: E402
import sys  # noqa: E402
import types  # noqa: E402

from back_dev_home.chat import config, rag  # noqa: E402


def _adapters():
    modules = [template]
    try:
        office = importlib.import_module("back_dev_home.chat.knowledge.providers.office")
    except ModuleNotFoundError:
        return modules
    return modules + [office]


@pytest.fixture(params=_adapters(), ids=lambda module: module.__name__.rsplit(".", 1)[-1])
def adapter(request):
    return request.param


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    """A RAG checkout on disk plus a fake ``skewnono_rag.retrieve`` package in memory."""
    (tmp_path / "skewnono_rag").mkdir()
    (tmp_path / "index").mkdir()
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))
    monkeypatch.delenv("SKEWNONO_RAG_INDEX_DIR", raising=False)
    monkeypatch.setattr(sys, "path", list(sys.path))
    calls: dict = {}

    serve = types.ModuleType("skewnono_rag.retrieve.serve")

    def search_manuals(query, scope, *, limit, index_dir, timeout):
        calls["search"] = {
            "query": query,
            "scope": scope,
            "limit": limit,
            "index_dir": index_dir,
            "timeout": timeout,
        }
        return calls.get("hits", [])

    serve.search_manuals = search_manuals

    agent = types.ModuleType("skewnono_rag.retrieve.agent")

    def rewrite_query(question, *, timeout):
        calls["rewrite"] = question
        calls["rewrite_timeout"] = timeout
        return f"{question} (expanded)"

    def generate_follow_ups(question, answer, sources, *, timeout):
        calls["follow_ups"] = (question, answer, sources)
        calls["follow_ups_timeout"] = timeout
        return ["다음 질문 1", "Next question 2"]

    agent.rewrite_query = rewrite_query
    agent.generate_follow_ups = generate_follow_ups
    monkeypatch.setitem(sys.modules, "skewnono_rag.retrieve.serve", serve)
    monkeypatch.setitem(sys.modules, "skewnono_rag.retrieve.agent", agent)
    calls["root"] = tmp_path
    return calls


def test_config_requires_the_checkout(adapter, monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))  # no skewnono_rag/

    with pytest.raises(KnowledgeUnavailable):
        adapter._config()


def test_config_index_dir_defaults_under_the_checkout(adapter, checkout):
    assert adapter._config()["index_dir"] == str((checkout["root"] / "index").resolve())


def test_config_index_dir_env_override_must_exist(adapter, checkout, monkeypatch, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    monkeypatch.setenv("SKEWNONO_RAG_INDEX_DIR", str(elsewhere))
    with pytest.raises(KnowledgeUnavailable):
        adapter._config()

    elsewhere.mkdir()
    assert adapter._config()["index_dir"] == str(elsewhere.resolve())


def test_build_request_embeds_scope_candidates_and_index_dir(adapter, checkout):
    request = adapter._build_request("manual", "alarm reset", None, _SCOPE, 24)

    assert request["query"] == "alarm reset"
    assert request["scope"] == _SCOPE
    assert request["limit"] == 24
    assert request["index_dir"] == str((checkout["root"] / "index").resolve())


@pytest.mark.parametrize("source_type", ["meeting", "email", "report"])
def test_unindexed_sources_build_no_request_and_execute_to_empty(adapter, checkout, source_type):
    """Empty, never a fallback to manuals — those sources have no index yet."""
    assert adapter._build_request(source_type, "q", None, _SCOPE, 24) == {}
    assert adapter._execute(source_type, {}) == []
    assert "search" not in checkout


def test_execute_calls_the_rag_search_and_passes_rows_through(adapter, checkout):
    checkout["hits"] = [dict(_OFFICE_MANUAL_HIT)]
    request = adapter._build_request("manual", "alignment", None, _SCOPE, 24)

    rows = adapter._execute("manual", request)

    assert rows == [dict(_OFFICE_MANUAL_HIT)]  # no transform, element_type intact
    assert checkout["search"] == {
        "query": "alignment",
        "scope": _SCOPE,
        "limit": 24,
        "index_dir": request["index_dir"],
        "timeout": 20.0,
    }


def test_rerank_is_the_identity_over_the_rag_scores(adapter):
    hits = [_hit("a", 0.2), _hit("b", 0.9), dict(_hit("c", 0.0), score=None)]

    assert adapter._rerank("manual", "q", hits) == [0.2, 0.9, 0.0]


def test_end_to_end_manual_search_through_the_rag(adapter, checkout):
    checkout["hits"] = [dict(_OFFICE_MANUAL_HIT, score=0.1), dict(_OFFICE_MANUAL_HIT, source_id="x", score=0.7)]

    rows = adapter.search_manuals("alignment", None, _SCOPE, 5)

    assert [row["source_id"] for row in rows] == ["x", _OFFICE_MANUAL_HIT["source_id"]]
    assert "element_type" not in rows[0]


def test_rewrite_and_follow_ups_go_to_the_rag_agent_module(adapter, checkout):
    sources = [{"source_id": "s1", "title": "T"}]

    assert adapter.rewrite_query("얼라인 alarm") == "얼라인 alarm (expanded)"
    assert adapter.generate_follow_ups("q", "a", sources) == ["다음 질문 1", "Next question 2"]
    assert checkout["rewrite"] == "얼라인 alarm"
    assert checkout["follow_ups"] == ("q", "a", sources)


def test_every_rag_call_carries_the_knowledge_timeout(adapter, checkout, monkeypatch):
    """A hung RAG call must not outlive the turn: the per-call bound rides on all three."""
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_TIMEOUT", "7")

    adapter.search_manuals("alignment", None, _SCOPE, 5)
    adapter.rewrite_query("q")
    adapter.generate_follow_ups("q", "a", [])

    assert checkout["search"]["timeout"] == 7.0
    assert checkout["rewrite_timeout"] == 7.0
    assert checkout["follow_ups_timeout"] == 7.0


def test_the_knowledge_timeout_never_exceeds_the_agent_wall_clock(monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_AGENT_TIMEOUT", "30")
    monkeypatch.setenv("SKEWNONO_CHAT_KNOWLEDGE_TIMEOUT", "90")

    assert config.get_knowledge_timeout() == 30.0


def test_rewrite_and_follow_ups_without_a_checkout_are_unavailable(adapter, monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))

    with pytest.raises(KnowledgeUnavailable):
        adapter.rewrite_query("q")
    with pytest.raises(KnowledgeUnavailable):
        adapter.generate_follow_ups("q", "a", [])


def test_a_rewrite_that_is_not_a_nonempty_string_is_unavailable(adapter, checkout):
    """A blank rewrite would send an empty retrieval hint — worse than none."""
    sys.modules["skewnono_rag.retrieve.agent"].rewrite_query = lambda question, **_: "   "

    with pytest.raises(KnowledgeUnavailable):
        adapter.rewrite_query("q")


def test_follow_ups_are_normalized_to_clean_strings(adapter, checkout):
    sys.modules["skewnono_rag.retrieve.agent"].generate_follow_ups = (
        lambda q, a, s, **_: ["  one ", "", None, "one", "two"]
    )

    assert adapter.generate_follow_ups("q", "a", []) == ["one", "two"]


def test_rag_root_is_the_bridge_default(adapter):
    """The seams resolve the checkout through chat/rag.py, not their own path logic."""
    assert adapter.rag is rag
