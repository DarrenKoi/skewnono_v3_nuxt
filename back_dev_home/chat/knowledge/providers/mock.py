"""Deterministic lexical search over deliberately synthetic knowledge fixtures."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from back_dev_home.chat.knowledge.contracts import AccessScope, Evidence


_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "__fixtures__" / "knowledge"
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


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
