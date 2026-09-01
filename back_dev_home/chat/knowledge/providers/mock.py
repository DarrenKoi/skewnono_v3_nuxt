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

The manual fixture rows carry ``None`` for ``revision``, ``occurred_at``,
``region`` and ``locator`` because the office manual search returns none of
them: ``search_manuals()`` at the office emits exactly ``source_id, title,
snippet, section, page, figure_id, score`` plus an index-internal
``element_type`` that the adapter drops (office 확인 2026-08-27). A mock that
filled them would have the SPA rendering "title · R2 · p.12" labels the
office can never produce. OFFICE-VERIFY: whether the office adapter derives a
``locator`` from ``source_id``/``page`` — until confirmed, the mock matches
the raw hit and emits ``None``. Meeting/email/report fixtures keep their
dates and locators; those sources are not connected yet and their office
shape is unknown.

The fixture figure ids reproduce the office's confirmed shape,
``{stem}_p{page}_i{idx}`` — e.g. ``CG6300_1.HHTSEM_SYSTEM_p100_i0`` (office
확인 2026-08-19) — with a synthetic stem and the ``_p{page}`` half kept
consistent with each record's ``page``. The stem is the manual's **filename**,
so its charset is the property worth copying rather than a cosmetic detail:
one fixture carries a dot, and one carries spaces and Hangul, because both are
ordinary in a filename and both were once rejected by the serving charset. An
id the route rejects renders no figure at all rather than erroring, so a mock
whose ids are tidier than the office's passes at home while every office
figure 404s. Nothing is stored behind these ids — only the shape is real.

``rewrite_query`` / ``generate_follow_ups`` stand in for the office RAG's two
LLM calls (``skewnono_rag.retrieve.agent``, office 확인 2026-08-27): the rewrite there
expands acronyms and pairs Korean/English terms; the follow-ups are 3–5 next
questions generated from the answer and its sources. Here both are table
lookups — a fixed acronym/translation table and title-derived questions — so
the orchestration path and the SPA are exercised deterministically with no
model in the loop. The office output is free text; only the shape (a
nonempty string; 3–5 distinct strings) is copied.

This is now a corpus, not a seam: the office side does its own retrieval
inside the RAG, so nothing here is ever selected against it. Its one caller is
``answer/providers/mock.py``, the home stand-in for ``agent_query`` — which is
why the fixtures still cover all four source types even though the office
index has only connected ``manual`` so far. The extra rows cost nothing and
keep the SPA's source rendering exercised for the types that come next.
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


# Acronym expansions and KR/EN pairs the office rewrite would produce; token
# → expansion, matched on the same tokenizer as retrieval so a hit here is a
# hit there.
_REWRITE_TABLE = {
    "cd-sem": "critical dimension SEM, 측장 SEM",
    "cd": "critical dimension, 측장",
    "sem": "scanning electron microscope, 전자현미경",
    "alarm": "알람",
    "알람": "alarm",
    "리셋": "reset",
    "reset": "리셋",
    "얼라인": "align, alignment",
    "align": "얼라인, 정렬",
    "recipe": "레시피",
    "레시피": "recipe",
    "manual": "매뉴얼",
    "매뉴얼": "manual",
    "calibration": "교정, 캘리브레이션",
    "교정": "calibration",
    "wafer": "웨이퍼",
    "웨이퍼": "wafer",
}
_REWRITE_PATTERN = re.compile(r"[a-z0-9가-힣-]+")


def rewrite_query(question: str) -> str:
    """Append table expansions in first-seen order; unchanged when none apply."""
    seen: list[str] = []
    for token in _REWRITE_PATTERN.findall(question.lower()):
        expansion = _REWRITE_TABLE.get(token)
        if expansion and expansion not in seen:
            seen.append(expansion)
    if not seen:
        return question
    return f"{question} ({'; '.join(seen)})"


_GENERIC_FOLLOW_UPS = (
    "이 절차에서 주의해야 할 점은 무엇인가요?",
    "관련 알람 코드와 대처 방법을 알려줘",
    "Which other equipment does this apply to?",
)


def generate_follow_ups(
    question: str,
    answer: str,
    sources: list[Mapping[str, Any]],
) -> list[str]:
    """Three questions: one per distinct cited title, padded with generic ones."""
    del question, answer  # the office LLM reads them; the table does not
    follow_ups: list[str] = []
    for source in sources:
        title = str(source.get("title") or "").strip()
        candidate = f"{title}에서 관련 절차를 더 알려줘"
        if title and candidate not in follow_ups:
            follow_ups.append(candidate)
        if len(follow_ups) == 3:
            break
    for generic in _GENERIC_FOLLOW_UPS:
        if len(follow_ups) == 3:
            break
        follow_ups.append(generic)
    return follow_ups
