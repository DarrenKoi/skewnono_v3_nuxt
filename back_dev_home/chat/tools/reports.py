"""Read-only report retrieval tool."""

from __future__ import annotations

import time

from langchain.tools import tool

from back_dev_home.chat.knowledge import data as knowledge_data
from back_dev_home.chat.knowledge.contracts import AccessScope
from back_dev_home.chat.tools.evidence import EvidenceBudget


def build_search_reports_tool(
    access_scope: AccessScope,
    evidence_budget: EvidenceBudget | None = None,
):
    """Build a report search tool closed over the caller's server-owned scope."""
    budget = evidence_budget or EvidenceBudget.from_config()

    @tool("search_reports", response_format="content_and_artifact")
    def search_reports(query: str) -> tuple[str, dict]:
        """Search approved reports for evidence relevant to the query."""
        started = time.perf_counter()
        rows = knowledge_data.search_reports(query, {}, access_scope, 5)
        trace = {
            "tool_name": "search_reports",
            "query": query,
            "result_count": len(rows),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "status": "success" if rows else "empty",
        }
        content, bounded = budget.prepare(rows, "No report evidence found.")
        trace["result_count"] = len(bounded)
        return content, {"sources": bounded, "trace": trace}

    return search_reports
