"""Lazy provider selection for chat scope classification."""

from __future__ import annotations

from importlib import import_module

from back_dev_home.chat.config import get_scope_provider_name
from back_dev_home.chat.scope.contracts import ScopeDecision, ScopeUnavailable


_OFFICE_MODULE = "back_dev_home.chat.scope.providers.office"


def _provider():
    if get_scope_provider_name() != "office":
        return import_module("back_dev_home.chat.scope.providers.mock")

    try:
        return import_module(_OFFICE_MODULE)
    except ModuleNotFoundError as error:
        if error.name == _OFFICE_MODULE:
            raise ScopeUnavailable(
                "The chat scope office provider is unavailable; "
                "add back_dev_home/chat/scope/providers/office.py."
            ) from error
        raise


def classify(query: str) -> ScopeDecision:
    """Classify a chat query through the configured scope provider."""
    return _provider().classify(query)
