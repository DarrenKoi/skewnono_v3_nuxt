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
check — NOT a true cumulative deadline (RAG 측 확인 2026-08-31).

There used to be an outer thread guard here, running the call on a daemon
worker with a five-second grace so an overshooting RAG could not pin a Flask
worker. It went away on 2026-09-01 with the turn-as-resource change: this
function now runs ON the background worker, so the request it once protected
is already finished. The guard could never kill the inner call anyway — it
abandoned it — so keeping it meant two abandoned threads for the same absent
guarantee. An overrun is now visible where it belongs: the turn stays
``pending`` and the store presents it as failed once it outlives the budget.
"""

from __future__ import annotations

from back_dev_home.chat import config, rag
from back_dev_home.chat.answer import contract
from back_dev_home.chat.answer.contract import AnswerResult
from back_dev_home.chat.contracts import (
    AccessScope,
    KnowledgeDenied,
    KnowledgeTimeout,
    KnowledgeUnavailable,
)

def answer_question(
    question: str,
    messages: list[dict],
    scope: AccessScope,
) -> AnswerResult:
    module = rag.import_rag("retrieve.agent")
    timeout = config.get_answer_timeout()
    try:
        raw = module.agent_query(
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
