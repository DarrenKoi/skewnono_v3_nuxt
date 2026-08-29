"""Factory for the read-only knowledge-source search tools.

``emails.py``/``manuals.py``/``meetings.py``/``reports.py`` were byte-identical
except for the tool name, the knowledge-source function it calls, and the
"no results" message — this builds all four from one place.
"""

from __future__ import annotations

import time

from langchain.tools import tool

from back_dev_home.chat.knowledge import data as knowledge_data
from back_dev_home.chat.knowledge.contracts import AccessScope
from back_dev_home.chat.tools.evidence import EvidenceBudget


def build_search_tool(name: str, description: str, empty_message: str):
    """Build a ``build_search_<x>_tool(access_scope, evidence_budget=None)``.

    ``name`` doubles as the ``knowledge_data`` function to call (every source
    tool is named after it: ``search_emails``, ``search_manuals``, ...). The
    lookup happens at call time via ``getattr`` — not a captured reference —
    so a test's ``monkeypatch.setattr(knowledge_data, name, ...)`` is honored.
    """

    def build(access_scope: AccessScope, evidence_budget: EvidenceBudget | None = None):
        budget = evidence_budget or EvidenceBudget.from_config()

        @tool(name, description=description, response_format="content_and_artifact")
        def search(query: str) -> tuple[str, dict]:
            started = time.perf_counter()
            rows = getattr(knowledge_data, name)(query, {}, access_scope, 5)
            trace = {
                "tool_name": name,
                "query": query,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "status": "success" if rows else "empty",
            }
            content, bounded = budget.prepare(rows, empty_message)
            trace["result_count"] = len(bounded)
            return content, {"sources": bounded, "trace": trace}

        return search

    return build
