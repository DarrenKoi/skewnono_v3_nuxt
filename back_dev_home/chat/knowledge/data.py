"""Lazy provider selection for chat knowledge retrieval."""

from __future__ import annotations

from importlib import import_module
from typing import Mapping

from back_dev_home.chat.config import (
    KNOWLEDGE_SOURCES,
    get_knowledge_provider_name,
    get_knowledge_sources,
)
from back_dev_home.chat.knowledge.contracts import (
    AccessScope,
    Evidence,
    KnowledgeUnavailable,
)


_OFFICE_MODULE = "back_dev_home.chat.knowledge.providers.office"


def available_sources() -> tuple[str, ...]:
    """Sources the selected provider can actually answer for.

    Mock answers for all four so the home session exercises the whole tool
    assembly path. Office answers only for the sources whose index exists.
    This never imports the provider module — listing what is ready must not
    depend on the gitignored office copy being present.
    """
    if get_knowledge_provider_name() != "office":
        return KNOWLEDGE_SOURCES
    return get_knowledge_sources()


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


def rewrite_query(question: str) -> str:
    """Expand the question once for retrieval — run before the agent loop."""
    return _provider().rewrite_query(question)


def generate_follow_ups(
    question: str,
    answer: str,
    sources: list[Mapping[str, object]],
) -> list[str]:
    """Suggest next questions from the answered turn — run after the answer."""
    return _provider().generate_follow_ups(question, answer, sources)
