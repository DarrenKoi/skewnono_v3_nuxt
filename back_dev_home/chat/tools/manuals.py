"""Read-only manual retrieval tool."""

from __future__ import annotations

from back_dev_home.chat.tools._shared import build_search_tool

build_search_manuals_tool = build_search_tool(
    "search_manuals",
    "Search approved equipment manuals for evidence relevant to the query.",
    "No manual evidence found.",
)
