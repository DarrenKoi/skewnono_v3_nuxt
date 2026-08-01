"""Tracked office knowledge-provider template that fails closed until implemented."""

from back_dev_home.chat.knowledge.contracts import KnowledgeUnavailable


def _not_connected(*args, **kwargs):
    raise KnowledgeUnavailable(
        "The chat knowledge office provider is not connected. "
        "Implement back_dev_home.chat.knowledge.providers.office before selecting office mode."
    )


search_manuals = _not_connected
search_meeting_summaries = _not_connected
search_emails = _not_connected
search_reports = _not_connected
