"""Deterministic lexical search over deliberately synthetic knowledge fixtures.

Stands in for the office RAG index (OpenSearch, manuals/meeting summaries/
emails/reports; figures in MinIO). The office path is a 2-leg hybrid search —
Nori BM25 ⊕ BGE-M3 dense k-NN — over-fetching 20-30 candidates and reranking
them with the ``bge-reranker-v2-m3`` cross-encoder before truncating to five
rows (see ``docs/superpowers/specs/2026-08-07-chat-rag-manuals-design.md``).
This mock has none of that: retrieval here is whole-token set overlap against
the fixture files, so there is no embedding similarity and no cross-encoder
rerank — only literal shared tokens. Consequently ``score`` here is a small
integer (token overlap count), not the office's rerank score (a float from
``bge-reranker-v2-m3``).

Fixture content is synthetic and mixes Korean and English on purpose. Users
ask in either language or both at once, so an English-only mock would report
zero results for a Korean question that the office index answers fine, and
every home session would be tuning against a retrieval path that cannot do
what the real one does. ``figure_id`` is populated only on the manual records
that would plausibly carry an extracted figure; text and table evidence
carries ``None``.

The fixture figure ids reproduce the office's confirmed shape,
``{doc_id}_p{page}_i{idx}`` — e.g. ``CG6300_1.HHTSEM_SYSTEM_p100_i0`` (office
확인 2026-08-19) — with a synthetic ``SYN…`` doc_id and the ``_p{page}`` half
kept consistent with each record's ``page``. The **dot** in the doc_id is the
property worth copying rather than a cosmetic detail: the earlier dot-free ids
taught that the serving charset could exclude ``.``, and an id the route
rejects renders no figure at all rather than erroring, so the mock would have
passed while every office figure 404'd. Nothing is stored behind these ids —
only the shape is real.

This mock answers all four sources unconditionally, even though the office
provider currently exposes only ``manual`` (``get_knowledge_sources()``
defaults to ``SKEWNONO_CHAT_KNOWLEDGE_SOURCES=manual``). That is deliberate:
home sessions need to exercise the whole tool-assembly path
(``available_sources()`` -> ``_build_tools()``), not just the one source the
office side has connected so far.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from back_dev_home.chat.knowledge.contracts import AccessScope, Evidence


_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "__fixtures__" / "knowledge"
# Hangul is in the class deliberately: without it every Korean query tokenizes
# to the empty set and short-circuits to "no results" — a silent wrong answer,
# not an error. Syllable-level, so it matches whole words only (no stemming,
# no 조사 stripping); that is weaker than the office analyzer, never stricter.
_TOKEN_PATTERN = re.compile(r"[a-z0-9가-힣]+")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(value.lower()))


def _has_access(record: Mapping[str, Any], scope: AccessScope) -> bool:
    access = record["access"]
    if not any(access.values()):
        return True
    return (
        scope["user_id"] in access["users"]
        or bool(set(scope["groups"]) & set(access["groups"]))
        or bool(set(scope["fabs"]) & set(access["fabs"]))
    )


def _load(source: str) -> list[dict[str, Any]]:
    with (_FIXTURE_ROOT / f"{source}.json").open(encoding="utf-8") as fixture:
        return json.load(fixture)


def _search(
    source: str,
    query: str,
    _filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    rows: list[Evidence] = []
    for record in _load(source):
        if not _has_access(record, scope):
            continue
        score = float(len(query_tokens & _tokens(record["search_text"])))
        if score == 0:
            continue
        evidence: Evidence = {
            key: value
            for key, value in record.items()
            if key not in {"access", "search_text"}
        }
        evidence["score"] = score
        rows.append(evidence)

    rows.sort(key=lambda row: (-float(row["score"] or 0), row["source_id"]))
    return rows[:limit]


def search_manuals(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("manuals", query, filters, scope, limit)


def search_meeting_summaries(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("meetings", query, filters, scope, limit)


def search_emails(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("emails", query, filters, scope, limit)


def search_reports(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _search("reports", query, filters, scope, limit)
