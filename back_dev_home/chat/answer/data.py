"""Lazy provider selection for the answer seam.

The dispatcher owns what the application owns regardless of provider: the
history cap (``get_answer_history_limit``, agreed-contract assumption 20
until the RAG side sends its ``max_history``). ``messages`` is prior turns
only — the current question travels in ``question``, never duplicated into
the history (agreed contract).
"""

from __future__ import annotations

from importlib import import_module

from back_dev_home.chat.answer.contracts import AnswerResult
from back_dev_home.chat.config import (
    get_answer_history_limit,
    get_answer_provider_name,
)
from back_dev_home.chat.knowledge.contracts import AccessScope, KnowledgeUnavailable


_OFFICE_MODULE = "back_dev_home.chat.answer.providers.office"


def _provider():
    if get_answer_provider_name() != "office":
        return import_module("back_dev_home.chat.answer.providers.mock")

    try:
        return import_module(_OFFICE_MODULE)
    except ModuleNotFoundError as error:
        if error.name == _OFFICE_MODULE:
            raise KnowledgeUnavailable(
                "The chat answer office provider is unavailable; "
                "add back_dev_home/chat/answer/providers/office.py."
            ) from error
        raise


def answer_question(
    question: str,
    messages: list[dict],
    scope: AccessScope,
) -> AnswerResult:
    history = list(messages)[-get_answer_history_limit():]
    return _provider().answer_question(question, history, scope)
