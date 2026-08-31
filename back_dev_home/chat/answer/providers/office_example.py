"""Office answer adapter TEMPLATE — the whole turn via the co-located RAG.

``cp office_example.py office.py`` at the office; the copy is the adapter
(presence detection). One seam: ``skewnono_rag.retrieve.agent.agent_query``,
the entry point agreed 2026-08-31
(``chat/docs/2026-08-31-chat-to-rag-answer-contract-agreed.md``). The RAG
owns rewrite, search iteration, rerank and answer generation; this adapter
owns only the call, the outer deadline guard, error translation and shape
normalization — never a second agent loop.

``timeout`` is the WHOLE-TURN budget (``SKEWNONO_CHAT_AGENT_TIMEOUT``); the
RAG distributes it internally and raises ``TimeoutError`` past it. The
thread guard here is the promised backstop with a small grace, so an
imperfect internal distribution can never pin a Flask worker forever.

Sources come back Evidence-shaped from the RAG (``source_type`` already
stamped ``manual`` there); chat validates shape only — required text fields
present, optional fields defaulted, five-row application cap.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Mapping

from back_dev_home.chat import config, rag
from back_dev_home.chat.answer.contracts import AnswerResult
from back_dev_home.chat.knowledge.contracts import (
    AccessScope,
    Evidence,
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)

_RESULT_LIMIT = 5  # application-owned cap, same as the knowledge seam
_GRACE_SECONDS = 5.0
_REQUIRED_KEYS = ("source_id", "title", "snippet")
_OPTIONAL_KEYS = (
    "revision",
    "occurred_at",
    "section",
    "page",
    "region",
    "locator",
    "figure_id",
    "score",
)


def answer_question(
    question: str,
    messages: list[dict],
    scope: AccessScope,
) -> AnswerResult:
    module = rag.import_rag("retrieve.agent")
    timeout = config.get_agent_timeout()
    try:
        raw = _call_with_deadline(
            module.agent_query,
            timeout + _GRACE_SECONDS,
            question,
            messages=list(messages),
            scope=dict(scope),
            timeout=timeout,
        )
    except TimeoutError as error:
        raise KnowledgeTimeout("The RAG answer timed out.") from error
    except PermissionError as error:
        raise KnowledgeDenied("The RAG answer was denied.") from error
    except (KnowledgeTimeout, KnowledgeDenied, KnowledgeUnavailable):
        raise
    except Exception as error:
        raise KnowledgeUnavailable("The RAG answer failed.") from error
    return _normalize(question, raw)


def _call_with_deadline(func, deadline_seconds: float, /, *args, **kwargs):
    """Run the RAG call behind a wall-clock backstop on a daemon worker.

    Same shape as the agent runtime's graph deadline: a worker finishing
    after timeout produces only an orphaned in-memory result — persistence
    stays with the caller.
    """
    outcome: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            outcome.put((True, func(*args, **kwargs)))
        except Exception as error:  # noqa: BLE001 — carried to the caller
            outcome.put((False, error))

    threading.Thread(target=run, name="chat-rag-answer", daemon=True).start()
    try:
        succeeded, value = outcome.get(timeout=deadline_seconds)
    except queue.Empty as error:
        raise TimeoutError("The RAG answer exceeded the outer deadline.") from error
    if not succeeded:
        raise value
    return value


def _normalize(question: str, raw: Mapping[str, Any]) -> AnswerResult:
    content = str(raw.get("content") or "").strip()
    if not content:
        raise KnowledgeUnavailable("The RAG answer came back empty.")
    rewrite = raw.get("rewrite") or None
    if rewrite == question:
        rewrite = None
    return {
        "content": content,
        "sources": [
            _to_evidence(hit) for hit in list(raw.get("sources") or [])[:_RESULT_LIMIT]
        ],
        "follow_ups": [str(item) for item in raw.get("follow_ups") or []],
        "rewrite": rewrite,
        "tool_traces": list(raw.get("tool_traces") or []),
        "prompt_tokens": raw.get("prompt_tokens"),
        "completion_tokens": raw.get("completion_tokens"),
    }


def _to_evidence(hit: Mapping[str, Any]) -> Evidence:
    for key in _REQUIRED_KEYS:
        if not hit.get(key):
            raise KnowledgeUnavailable(f"A RAG source is missing {key!r}.")
    evidence: dict[str, Any] = {key: hit[key] for key in _REQUIRED_KEYS}
    evidence["source_type"] = hit.get("source_type", "manual")
    for key in _OPTIONAL_KEYS:
        evidence[key] = hit.get(key)
    return evidence  # type: ignore[return-value]
