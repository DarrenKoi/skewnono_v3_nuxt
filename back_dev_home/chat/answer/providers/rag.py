"""The whole turn via the co-located RAG — chat's only office answer path.

Tracked, not copied: selection is ``rag.rag_ready()``, so this file is live
wherever the checkout is and inert everywhere else. One seam:
``skewnono_rag.retrieve.agent.agent_query``, the entry point agreed 2026-08-31
(``chat/docs/2026-08-31-chat-to-rag-answer-contract-agreed.md``). The RAG
owns rewrite, search iteration, rerank and answer generation; this adapter
owns only the call, the outer deadline guard and error translation — never a
second agent loop.

What the answer must look like is NOT decided here. ``answer/contract.py``
holds the field rules, the citation cap and the exception mapping, and both
sides execute it: this adapter calls ``validate_answer`` on every turn, and
the RAG side runs the same module in the office runtime to check itself
before chat ever sees the result. Adding a coercion here instead of there is
how the two environments drift apart again.

``timeout`` is the WHOLE-TURN budget (``SKEWNONO_CHAT_ANSWER_TIMEOUT``). The
RAG enforces it as per-call ``timeout=remaining`` plus a pre-invoke deadline
check — NOT a true cumulative deadline (RAG 측 확인 2026-08-31) — so the
thread guard here is the real ceiling: an overshooting internal call can
never pin a Flask worker past budget + grace.
"""

from __future__ import annotations

import queue
import threading
from typing import Any

from back_dev_home.chat import config, rag
from back_dev_home.chat.answer import contract
from back_dev_home.chat.answer.contract import AnswerResult
from back_dev_home.chat.contracts import (
    AccessScope,
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)

_GRACE_SECONDS = 5.0


def answer_question(
    question: str,
    messages: list[dict],
    scope: AccessScope,
) -> AnswerResult:
    module = rag.import_rag("retrieve.agent")
    timeout = config.get_answer_timeout()
    try:
        raw = _call_with_deadline(
            module.agent_query,
            timeout + _GRACE_SECONDS,
            question,
            messages=list(messages),
            scope=dict(scope),
            timeout=timeout,
        )
    # The three-way translation declared in contract.EXCEPTION_MAP, which
    # test_answer_rag.py pins against this function so the table and the code
    # cannot drift. Written out rather than dispatched through the map: two
    # clauses read better than a loop, and the test is what keeps them honest.
    except TimeoutError as error:
        raise KnowledgeTimeout("The RAG answer timed out.") from error
    except PermissionError as error:
        raise KnowledgeDenied("The RAG answer was denied.") from error
    except (KnowledgeTimeout, KnowledgeDenied, KnowledgeUnavailable):
        raise
    except Exception as error:
        # Carry the cause into the message: at the office the 503 body is
        # often the only visible diagnostic, and a TypeError naming a keyword
        # argument identifies a signature mismatch that a bare sentence hides.
        raise KnowledgeUnavailable(
            f"The RAG answer failed: {type(error).__name__}: {error}"
        ) from error
    return contract.validate_answer(raw, question=question)


def _call_with_deadline(func, deadline_seconds: float, /, *args, **kwargs):
    """Run the RAG call behind a wall-clock backstop on a daemon worker.

    A worker finishing after the deadline produces only an orphaned in-memory
    result: persistence stays with the caller, so a late answer can never
    append an assistant turn to a request that already returned 504.
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
