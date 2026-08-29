"""Read-only email retrieval tool."""

from __future__ import annotations

from back_dev_home.chat.tools._shared import build_search_tool

build_search_emails_tool = build_search_tool(
    "search_emails",
    "Search approved emails for evidence relevant to the query.",
    "No email evidence found.",
)
