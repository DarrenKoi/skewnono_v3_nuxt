"""The import bridge to the co-located office RAG checkout (``skewnono_rag.*``)."""

from __future__ import annotations

import sys
import types

import pytest

from back_dev_home.chat import rag
from back_dev_home.chat.knowledge.contracts import KnowledgeUnavailable


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv("SKEWNONO_CHAT_RAG_ROOT", raising=False)
    monkeypatch.setattr(rag, "_DEFAULT_ROOT", None)
    monkeypatch.setattr(sys, "path", list(sys.path))


def test_env_root_wins_over_the_default(tmp_path, monkeypatch):
    (tmp_path / "skewnono_rag").mkdir()
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))

    assert rag.rag_root() == tmp_path.resolve()


def test_default_root_is_the_underscore_rag_checkout(tmp_path, monkeypatch):
    checkout = tmp_path / "_rag"
    (checkout / "skewnono_rag").mkdir(parents=True)
    monkeypatch.setattr(rag, "_DEFAULT_ROOT", checkout)

    assert rag.rag_root() == checkout.resolve()


def test_root_without_the_rag_package_is_not_a_checkout(tmp_path, monkeypatch):
    """An empty or half-cloned directory must read as absent, not as a RAG."""
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))

    assert rag.rag_root() is None


def test_import_without_a_checkout_is_unavailable_not_import_error():
    with pytest.raises(KnowledgeUnavailable, match="RAG"):
        rag.import_rag("retrieve.serve")


def test_import_puts_the_root_on_sys_path_once(tmp_path, monkeypatch):
    (tmp_path / "skewnono_rag").mkdir()
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))
    fake = types.ModuleType("skewnono_rag.retrieve.serve")
    monkeypatch.setitem(sys.modules, "skewnono_rag.retrieve.serve", fake)

    assert rag.import_rag("retrieve.serve") is fake
    assert rag.import_rag("retrieve.serve") is fake
    assert sys.path.count(str(tmp_path.resolve())) == 1
    assert sys.path[0] == str(tmp_path.resolve())


def test_broken_rag_module_is_unavailable(tmp_path, monkeypatch):
    (tmp_path / "skewnono_rag").mkdir()
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))

    with pytest.raises(KnowledgeUnavailable, match="retrieve.missing"):
        rag.import_rag("retrieve.missing")


def test_index_dir_defaults_inside_the_package(tmp_path, monkeypatch):
    (tmp_path / "skewnono_rag" / "index").mkdir(parents=True)
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))
    monkeypatch.delenv("SKEWNONO_RAG_INDEX_DIR", raising=False)

    assert rag.index_dir() == tmp_path.resolve() / "skewnono_rag" / "index"


def test_index_dir_env_override_wins_without_a_checkout(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_RAG_ROOT", str(tmp_path))  # no package
    monkeypatch.setenv("SKEWNONO_RAG_INDEX_DIR", str(tmp_path / "elsewhere"))

    assert rag.index_dir() == tmp_path / "elsewhere"
