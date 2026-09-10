"""Provider selection for the answer seam — the RAG when it is here, else mock.

There is no environment variable and no adapter to copy: ``rag.rag_ready()``
asks whether the delivered ``skewnono_rag`` package and its built index are on
this machine, and that is the whole decision. At home the checkout is absent,
so every developer gets the mock; at the office it is present, so the same code
answers from the real index. Read per call, not cached, so a checkout that
lands while the server runs takes effect on the next turn.

The dispatcher also owns what the application owns regardless of provider: the
history cap (``get_answer_history_limit``, default 5 = the RAG's own
MAX_HISTORY). ``messages`` is prior turns only — the current question travels
in ``question``, never duplicated into the history (agreed contract).
"""

from __future__ import annotations

from backend.chat import rag
from backend.chat.answer.contract import AnswerResult
from backend.chat.config import get_answer_history_limit
from backend.chat.contracts import AccessScope


def _provider():
    if rag.rag_ready():
        from backend.chat.answer.providers import rag as provider
        return provider
    from backend.chat.answer.providers import mock as provider
    return provider


def answer_question(
    question: str,
    messages: list[dict],
    scope: AccessScope,
) -> AnswerResult:
    history = list(messages)[-get_answer_history_limit():]
    return _provider().answer_question(question, history, scope)
