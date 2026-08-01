"""Lazy provider selection for chat knowledge retrieval."""

from __future__ import annotations

from importlib import import_module
from typing import Mapping

from back_dev_home.chat.config import get_knowledge_provider_name
from back_dev_home.chat.knowledge.contracts import (
    AccessScope,
    Evidence,
    KnowledgeUnavailable,
)


_OFFICE_MODULE = "back_dev_home.chat.knowledge.providers.office"


def _provider():
    if get_knowledge_provider_name() != "office":
        return import_module("back_dev_home.chat.knowledge.providers.mock")

    try:
        return import_module(_OFFICE_MODULE)
    except ModuleNotFoundError as error:
        if error.name == _OFFICE_MODULE:
            raise KnowledgeUnavailable(
                "The chat knowledge office provider is unavailable; "
                "add back_dev_home/chat/knowledge/providers/office.py."
            ) from error
        raise


def _limit(value: int) -> int:
    return min(max(value, 1), 5)


def search_manuals(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _provider().search_manuals(query, filters, scope, _limit(limit))


def search_meeting_summaries(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _provider().search_meeting_summaries(query, filters, scope, _limit(limit))


def search_emails(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _provider().search_emails(query, filters, scope, _limit(limit))


def search_reports(
    query: str,
    filters: Mapping[str, object] | None,
    scope: AccessScope,
    limit: int,
) -> list[Evidence]:
    return _provider().search_reports(query, filters, scope, _limit(limit))
