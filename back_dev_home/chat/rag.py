"""Import bridge to the office RAG checkout, which the chat feature calls in-process.

The RAG is a separate git repository (사내, never pushed here) whose top-level
package is ``src`` — ``src.retrieve.serve.search_manuals``,
``src.retrieve.agent.rewrite_query`` / ``generate_follow_ups``. It is checked
out at ``back_dev_home/chat/_rag/`` by default: the leading underscore is what
keeps a whole foreign repo inert inside this tree — the app factory's
``routes.py`` scan, the office registry's ``providers/`` scan and the deploy
pack all skip ``_``-prefixed directories, and ``.gitignore`` hides it from this
repo (its own ``.git`` keeps working: ``git -C back_dev_home/chat/_rag pull``).
``SKEWNONO_CHAT_RAG_ROOT`` points anywhere else.

``import_rag("retrieve.serve")`` is the only import path: it puts the root on
``sys.path`` once and turns every failure — no checkout, a half-cloned tree,
a missing 사내 dependency — into ``KnowledgeUnavailable`` so the caller reports
503 instead of a 500 from a bare ``ModuleNotFoundError``.
"""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from types import ModuleType

from back_dev_home.chat.knowledge.contracts import KnowledgeUnavailable

_DEFAULT_ROOT: Path | None = Path(__file__).resolve().parent / "_rag"
_PACKAGE = "src"


def rag_root() -> Path | None:
    """Directory holding the RAG's ``src/`` package, or None when absent."""
    raw = os.environ.get("SKEWNONO_CHAT_RAG_ROOT", "").strip()
    root = Path(raw) if raw else _DEFAULT_ROOT
    if root is None or not (root / _PACKAGE).is_dir():
        return None
    return root.resolve()


def import_rag(module: str) -> ModuleType:
    """Import ``src.<module>`` from the checkout; unavailable when it cannot be."""
    root = rag_root()
    if root is None:
        raise KnowledgeUnavailable(
            "The office RAG checkout is not present; set SKEWNONO_CHAT_RAG_ROOT "
            "or clone it to back_dev_home/chat/_rag."
        )
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    name = f"{_PACKAGE}.{module}"
    try:
        return import_module(name)
    except Exception as error:  # noqa: BLE001 — every failure is a 503, not a 500
        raise KnowledgeUnavailable(
            f"The office RAG module {name} could not be imported."
        ) from error
