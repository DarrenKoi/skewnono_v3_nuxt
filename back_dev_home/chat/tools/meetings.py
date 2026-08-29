"""Read-only meeting-summary retrieval tool."""

from __future__ import annotations

from back_dev_home.chat.tools._shared import build_search_tool

build_search_meeting_summaries_tool = build_search_tool(
    "search_meeting_summaries",
    "Search approved meeting summaries for evidence relevant to the query.",
    "No meeting evidence found.",
)
