# TEMPLATE — copy to office.py at the office, then implement the OFFICE-TODO
# seams. office.py is gitignored; this file (office_example.py) is the tracked
# skeleton. Unlike presence-switched features, chat knowledge is selected by
# SKEWNONO_CHAT_KNOWLEDGE_PROVIDER=office, so copying this file alone changes
# nothing until that variable is set.
"""Phase 2/3 adapter skeleton for the office chat RAG knowledge source.

The contract half of this adapter is already written and must not change:
``_search()`` clamps limits, short-circuits empty queries, converts every
backend failure into the typed exceptions from ``contracts.py``, and
``_to_evidence()`` strictly validates each raw hit into an ``Evidence`` row.
The office implementation fills exactly four seams:

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
the office RAG's ``src/retrieve/serve.py:search_manuals()`` returns exactly
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
``{client prefix}/hitachi_sem/manual_figures/{figure_id}.webp`` (office 확인
2026-08-27) — and rejects any id outside ``^[A-Za-z0-9._-]{1,128}$`` (dots
admitted because real doc_ids carry them: ``CG6300_1.HHTSEM_SYSTEM_p100_i0``)
before it reaches storage, so an id carrying a path is a hit that will simply
never render. Text and table chunks emit ``None``.

``source_type`` is stamped by this adapter from the called function, never
read from the hit. Malformed hits raise ``KnowledgeUnavailable`` (index/schema
mismatch) naming the offending key but never the content. Empty results are
an empty list — no fallback to mock or another source, ever.

Verification: fill the OFFICE-TODO fixtures in
``back_dev_home/chat/tests/test_knowledge_office.py`` (tracked; skips at home)
and follow the ladder in ``back_dev_home/chat/MIGRATION.md``.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from back_dev_home.chat import config
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
# OFFICE-TODO seams — the only code the office implementation writes.
# ---------------------------------------------------------------------------


def _config() -> Mapping[str, Any]:
    """Load office-side settings (hosts, index aliases, timeouts).

    OFFICE-TODO: read from environment/.env only (the self-load pattern in
    ``back_dev_home/_runtime/office_redis.load_env_file`` is available).
    Raise ``KnowledgeUnavailable`` when required settings are missing.
    Never log or return credentials.
    """
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected: _config() is "
        "not implemented."
    )


def _build_request(
    source_type: str,
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> Mapping[str, Any]:
    """Build the backend search request for one source type.

    ``limit`` is the CANDIDATE count to retrieve, not the number of rows the
    caller receives. The contract half reranks those candidates and truncates
    to the application's five-row cap afterwards, so fetch all of them.

    OFFICE-TODO: embed the ``scope`` access filter (user_id/groups/fabs) in
    the request itself so unauthorized sources are excluded at query time and
    their existence, title, count, and score are never observable. Restrict
    the field projection to the normalized raw hit keys — ``figure_id``
    included, or every hit arrives figure-less.

    One request must serve Korean and English TOGETHER. Users mix them in a
    single question ("얼라인 alarm 리셋"), and the corpus mixes them too, so a
    request that only satisfies one language silently halves recall instead of
    failing visibly. The k-NN leg handles this if the embedding model is
    multilingual — confirm that it is rather than assuming. Any lexical/BM25
    leg needs an explicit Korean analyzer: OpenSearch's default ``standard``
    analyzer splits Hangul into single characters, which matches nothing
    useful. Do not translate or language-detect the query and dispatch one
    branch; that turns a mixed-language question into a worse monolingual one.
    """
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected: "
        "_build_request() is not implemented."
    )


def _execute(source_type: str, request: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Run one search against the office backend.

    OFFICE-TODO: call the office index/service and return raw hits in the
    normalized raw hit shape, preserving backend rank order. Let
    backend-specific exceptions escape; ``_search()`` routes them through
    ``_translate_error()``.
    """
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected: _execute() is "
        "not implemented."
    )


def _rerank(
    source_type: str,
    query: str,
    hits: list[Mapping[str, Any]],
) -> list[float]:
    """Score each candidate hit against the query.

    OFFICE-TODO: call the approved in-house reranker and return ONE score per
    hit, in the SAME ORDER as ``hits``. Higher is better. The contract half
    below owns the sort and the row cap, so never reorder or truncate here.

    When reranking happens inside the search backend itself (the C1 path in
    the design spec), return each hit's existing ``score`` — that keeps this
    seam an identity ordering without special-casing the contract half.

    Do not silently skip the rerank when the service is down: raise, and let
    ``_search()`` route it through ``_translate_error()``. Returning the raw
    retrieval order would look like a working answer of measurably worse
    quality, which is the failure mode this contract exists to prevent.
    """
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected: _rerank() is "
        "not implemented."
    )


def _translate_error(error: Exception) -> Exception:
    """Map backend-specific exceptions onto the typed contract exceptions.

    OFFICE-TODO: extend the mapping for the office client library —
    authorization failures to ``KnowledgeDenied``, deadline/timeout errors to
    ``KnowledgeTimeout``. Anything unrecognized stays ``KnowledgeUnavailable``
    (configuration/index mismatch/service down); never re-raise raw client
    errors and never include query text or credentials in messages.
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
