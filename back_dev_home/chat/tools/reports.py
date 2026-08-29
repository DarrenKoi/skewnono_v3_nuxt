"""Read-only report retrieval tool."""

from __future__ import annotations

from back_dev_home.chat.tools._shared import build_search_tool

build_search_reports_tool = build_search_tool(
    "search_reports",
    "Search approved reports for evidence relevant to the query.",
    "No report evidence found.",
)
