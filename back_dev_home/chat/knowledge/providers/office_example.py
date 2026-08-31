# TEMPLATE — copy to office.py at the office (`cp office_example.py office.py`).
# office.py is gitignored; this file (office_example.py) is the tracked
# implementation, COMPLETE as of 2026-08-28: the seams below call the office
# RAG in-process, so the copy needs no edits. Unlike presence-switched
# features, chat knowledge is selected by SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=
# office, so copying this file alone changes nothing until that variable is set.
"""Phase 2/3 adapter for the office chat RAG knowledge source.

The RAG is a separate 사내 repository checked out beside this package (see
``chat/rag.py`` for where and why) and called IN-PROCESS — there is no
service between Flask and the index. Its public surface, as handed over by
the RAG side (office 확인 2026-08-27, ``docs/datatables/chat/
chat_office_adapter_handoff.txt``):

* ``skewnono_rag.retrieve.serve.search_manuals(query, scope, limit=, index_dir=,
  timeout=)`` — single-shot hybrid retrieval + ``bge-reranker-v2-m3`` rerank,
  returning hits already in the normalized raw hit shape below;
* ``skewnono_rag.retrieve.agent.rewrite_query(question, timeout=)`` — one LLM
  call that expands acronyms and pairs Korean/English terms, run once BEFORE
  the agent loop;
* ``skewnono_rag.retrieve.agent.generate_follow_ups(question, answer, sources,
  timeout=)`` — 3–5 suggested next questions, run once AFTER the answer.

All three accept ``timeout=`` seconds and raise ``TimeoutError`` past it
(RAG 측 확인 2026-08-28); ``_config()`` supplies the value from
``SKEWNONO_CHAT_KNOWLEDGE_TIMEOUT``. The package was ``src`` until 2026-08-28.

The RAG side runs no agent loop of its own: the chat agent's tools call
``search_manuals`` repeatedly, and nesting a second loop inside ``_execute``
would multiply LLM calls. Rewrite and follow-ups are exposed here as two
extra provider functions (``rewrite_query`` / ``generate_follow_ups``) so the
orchestrator reaches them through ``knowledge/data.py`` like everything else.

The contract half of this adapter must not change: ``_search()`` clamps
limits, short-circuits empty queries, converts every backend failure into the
typed exceptions from ``contracts.py``, and ``_to_evidence()`` strictly
validates each raw hit into an ``Evidence`` row. The four seams are:

* ``_config()``       — load office settings (hosts, index aliases, timeouts)
  from environment/.env. Never accept them from user input or model arguments.
* ``_build_request(source_type, query, filters, scope, limit)`` — build the
  backend query. The ``AccessScope`` filter (user_id/groups/fabs) MUST be part
  of this request so filtering happens at query time; post-hoc Python
  filtering of results is a contract violation.
* ``_execute(source_type, request)`` — call the office backend and return raw
  hits as a list of mappings in the NORMALIZED RAW HIT shape below (rank
  order preserved). Map backend-specific errors in ``_translate_error()``.
* ``_rerank(source_type, query, hits)`` — score the candidates with the
  approved in-house reranker and return one score per hit in the same order.
  The sort, the score substitution and the five-row cap belong to the contract
  half; never reorder or truncate inside this seam.

Normalized raw hit — one mapping per result, keys:

| key             | type          | rule                                  |
| --------------- | ------------- | ------------------------------------- |
| ``source_id``   | str, required | stable across re-indexing; changes only with revision |
| ``title``       | str, required | approved-for-display title only       |
| ``snippet``     | str, required | approved minimal evidence, never full text |
| ``revision``    | str or None   | manual/report revision                |
| ``occurred_at`` | str or None   | normalized ISO-8601 source date       |
| ``section``     | str or None   | section provenance                    |
| ``page``        | int or None   | 1-based page number                   |
| ``region``      | str or None   | approved page region reference        |
| ``locator``     | str or None   | stable approved locator — never a URL or filesystem/MinIO path |
| ``figure_id``   | str or None   | opaque figure token — None for text/table evidence |
| ``score``       | float or None | ranking diagnostic                    |

Optional keys may be ABSENT rather than ``None`` — ``_to_evidence()`` reads
them with ``.get`` — and unknown keys are ignored. That matters for manuals:
the office RAG's ``skewnono_rag/retrieve/serve.py:search_manuals()`` returns exactly
``source_id, title, snippet, section, page, figure_id, score, element_type``
per hit (office 확인 2026-08-27). ``_execute()`` can pass those rows through
as they are: revision/occurred_at/region/locator map to ``None`` (manuals
carry no revision — user-confirmed 2026-08-06), and ``element_type`` is
dropped at the seam. It is an index-internal label (see
``docs/datatables/hitachi/chat_rag_contract.txt``), not an Evidence field;
``figure_id`` — null for text/table chunks, set for figure chunks — is the
signal that crosses. The filesystem ``image_path`` never crosses; only the
id does.

``figure_id`` identifies the figure a chunk was extracted from. It is the one
key whose value the application later turns into storage access, so it is an
OPAQUE TOKEN, not a key: emit the bare id, never a bucket, prefix, path
separator or ``.webp`` suffix. The serving side (``chat/figures.py``) owns the
whole key template — at the office
``{client prefix}/skewnono_rag/hitachi_manuals/figures/{figure_id}.webp``
(RAG 측 확인 2026-08-31) — and rejects any id outside ``^[A-Za-z0-9._-]{1,128}$`` (dots
admitted because real doc_ids carry them: ``CG6300_1.HHTSEM_SYSTEM_p100_i0``)
before it reaches storage, so an id carrying a path is a hit that will simply
never render. Text and table chunks emit ``None``.

``source_type`` is stamped by this adapter from the called function, never
read from the hit. Malformed hits raise ``KnowledgeUnavailable`` (index/schema
mismatch) naming the offending key but never the content. Empty results are
an empty list — no fallback to mock or another source, ever.

Verification: ``tests/test_knowledge_office_template.py`` exercises these
seams at home against a fake ``skewnono_rag.retrieve`` package, and runs the same
tests against the gitignored copy when it exists; the ladder is in
``back_dev_home/chat/MIGRATION.md``.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Mapping

from back_dev_home.chat import config, rag
from back_dev_home.chat.knowledge.contracts import (
    AccessScope,
    Evidence,
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)

# Application-side cap; callers already clamp to 5, this is defense in depth.
_RESULT_LIMIT = 5

_SOURCE_TYPES = ("manual", "meeting", "email", "report")

_OPTIONAL_STR_KEYS = (
    "revision",
    "occurred_at",
    "section",
    "region",
    "locator",
    "figure_id",
)


# ---------------------------------------------------------------------------
# Seams — the office-specific half. Everything below calls the co-located RAG.
# ---------------------------------------------------------------------------


def _config() -> Mapping[str, Any]:
    """Locate the RAG checkout and its index; unavailable when either is absent.

    ``index_dir`` is ``SKEWNONO_RAG_INDEX_DIR`` when set, else ``index/``
    INSIDE the delivered package — ``{root}/skewnono_rag/index`` (db, vectors,
    faiss, bm25; RAG 측 확인 2026-08-31). The RAG's own default is the
    RELATIVE ``"index"``, which would resolve against Flask's cwd
    (``/project/workSpace/`` on the cloud), so it is always passed absolute. ``timeout`` is the per-call bound every
    RAG function receives. Never log or return credentials (there are none:
    the RAG reads a local index).
    """
    root = rag.rag_root()
    if root is None:
        raise KnowledgeUnavailable(
            "The chat knowledge office provider has no RAG checkout; set "
            "SKEWNONO_CHAT_RAG_ROOT or clone it to back_dev_home/chat/_rag."
        )
    raw = os.environ.get("SKEWNONO_RAG_INDEX_DIR", "").strip()
    index_dir = Path(raw) if raw else root / "skewnono_rag" / "index"
    if not index_dir.is_dir():
        raise KnowledgeUnavailable(
            "The chat knowledge office provider has no RAG index directory; "
            "set SKEWNONO_RAG_INDEX_DIR to the built index."
        )
    return {
        "index_dir": str(index_dir.resolve()),
        "timeout": config.get_knowledge_timeout(),
    }


def _build_request(
    source_type: str,
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> Mapping[str, Any]:
    """Build the RAG search request for one source type.

    ``limit`` is the CANDIDATE count to retrieve, not the number of rows the
    caller receives. The contract half reranks those candidates and truncates
    to the application's five-row cap afterwards, so fetch all of them.

    Only ``manual`` is indexed; the other sources build no request and
    ``_execute`` returns an empty list for them — never a manual search in
    disguise. The ``scope`` rides in the request so the RAG can filter at
    query time; manuals are currently unrestricted, but the filter still has
    to be applied there rather than on the returned rows.

    Korean and English are served by ONE request: the RAG's dense leg is
    BGE-M3 (multilingual) and its lexical leg uses the Nori analyzer, so the
    query is passed through as typed — never translated or language-routed.
    """
    del filters  # no per-call filters are exposed to the model
    if source_type != "manual":
        return {}
    settings = _config()
    return {
        "query": query,
        "scope": dict(scope),
        "limit": limit,
        "index_dir": settings["index_dir"],
        "timeout": settings["timeout"],
    }


def _execute(source_type: str, request: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Run one search through the RAG; rows pass through untransformed.

    ``search_manuals`` already returns the normalized raw hit shape
    (``source_id, title, snippet, section, page, figure_id, score`` plus the
    index-internal ``element_type`` that ``_to_evidence`` drops), in rank
    order. RAG exceptions escape to ``_search()`` → ``_translate_error()``.
    """
    if source_type != "manual":
        return []
    serve = rag.import_rag("retrieve.serve")
    hits = serve.search_manuals(
        request["query"],
        request["scope"],
        limit=request["limit"],
        index_dir=request["index_dir"],
        timeout=request["timeout"],
    )
    return list(hits)


def _rerank(
    source_type: str,
    query: str,
    hits: list[Mapping[str, Any]],
) -> list[float]:
    """Identity: the RAG reranks with ``bge-reranker-v2-m3`` inside ``search_manuals``.

    Each hit's ``score`` IS the cross-encoder score, so returning it keeps the
    contract half's sort a no-op re-statement of the RAG's order. A missing
    score sorts last rather than failing — the RAG never omits it for manuals,
    and a hit without one is still evidence.
    """
    del source_type, query
    return [float(hit.get("score") or 0.0) for hit in hits]


def rewrite_query(question: str) -> str:
    """Expand the user's question once for retrieval (acronyms + KR/EN pairs).

    Runs BEFORE the agent loop; the result is handed to the model as the
    application-provided retrieval query. A blank rewrite is unavailable
    rather than silently accepted — an empty hint is worse than none.
    """
    agent = rag.import_rag("retrieve.agent")
    try:
        rewritten = agent.rewrite_query(question, timeout=_config()["timeout"])
    except Exception as error:  # noqa: BLE001 — typed for the caller
        raise _translate_error(error) from error
    if not isinstance(rewritten, str) or not rewritten.strip():
        raise KnowledgeUnavailable("The office RAG query rewrite returned no text.")
    return rewritten.strip()


def generate_follow_ups(
    question: str,
    answer: str,
    sources: list[Mapping[str, Any]],
) -> list[str]:
    """Suggest 3–5 next questions from the answered turn (deduplicated, trimmed)."""
    agent = rag.import_rag("retrieve.agent")
    try:
        raw = agent.generate_follow_ups(
            question, answer, sources, timeout=_config()["timeout"]
        )
    except Exception as error:  # noqa: BLE001 — typed for the caller
        raise _translate_error(error) from error
    follow_ups: list[str] = []
    for item in raw or ():
        if isinstance(item, str) and item.strip() and item.strip() not in follow_ups:
            follow_ups.append(item.strip())
    return follow_ups


def _translate_error(error: Exception) -> Exception:
    """Map RAG exceptions onto the typed contract exceptions.

    The RAG raises ``TimeoutError`` past ``timeout=`` and ``PermissionError``
    for authorization failures (RAG 측 확인 2026-08-28); everything else is a
    plain Python error.
    Anything unrecognized stays ``KnowledgeUnavailable`` (missing index, model
    load failure, 사내 dependency absent); raw errors are never re-raised and
    messages never carry query text.
    """
    if isinstance(error, TimeoutError):
        return KnowledgeTimeout("The chat knowledge search timed out.")
    if isinstance(error, PermissionError):
        return KnowledgeDenied("The chat knowledge search was denied.")
    return KnowledgeUnavailable("The chat knowledge search is unavailable.")


# ---------------------------------------------------------------------------
# Contract half — already written; the office copy must NOT edit below.
# ---------------------------------------------------------------------------


def _rank_hits(
    source_type: str,
    query: str,
    hits: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Order candidates by rerank score. Contract half — the office copy must not edit.

    The sort is stable, so equal scores keep the backend's original order. The
    rerank score replaces the retrieval score in the emitted row because that
    is the number that actually decided the ranking.
    """
    if not hits:
        return []

    scores = _rerank(source_type, query, hits)
    if not isinstance(scores, (list, tuple)) or len(scores) != len(hits):
        raise KnowledgeUnavailable(
            "Office knowledge rerank returned a score count that does not "
            "match the hit count."
        )

    scored: list[tuple[Mapping[str, Any], float]] = []
    for hit, score in zip(hits, scores, strict=True):
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise KnowledgeUnavailable(
                "Office knowledge rerank returned a non-numeric score."
            )
        value = float(score)
        if not math.isfinite(value):
            raise KnowledgeUnavailable(
                "Office knowledge rerank returned a non-finite score."
            )
        scored.append(({**hit, "score": value}, value))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [hit for hit, _ in scored]


def _search(
    source_type: str,
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    if source_type not in _SOURCE_TYPES:
        raise KnowledgeUnavailable(f"Unknown chat knowledge source type: {source_type}")
    bounded = min(max(int(limit), 1), _RESULT_LIMIT)
    trimmed = query.strip()
    if not trimmed:
        return []

    candidates = max(bounded, config.get_knowledge_candidate_pool())
    request = _build_request(source_type, trimmed, filters, scope, candidates)
    try:
        raw_hits = _execute(source_type, request)
        ranked = _rank_hits(source_type, trimmed, raw_hits)
    except (KnowledgeDenied, KnowledgeTimeout, KnowledgeUnavailable):
        raise
    except Exception as error:  # noqa: BLE001 — everything becomes a typed error
        raise _translate_error(error) from error

    return [_to_evidence(source_type, hit) for hit in ranked[:bounded]]


def _to_evidence(source_type: str, hit: Mapping[str, Any]) -> Evidence:
    """Validate one normalized raw hit into an Evidence row (strict)."""
    evidence: dict[str, Any] = {"source_type": source_type}

    for key in ("source_id", "title", "snippet"):
        value = hit.get(key)
        if not isinstance(value, str) or not value.strip():
            raise KnowledgeUnavailable(
                f"Office knowledge hit is missing required field '{key}'."
            )
        evidence[key] = value

    for key in _OPTIONAL_STR_KEYS:
        value = hit.get(key)
        if value is not None and not isinstance(value, str):
            raise KnowledgeUnavailable(
                f"Office knowledge hit field '{key}' must be a string or None."
            )
        evidence[key] = value

    page = hit.get("page")
    if page is not None:
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise KnowledgeUnavailable(
                "Office knowledge hit field 'page' must be a 1-based int or None."
            )
    evidence["page"] = page

    score = hit.get("score")
    if score is not None:
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise KnowledgeUnavailable(
                "Office knowledge hit field 'score' must be a number or None."
            )
        score = float(score)
    evidence["score"] = score

    return evidence  # type: ignore[return-value]


def search_manuals(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("manual", query, filters, scope, limit)


def search_meeting_summaries(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("meeting", query, filters, scope, limit)


def search_emails(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("email", query, filters, scope, limit)


def search_reports(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("report", query, filters, scope, limit)
