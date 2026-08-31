"""RAG-answer runtime — the whole turn from the answer seam, bundled.

``SKEWNONO_CHAT_RUNTIME=rag``: the RAG's ``agent_query`` (or its home mock)
answers the turn, so rewrite and follow-ups arrive INSIDE the result — the
orchestrator keeps them instead of running its own knowledge calls. The
request's last message is the current user turn (mixed substitution already
applied by the orchestrator); it travels as ``question`` and is dropped from
the history per the agreed contract. ``system_prompt`` and ``model`` are
chat-LLM concerns the RAG does not take — the RAG owns its prompts and its
own LLM, so ``model`` reports None.

Errors propagate as the knowledge family; routes translate both families to
the same statuses (403/503/504).
"""

from __future__ import annotations

import time

from back_dev_home.chat.answer import data as answer_data
from back_dev_home.chat.runtime.contracts import RuntimeRequest, RuntimeResult


def invoke(request: RuntimeRequest) -> RuntimeResult:
    messages = list(request["messages"])
    question = messages.pop()["content"] if messages else ""
    started = time.perf_counter()
    answer = answer_data.answer_question(
        question, messages, request["access_scope"]
    )
    return {
        "content": answer["content"],
        "runtime": "rag",
        "model": None,
        "prompt_tokens": answer["prompt_tokens"],
        "completion_tokens": answer["completion_tokens"],
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "sources": answer["sources"],
        "tool_traces": answer["tool_traces"],
        "rewrite": answer["rewrite"],
        "follow_ups": answer["follow_ups"],
    }
