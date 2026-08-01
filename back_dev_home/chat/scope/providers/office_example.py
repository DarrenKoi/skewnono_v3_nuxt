"""Tracked office scope-provider template that fails closed until implemented."""

from back_dev_home.chat.scope.contracts import ScopeUnavailable


def classify(query: str):
    raise ScopeUnavailable(
        "The chat scope office provider is not connected. "
        "Implement back_dev_home/chat/scope/providers/office before selecting office mode."
    )
