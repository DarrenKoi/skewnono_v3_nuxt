# Chat Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full chat page backed by OpenRouter at home and a company internal OpenAI-compatible LLM at office, with multi-turn history persisted in SQLite (home) and a 30-day archive for later RAG.

**Architecture:** A new `back_dev_home/chat/` feature mirrors the `afm/` seam. Storage swaps mock(SQLite)/office(OpenSearch) via `SKEWNONO_CHAT_PROVIDER`; the LLM endpoint/model list swaps by env config only (`CHAT_BASE_URL`, `CHAT_API_KEY`, `CHAT_MODELS`). The frontend is a standalone `/chat` page with a thread sidebar. Non-streaming: one request, one full reply.

**Tech Stack:** Flask blueprint, `sqlite3` (stdlib), `httpx` (new dep), `python-dotenv` (new dep); Nuxt 4 + NuxtUI, `$fetch` + `useAsyncData`.

## Global Constraints

- Provider seam matches `afm`: `data.py` delegates via `get_data_provider("chat")`; `office.py` raises `_not_connected()` until wired.
- Storage functions are scoped by `user_id` (from `getattr(g, "user_id", None)`).
- Error responses use `error_json(code, message, status)` → `{"error":{"code","message"}}`.
- Blueprints auto-register: each feature exports `bp`; folders starting with `_` are skipped. No manual registration needed.
- Non-streaming only. No `stream` flag on LLM calls.
- Persist the user message BEFORE the LLM call; persist the assistant message only on success.
- Retention: `purge_expired(30)` deletes threads/messages with `updated_at` older than 30 days.
- Run `.venv/bin/pytest` for backend tests. Frontend components are verified in the running app (repo convention: only `utils/*` have vitest tests).
- Markdown edits (none expected here) would need `npm run lint:md`.

---

### Task 1: Dependencies + config module

**Files:**
- Modify: `back_dev_home/requirements.txt`
- Create: `back_dev_home/chat/__init__.py`
- Create: `back_dev_home/chat/config.py`
- Test: `back_dev_home/chat/tests/__init__.py`, `back_dev_home/chat/tests/test_config.py`

**Interfaces:**
- Produces: `config.get_base_url() -> str`, `config.get_api_key() -> str | None`, `config.get_timeout() -> float`, `config.list_models() -> list[dict]` (each `{"id","label"}`).

- [ ] **Step 1: Add dependencies and install**

Append to `back_dev_home/requirements.txt`:

```text
httpx>=0.27
python-dotenv>=1.0
```

Run: `.venv/bin/pip install "httpx>=0.27" "python-dotenv>=1.0"`
Expected: both install successfully.

- [ ] **Step 2: Create empty package + test package files**

Create `back_dev_home/chat/__init__.py`:

```python
"""Chat feature: multi-turn LLM chat with a persisted 30-day archive."""

from back_dev_home.chat.routes import bp

__all__ = ["bp"]
```

> NOTE: `routes.py` does not exist yet — this import will fail until Task 4. To keep Task 1 runnable in isolation, temporarily make `__init__.py` empty (`"""Chat feature."""`) and add the `from ...routes import bp` line in Task 4, Step 6. Do that now: create `__init__.py` with only the docstring.

Create `back_dev_home/chat/tests/__init__.py` (empty file).

- [ ] **Step 3: Write the failing test**

Create `back_dev_home/chat/tests/test_config.py`:

```python
import json

from back_dev_home.chat import config


def test_list_models_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("CHAT_MODELS", raising=False)
    models = config.list_models()
    assert isinstance(models, list)
    assert models
    for m in models:
        assert set(m) >= {"id", "label"}


def test_list_models_parses_env_json(monkeypatch):
    monkeypatch.setenv("CHAT_MODELS", json.dumps([{"id": "x/y", "label": "XY"}]))
    assert config.list_models() == [{"id": "x/y", "label": "XY"}]


def test_base_url_default_and_strip(monkeypatch):
    monkeypatch.delenv("CHAT_BASE_URL", raising=False)
    assert config.get_base_url() == "https://openrouter.ai/api/v1"
    monkeypatch.setenv("CHAT_BASE_URL", "http://internal/v1/")
    assert config.get_base_url() == "http://internal/v1"


def test_timeout_default_and_override(monkeypatch):
    monkeypatch.delenv("CHAT_TIMEOUT", raising=False)
    assert config.get_timeout() == 60.0
    monkeypatch.setenv("CHAT_TIMEOUT", "12")
    assert config.get_timeout() == 12.0
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: back_dev_home.chat.config`.

- [ ] **Step 5: Write minimal implementation**

Create `back_dev_home/chat/config.py`:

```python
"""LLM endpoint/model configuration. Swaps by env only — no code change per phase."""

import json
import os

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MODELS = [
    {"id": "meta-llama/llama-3.3-70b-instruct:free", "label": "Llama 3.3 70B (free)"},
    {"id": "google/gemini-2.0-flash-exp:free", "label": "Gemini 2.0 Flash (free)"},
]


def get_base_url() -> str:
    return os.environ.get("CHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def get_api_key() -> str | None:
    return os.environ.get("CHAT_API_KEY")


def get_timeout() -> float:
    raw = os.environ.get("CHAT_TIMEOUT")
    return float(raw) if raw else DEFAULT_TIMEOUT


def list_models() -> list[dict]:
    raw = os.environ.get("CHAT_MODELS")
    if not raw:
        return [dict(m) for m in DEFAULT_MODELS]
    return json.loads(raw)
```

> The default model ids are free OpenRouter tiers and may change over time. Set `CHAT_MODELS` in `back_dev_home/.env` to the models you actually want (home) or GLM-5.2 / Kimi-2.6 (office).

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/requirements.txt back_dev_home/chat/__init__.py back_dev_home/chat/config.py back_dev_home/chat/tests/
git commit -m "feat(chat): add config module and LLM deps"
```

---

### Task 2: LLM client

**Files:**
- Create: `back_dev_home/chat/llm.py`
- Test: `back_dev_home/chat/tests/test_llm.py`

**Interfaces:**
- Consumes: `config.get_base_url/get_api_key/get_timeout`.
- Produces: `llm.send_chat(model: str, messages: list[dict]) -> dict` with keys `content: str`, `prompt_tokens: int | None`, `completion_tokens: int | None`, `latency_ms: int`. Exceptions `llm.ChatTimeout(message)` and `llm.ChatUpstreamError(message)` (both subclass `llm.ChatError`, both carry `.message`).

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/chat/tests/test_llm.py`:

```python
import httpx
import pytest

from back_dev_home.chat import llm


class _FakeResp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_send_chat_success(monkeypatch):
    payload = {
        "choices": [{"message": {"content": "hi there"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResp(200, payload))
    out = llm.send_chat("m", [{"role": "user", "content": "hi"}])
    assert out["content"] == "hi there"
    assert out["prompt_tokens"] == 5
    assert out["completion_tokens"] == 2
    assert isinstance(out["latency_ms"], int)


def test_send_chat_timeout_raises(monkeypatch):
    def _boom(*a, **k):
        raise httpx.TimeoutException("slow")
    monkeypatch.setattr(httpx, "post", _boom)
    with pytest.raises(llm.ChatTimeout):
        llm.send_chat("m", [])


def test_send_chat_error_status_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResp(500, text="boom"))
    with pytest.raises(llm.ChatUpstreamError):
        llm.send_chat("m", [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: back_dev_home.chat.llm`.

- [ ] **Step 3: Write minimal implementation**

Create `back_dev_home/chat/llm.py`:

```python
"""Stateless OpenAI-compatible chat client. Identical code across phases."""

import time

import httpx

from back_dev_home.chat import config


class ChatError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ChatTimeout(ChatError):
    pass


class ChatUpstreamError(ChatError):
    pass


def send_chat(model: str, messages: list[dict]) -> dict:
    url = f"{config.get_base_url()}/chat/completions"
    headers = {"Content-Type": "application/json"}
    api_key = config.get_api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.perf_counter()
    try:
        resp = httpx.post(
            url,
            json={"model": model, "messages": messages},
            headers=headers,
            timeout=config.get_timeout(),
        )
    except httpx.TimeoutException as exc:
        raise ChatTimeout("The model did not respond in time.") from exc
    except httpx.HTTPError as exc:
        raise ChatUpstreamError(f"Could not reach the model gateway: {exc}") from exc

    latency_ms = int((time.perf_counter() - start) * 1000)

    if resp.status_code >= 400:
        raise ChatUpstreamError(
            f"Model gateway returned {resp.status_code}: {resp.text[:200]}"
        )

    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content", "")
    usage = data.get("usage") or {}
    return {
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "latency_ms": latency_ms,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_llm.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/chat/llm.py back_dev_home/chat/tests/test_llm.py
git commit -m "feat(chat): add OpenAI-compatible LLM client"
```

---

### Task 3: SQLite store, contracts, and data seam

**Files:**
- Create: `back_dev_home/chat/contracts.py`
- Create: `back_dev_home/chat/providers/__init__.py`
- Create: `back_dev_home/chat/providers/mock.py`
- Create: `back_dev_home/chat/providers/office.py`
- Create: `back_dev_home/chat/data.py`
- Test: `back_dev_home/chat/tests/test_store.py`

**Interfaces:**
- Produces (via `data.py`, delegating to the active provider):
  - `create_thread(user_id, model, system_prompt=None) -> Thread`
  - `list_threads(user_id) -> list[ThreadSummary]` (newest first)
  - `get_thread(user_id, thread_id) -> ThreadDetail | None`
  - `rename_thread(user_id, thread_id, title) -> bool`
  - `delete_thread(user_id, thread_id) -> bool`
  - `append_message(thread_id, role, content, meta=None) -> Message`
  - `purge_expired(days=30) -> int`
- `Thread` keys: `id, user_id, title, model, system_prompt, created_at, updated_at`. `ThreadSummary`: `id, title, model, updated_at`. `ThreadDetail` = `Thread` + `messages: list[Message]`. `Message` keys: `id, thread_id, role, content, model, prompt_tokens, completion_tokens, latency_ms, created_at`.
- The mock provider reads its DB path from `SKEWNONO_CHAT_DB` (else `back_dev_home/chat/chat.db`), so tests point it at a temp file.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/chat/tests/test_store.py`:

```python
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from back_dev_home.chat import data


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "mock")


def test_create_and_list_thread():
    t = data.create_thread("u1", "m1", system_prompt="be brief")
    assert t["title"] == "New chat"
    assert t["model"] == "m1"
    rows = data.list_threads("u1")
    assert [r["id"] for r in rows] == [t["id"]]
    assert rows[0]["model"] == "m1"


def test_threads_scoped_by_user():
    data.create_thread("u1", "m1")
    data.create_thread("u2", "m1")
    assert len(data.list_threads("u1")) == 1
    assert len(data.list_threads("u2")) == 1


def test_get_thread_returns_messages_in_order():
    t = data.create_thread("u1", "m1")
    data.append_message(t["id"], "user", "hello")
    data.append_message(t["id"], "assistant", "hi", meta={"latency_ms": 10, "model": "m1"})
    detail = data.get_thread("u1", t["id"])
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["latency_ms"] == 10


def test_get_thread_wrong_user_is_none():
    t = data.create_thread("u1", "m1")
    assert data.get_thread("u2", t["id"]) is None


def test_rename_and_delete():
    t = data.create_thread("u1", "m1")
    assert data.rename_thread("u1", t["id"], "Renamed") is True
    assert data.get_thread("u1", t["id"])["title"] == "Renamed"
    assert data.delete_thread("u1", t["id"]) is True
    assert data.get_thread("u1", t["id"]) is None
    assert data.rename_thread("u1", t["id"], "x") is False


def test_purge_expired_removes_old_threads(tmp_path, monkeypatch):
    t_old = data.create_thread("u1", "m1")
    t_new = data.create_thread("u1", "m1")
    # backdate t_old past the 30-day window
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    conn = sqlite3.connect(str(tmp_path / "chat.db"))
    conn.execute("UPDATE threads SET updated_at=? WHERE id=?", (old, t_old["id"]))
    conn.commit()
    conn.close()
    removed = data.purge_expired(30)
    assert removed == 1
    remaining = [r["id"] for r in data.list_threads("u1")]
    assert remaining == [t_new["id"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: back_dev_home.chat.data`.

- [ ] **Step 3: Create contracts**

Create `back_dev_home/chat/contracts.py`:

```python
"""Stable response contracts for chat endpoints."""

from __future__ import annotations

from typing import TypedDict

__all__ = ["ModelInfo", "Message", "ThreadSummary", "Thread", "ThreadDetail"]


class ModelInfo(TypedDict):
    id: str
    label: str


class Message(TypedDict):
    id: str
    thread_id: str
    role: str
    content: str
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int | None
    created_at: str


class ThreadSummary(TypedDict):
    id: str
    title: str
    model: str
    updated_at: str


class Thread(TypedDict):
    id: str
    user_id: str
    title: str
    model: str
    system_prompt: str | None
    created_at: str
    updated_at: str


class ThreadDetail(Thread):
    messages: list[Message]
```

- [ ] **Step 4: Create the SQLite mock provider**

Create `back_dev_home/chat/providers/__init__.py`:

```python
"""Chat storage adapters."""
```

Create `back_dev_home/chat/providers/mock.py`:

```python
"""Home chat store: SQLite. Survives restart; queryable 30-day archive."""

import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _db_path() -> str:
    override = os.environ.get("SKEWNONO_CHAT_DB")
    if override:
        return override
    return str(Path(__file__).resolve().parents[1] / "chat.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS threads (
          id TEXT PRIMARY KEY, user_id TEXT, title TEXT,
          model TEXT, system_prompt TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY, thread_id TEXT, role TEXT, content TEXT,
          model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
          latency_ms INTEGER, created_at TEXT
        );
        """
    )
    conn.commit()
    return conn


def create_thread(user_id, model, system_prompt=None):
    tid = uuid.uuid4().hex
    now = _now()
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO threads (id,user_id,title,model,system_prompt,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (tid, user_id, "New chat", model, system_prompt, now, now),
        )
    conn.close()
    return {
        "id": tid, "user_id": user_id, "title": "New chat", "model": model,
        "system_prompt": system_prompt, "created_at": now, "updated_at": now,
    }


def list_threads(user_id):
    conn = _connect()
    rows = conn.execute(
        "SELECT id,title,model,updated_at FROM threads WHERE user_id=? ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_thread(user_id, thread_id):
    conn = _connect()
    t = conn.execute(
        "SELECT * FROM threads WHERE id=? AND user_id=?", (thread_id, user_id)
    ).fetchone()
    if t is None:
        conn.close()
        return None
    msgs = conn.execute(
        "SELECT id,thread_id,role,content,model,prompt_tokens,completion_tokens,latency_ms,created_at"
        " FROM messages WHERE thread_id=? ORDER BY created_at ASC, rowid ASC",
        (thread_id,),
    ).fetchall()
    conn.close()
    thread = dict(t)
    thread["messages"] = [dict(m) for m in msgs]
    return thread


def rename_thread(user_id, thread_id, title):
    conn = _connect()
    with conn:
        cur = conn.execute(
            "UPDATE threads SET title=?, updated_at=? WHERE id=? AND user_id=?",
            (title, _now(), thread_id, user_id),
        )
    changed = cur.rowcount > 0
    conn.close()
    return changed


def delete_thread(user_id, thread_id):
    conn = _connect()
    with conn:
        cur = conn.execute(
            "DELETE FROM threads WHERE id=? AND user_id=?", (thread_id, user_id)
        )
        if cur.rowcount > 0:
            conn.execute("DELETE FROM messages WHERE thread_id=?", (thread_id,))
    changed = cur.rowcount > 0
    conn.close()
    return changed


def append_message(thread_id, role, content, meta=None):
    meta = meta or {}
    mid = uuid.uuid4().hex
    now = _now()
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO messages (id,thread_id,role,content,model,prompt_tokens,"
            "completion_tokens,latency_ms,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (mid, thread_id, role, content, meta.get("model"),
             meta.get("prompt_tokens"), meta.get("completion_tokens"),
             meta.get("latency_ms"), now),
        )
        conn.execute("UPDATE threads SET updated_at=? WHERE id=?", (now, thread_id))
    conn.close()
    return {
        "id": mid, "thread_id": thread_id, "role": role, "content": content,
        "model": meta.get("model"), "prompt_tokens": meta.get("prompt_tokens"),
        "completion_tokens": meta.get("completion_tokens"),
        "latency_ms": meta.get("latency_ms"), "created_at": now,
    }


def purge_expired(days=30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = _connect()
    with conn:
        conn.execute(
            "DELETE FROM messages WHERE thread_id IN "
            "(SELECT id FROM threads WHERE updated_at < ?)",
            (cutoff,),
        )
        cur = conn.execute("DELETE FROM threads WHERE updated_at < ?", (cutoff,))
    removed = cur.rowcount
    conn.close()
    return removed
```

- [ ] **Step 5: Create the office stub**

Create `back_dev_home/chat/providers/office.py`:

```python
"""Office chat store hookup point (OpenSearch). Not yet connected."""


def _not_connected(*args, **kwargs):
    raise NotImplementedError(
        "The chat office adapter has not been connected. "
        "Configure the approved chat data platform before selecting office mode."
    )


create_thread = _not_connected
list_threads = _not_connected
get_thread = _not_connected
rename_thread = _not_connected
delete_thread = _not_connected
append_message = _not_connected
purge_expired = _not_connected
```

- [ ] **Step 6: Create the data seam**

Create `back_dev_home/chat/data.py`:

```python
"""Stable chat storage seam with mock/office adapters."""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.chat.contracts import (
    Message, Thread, ThreadDetail, ThreadSummary,
)

__all__ = [
    "Message", "Thread", "ThreadDetail", "ThreadSummary",
    "create_thread", "list_threads", "get_thread",
    "rename_thread", "delete_thread", "append_message", "purge_expired",
]


def _provider():
    if get_data_provider("chat") == "office":
        from back_dev_home.chat.providers import office
        return office
    from back_dev_home.chat.providers import mock
    return mock


def create_thread(user_id, model, system_prompt=None):
    return _provider().create_thread(user_id, model, system_prompt)


def list_threads(user_id):
    return _provider().list_threads(user_id)


def get_thread(user_id, thread_id):
    return _provider().get_thread(user_id, thread_id)


def rename_thread(user_id, thread_id, title):
    return _provider().rename_thread(user_id, thread_id, title)


def delete_thread(user_id, thread_id):
    return _provider().delete_thread(user_id, thread_id)


def append_message(thread_id, role, content, meta=None):
    return _provider().append_message(thread_id, role, content, meta)


def purge_expired(days=30):
    return _provider().purge_expired(days)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_store.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Commit**

```bash
git add back_dev_home/chat/contracts.py back_dev_home/chat/providers/ back_dev_home/chat/data.py back_dev_home/chat/tests/test_store.py
git commit -m "feat(chat): add SQLite store, contracts, and data seam"
```

---

### Task 4: Routes and orchestration

**Files:**
- Create: `back_dev_home/chat/routes.py`
- Modify: `back_dev_home/chat/__init__.py` (add `bp` re-export)
- Test: `back_dev_home/chat/tests/test_routes.py`

**Interfaces:**
- Consumes: `config.list_models`, `data.*`, `llm.send_chat` / `llm.ChatTimeout` / `llm.ChatUpstreamError`.
- Produces: Flask `bp` with routes under `/api/chat`. All success bodies are `{"data": ...}`.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/chat/tests/test_routes.py`:

```python
import pytest
from flask import Flask, g

from back_dev_home.chat import llm
from back_dev_home.chat.routes import bp


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "mock")
    app = Flask(__name__)
    app.register_blueprint(bp, url_prefix="/api")

    @app.before_request
    def _uid():
        g.user_id = "u1"

    return app.test_client()


def test_models_endpoint(client):
    r = client.get("/api/chat/models")
    assert r.status_code == 200
    assert isinstance(r.get_json()["data"], list)


def test_create_and_list_thread(client):
    r = client.post("/api/chat/threads", json={"model": "m1"})
    assert r.status_code == 201
    tid = r.get_json()["data"]["id"]
    listed = client.get("/api/chat/threads").get_json()["data"]
    assert [t["id"] for t in listed] == [tid]


def test_create_requires_model(client):
    r = client.post("/api/chat/threads", json={})
    assert r.status_code == 400


def test_send_message_persists_reply(client, monkeypatch):
    monkeypatch.setattr(llm, "send_chat", lambda model, messages: {
        "content": "pong", "prompt_tokens": 3, "completion_tokens": 1, "latency_ms": 7,
    })
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]
    r = client.post(f"/api/chat/threads/{tid}/messages", json={"content": "ping"})
    assert r.status_code == 200
    body = r.get_json()["data"]
    assert body["role"] == "assistant"
    assert body["content"] == "pong"
    assert body["latency_ms"] == 7
    roles = [m["role"] for m in client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]]
    assert roles == ["user", "assistant"]


def test_send_message_timeout_preserves_user_message(client, monkeypatch):
    def _boom(model, messages):
        raise llm.ChatTimeout("too slow")
    monkeypatch.setattr(llm, "send_chat", _boom)
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]
    r = client.post(f"/api/chat/threads/{tid}/messages", json={"content": "ping"})
    assert r.status_code == 504
    msgs = client.get(f"/api/chat/threads/{tid}").get_json()["data"]["messages"]
    assert [m["role"] for m in msgs] == ["user"]  # user msg kept, no assistant


def test_send_message_requires_content(client):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]
    r = client.post(f"/api/chat/threads/{tid}/messages", json={"content": "  "})
    assert r.status_code == 400


def test_get_unknown_thread_404(client):
    assert client.get("/api/chat/threads/nope").status_code == 404


def test_delete_thread(client):
    tid = client.post("/api/chat/threads", json={"model": "m1"}).get_json()["data"]["id"]
    assert client.delete(f"/api/chat/threads/{tid}").status_code == 200
    assert client.get(f"/api/chat/threads/{tid}").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: back_dev_home.chat.routes`.

- [ ] **Step 3: Write the routes**

Create `back_dev_home/chat/routes.py`:

```python
"""Chat blueprint: models, threads CRUD, and the send-message orchestration."""

from flask import Blueprint, g, request

from back_dev_home._auth.errors import error_json
from back_dev_home.chat import config, data, llm

bp = Blueprint("chat", __name__)


def _uid() -> str:
    return getattr(g, "user_id", None) or "anon"


@bp.get("/chat/models")
def chat_models():
    return {"data": config.list_models()}


@bp.get("/chat/threads")
def chat_list_threads():
    data.purge_expired(30)
    return {"data": data.list_threads(_uid())}


@bp.post("/chat/threads")
def chat_create_thread():
    body = request.get_json(silent=True) or {}
    model = body.get("model")
    if not model:
        return error_json("bad_request", "model is required", 400)
    thread = data.create_thread(_uid(), model, body.get("system_prompt"))
    thread["messages"] = []
    return {"data": thread}, 201


@bp.get("/chat/threads/<thread_id>")
def chat_get_thread(thread_id):
    thread = data.get_thread(_uid(), thread_id)
    if thread is None:
        return error_json("not_found", "thread not found", 404)
    return {"data": thread}


@bp.patch("/chat/threads/<thread_id>")
def chat_rename_thread(thread_id):
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return error_json("bad_request", "title is required", 400)
    if not data.rename_thread(_uid(), thread_id, title):
        return error_json("not_found", "thread not found", 404)
    return {"data": {"id": thread_id, "title": title}}


@bp.delete("/chat/threads/<thread_id>")
def chat_delete_thread(thread_id):
    if not data.delete_thread(_uid(), thread_id):
        return error_json("not_found", "thread not found", 404)
    return {"data": {"id": thread_id, "deleted": True}}


@bp.post("/chat/threads/<thread_id>/messages")
def chat_send_message(thread_id):
    body = request.get_json(silent=True) or {}
    content = (body.get("content") or "").strip()
    if not content:
        return error_json("bad_request", "content is required", 400)

    thread = data.get_thread(_uid(), thread_id)
    if thread is None:
        return error_json("not_found", "thread not found", 404)

    # Persist the user message BEFORE the LLM call so a failure never loses it.
    data.append_message(thread_id, "user", content)

    payload = []
    if thread.get("system_prompt"):
        payload.append({"role": "system", "content": thread["system_prompt"]})
    for m in thread["messages"]:
        payload.append({"role": m["role"], "content": m["content"]})
    payload.append({"role": "user", "content": content})

    try:
        reply = llm.send_chat(thread["model"], payload)
    except llm.ChatTimeout as exc:
        return error_json("gateway_timeout", exc.message, 504)
    except llm.ChatUpstreamError as exc:
        return error_json("bad_gateway", exc.message, 502)

    assistant = data.append_message(
        thread_id, "assistant", reply["content"],
        meta={
            "model": thread["model"],
            "prompt_tokens": reply["prompt_tokens"],
            "completion_tokens": reply["completion_tokens"],
            "latency_ms": reply["latency_ms"],
        },
    )
    return {"data": assistant}
```

- [ ] **Step 4: Wire the blueprint re-export**

Replace `back_dev_home/chat/__init__.py` contents with:

```python
"""Chat feature: multi-turn LLM chat with a persisted 30-day archive."""

from back_dev_home.chat.routes import bp

__all__ = ["bp"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_routes.py -v`
Expected: PASS (8 tests).

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/chat/routes.py back_dev_home/chat/__init__.py back_dev_home/chat/tests/test_routes.py
git commit -m "feat(chat): add chat routes and send-message orchestration"
```

---

### Task 5: App wiring — dotenv, gitignore, boot check

**Files:**
- Modify: `back_dev_home/__init__.py` (load `.env` in `create_app`)
- Modify: `.gitignore` (ignore `chat.db`)
- Test: `back_dev_home/chat/tests/test_app_boot.py`

**Interfaces:**
- Consumes: `create_app` from `back_dev_home`.
- Produces: `.env` values loaded at startup; `/api/chat/models` reachable on the full app.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/chat/tests/test_app_boot.py`:

```python
import back_dev_home
from back_dev_home import create_app


def test_chat_routes_registered():
    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/chat/models" in rules
    assert "/api/chat/threads" in rules


def test_create_app_loads_dotenv():
    # create_app must import load_dotenv at module scope and call it at startup
    # so CHAT_API_KEY from back_dev_home/.env is available to the LLM client.
    assert callable(back_dev_home.load_dotenv)
    # smoke: building the app twice must not raise
    create_app()
    create_app()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_app_boot.py -v`
Expected: FAIL — `test_dotenv_loaded...` fails because `back_dev_home.load_dotenv` does not exist yet. (`test_chat_routes_registered` should already PASS since the blueprint auto-registers.)

- [ ] **Step 3: Load dotenv in the app factory**

In `back_dev_home/__init__.py`, add near the top imports:

```python
from dotenv import load_dotenv
```

Then as the FIRST lines inside `def create_app() -> Flask:` (before `app = Flask(__name__)`):

```python
def create_app() -> Flask:
    load_dotenv(Path(__file__).parent / ".env")
    app = Flask(__name__)
```

(`Path` is already imported in this module.)

- [ ] **Step 4: Ignore the SQLite db**

Append to `.gitignore` (repo root):

```text
# Chat feature local store (home/Phase 1)
back_dev_home/chat/chat.db
*.db
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/chat/tests/test_app_boot.py -v`
Expected: PASS (2 tests).

Confirm the db is ignored:
Run: `git check-ignore back_dev_home/chat/chat.db`
Expected: prints the path.

- [ ] **Step 6: Full backend suite**

Run: `.venv/bin/pytest back_dev_home/chat -v`
Expected: all chat tests PASS.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/__init__.py .gitignore back_dev_home/chat/tests/test_app_boot.py
git commit -m "feat(chat): load .env at startup and ignore local chat.db"
```

---

### Task 6: Frontend API composable

**Files:**
- Create: `front-dev-home/app/composables/useChatApi.ts`

**Interfaces:**
- Produces: `useChatApi()` returning `fetchModels`, `fetchThreads`, `fetchThread`, `createThread`, `renameThread`, `deleteThread`, `sendMessage`; plus exported types `ChatModel`, `ChatMessage`, `ThreadSummary`, `ThreadDetail`.

- [ ] **Step 1: Create the composable**

Create `front-dev-home/app/composables/useChatApi.ts`:

```ts
import { joinApiPath } from '~/utils/apiPath'

export interface ChatModel {
  id: string
  label: string
}

export interface ChatMessage {
  id: string
  thread_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  model?: string | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  latency_ms?: number | null
  created_at: string
}

export interface ThreadSummary {
  id: string
  title: string
  model: string
  updated_at: string
}

export interface ThreadDetail extends ThreadSummary {
  user_id: string
  system_prompt?: string | null
  created_at: string
  messages: ChatMessage[]
}

export const useChatApi = () => {
  const config = useRuntimeConfig()
  const url = (p: string) => joinApiPath(config.public.apiBase, p)

  const fetchModels = async (): Promise<ChatModel[]> =>
    (await $fetch<{ data: ChatModel[] }>(url('/chat/models'))).data

  const fetchThreads = async (): Promise<ThreadSummary[]> =>
    (await $fetch<{ data: ThreadSummary[] }>(url('/chat/threads'))).data

  const fetchThread = async (id: string): Promise<ThreadDetail> =>
    (await $fetch<{ data: ThreadDetail }>(url(`/chat/threads/${id}`))).data

  const createThread = async (model: string, systemPrompt?: string): Promise<ThreadDetail> => {
    const t = (await $fetch<{ data: ThreadDetail }>(url('/chat/threads'), {
      method: 'POST',
      body: { model, system_prompt: systemPrompt || null }
    })).data
    return { ...t, messages: t.messages ?? [] }
  }

  const renameThread = async (id: string, title: string): Promise<void> => {
    await $fetch(url(`/chat/threads/${id}`), { method: 'PATCH', body: { title } })
  }

  const deleteThread = async (id: string): Promise<void> => {
    await $fetch(url(`/chat/threads/${id}`), { method: 'DELETE' })
  }

  const sendMessage = async (id: string, content: string): Promise<ChatMessage> =>
    (await $fetch<{ data: ChatMessage }>(url(`/chat/threads/${id}/messages`), {
      method: 'POST',
      body: { content }
    })).data

  return {
    fetchModels, fetchThreads, fetchThread,
    createThread, renameThread, deleteThread, sendMessage
  }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd front-dev-home && npx nuxi typecheck 2>&1 | tail -20`
Expected: no errors referencing `useChatApi.ts`. (Pre-existing unrelated errors elsewhere, if any, are out of scope.)

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/composables/useChatApi.ts
git commit -m "feat(chat): add useChatApi composable"
```

---

### Task 7: Chat page and components

**Files:**
- Create: `front-dev-home/app/components/chat/ChatMessage.vue`
- Create: `front-dev-home/app/components/chat/ChatComposer.vue`
- Create: `front-dev-home/app/components/chat/ModelPicker.vue`
- Create: `front-dev-home/app/components/chat/SystemPromptField.vue`
- Create: `front-dev-home/app/components/chat/ChatSidebar.vue`
- Create: `front-dev-home/app/components/chat/ChatThread.vue`
- Create: `front-dev-home/app/pages/chat.vue`

**Interfaces:**
- Consumes: `useChatApi()` and its types from Task 6.
- Produces: a working `/chat` route.

- [ ] **Step 1: ChatMessage.vue (one bubble + assistant meta)**

Create `front-dev-home/app/components/chat/ChatMessage.vue`:

```vue
<script setup lang="ts">
import type { ChatMessage } from '~/composables/useChatApi'

const props = defineProps<{ message: ChatMessage; pending?: boolean; error?: boolean }>()

const isUser = computed(() => props.message.role === 'user')
const meta = computed(() => {
  const m = props.message
  const bits: string[] = []
  if (m.latency_ms != null) bits.push(`${m.latency_ms} ms`)
  const tokens = (m.prompt_tokens ?? 0) + (m.completion_tokens ?? 0)
  if (tokens) bits.push(`${tokens} tok`)
  return bits.join(' · ')
})
</script>

<template>
  <div
    class="flex"
    :class="isUser ? 'justify-end' : 'justify-start'"
  >
    <div
      class="max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap"
      :class="[
        isUser ? 'bg-sky-500 text-white' : 'bg-elevated text-default',
        error ? 'ring-1 ring-error' : ''
      ]"
    >
      <span v-if="pending" class="opacity-70">…</span>
      <template v-else>{{ message.content }}</template>
      <div
        v-if="!isUser && !pending && meta"
        class="sk-meta mt-1 opacity-70"
      >
        {{ meta }}
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: ModelPicker.vue**

Create `front-dev-home/app/components/chat/ModelPicker.vue`:

```vue
<script setup lang="ts">
import type { ChatModel } from '~/composables/useChatApi'

defineProps<{ models: ChatModel[]; disabled?: boolean }>()
const model = defineModel<string>()
</script>

<template>
  <USelect
    v-model="model"
    :items="models.map(m => ({ label: m.label, value: m.id }))"
    :disabled="disabled"
    placeholder="모델 선택"
    class="min-w-48"
  />
</template>
```

- [ ] **Step 3: SystemPromptField.vue (collapsible)**

Create `front-dev-home/app/components/chat/SystemPromptField.vue`:

```vue
<script setup lang="ts">
const value = defineModel<string>()
const open = ref(false)
</script>

<template>
  <div class="border-b border-default">
    <button
      type="button"
      class="flex items-center gap-1 px-4 py-2 sk-meta w-full text-left"
      @click="open = !open"
    >
      <UIcon :name="open ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'" />
      시스템 프롬프트
    </button>
    <div v-if="open" class="px-4 pb-3">
      <UTextarea
        v-model="value"
        :rows="3"
        class="w-full"
        placeholder="이 대화의 시스템 프롬프트 (선택)"
      />
    </div>
  </div>
</template>
```

- [ ] **Step 4: ChatComposer.vue**

Create `front-dev-home/app/components/chat/ChatComposer.vue`:

```vue
<script setup lang="ts">
const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()
const text = ref('')

const submit = () => {
  const value = text.value.trim()
  if (!value || props.disabled) return
  emit('send', value)
  text.value = ''
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="flex items-end gap-2 border-t border-default p-3">
    <UTextarea
      v-model="text"
      :rows="1"
      autoresize
      :disabled="disabled"
      placeholder="메시지를 입력하세요 (Enter 전송, Shift+Enter 줄바꿈)"
      class="flex-1"
      @keydown="onKeydown"
    />
    <UButton
      icon="i-lucide-send"
      :disabled="disabled || !text.trim()"
      @click="submit"
    />
  </div>
</template>
```

- [ ] **Step 5: ChatSidebar.vue**

Create `front-dev-home/app/components/chat/ChatSidebar.vue`:

```vue
<script setup lang="ts">
import type { ThreadSummary } from '~/composables/useChatApi'

defineProps<{ threads: ThreadSummary[]; activeId: string | null }>()
const emit = defineEmits<{
  select: [id: string]
  create: []
  remove: [id: string]
}>()
</script>

<template>
  <aside class="w-64 shrink-0 border-r border-default flex flex-col">
    <div class="p-3">
      <UButton
        block
        icon="i-lucide-plus"
        label="새 대화"
        @click="emit('create')"
      />
    </div>
    <div class="flex-1 overflow-y-auto">
      <div
        v-for="t in threads"
        :key="t.id"
        class="group flex items-center gap-1 px-3 py-2 cursor-pointer hover:bg-elevated"
        :class="t.id === activeId ? 'bg-elevated' : ''"
        @click="emit('select', t.id)"
      >
        <span class="flex-1 truncate text-sm">{{ t.title }}</span>
        <UButton
          icon="i-lucide-trash-2"
          color="neutral"
          variant="ghost"
          size="xs"
          class="opacity-0 group-hover:opacity-100"
          @click.stop="emit('remove', t.id)"
        />
      </div>
      <p v-if="!threads.length" class="sk-meta px-3 py-2">대화가 없습니다.</p>
    </div>
  </aside>
</template>
```

- [ ] **Step 6: ChatThread.vue (message list)**

Create `front-dev-home/app/components/chat/ChatThread.vue`:

```vue
<script setup lang="ts">
import type { ChatMessage } from '~/composables/useChatApi'

defineProps<{
  messages: ChatMessage[]
  pending?: boolean
  errorMessage?: string | null
}>()
const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <div class="flex-1 overflow-y-auto p-4 space-y-3">
    <ChatMessage
      v-for="m in messages"
      :key="m.id"
      :message="m"
    />
    <ChatMessage
      v-if="pending"
      :message="{ id: 'pending', thread_id: '', role: 'assistant', content: '', created_at: '' }"
      pending
    />
    <div v-if="errorMessage" class="flex justify-start">
      <div class="max-w-[80%] rounded-lg px-3 py-2 text-sm bg-elevated ring-1 ring-error">
        <p class="text-error">{{ errorMessage }}</p>
        <UButton
          size="xs"
          variant="ghost"
          icon="i-lucide-rotate-cw"
          label="다시 시도"
          class="mt-1"
          @click="emit('retry')"
        />
      </div>
    </div>
    <p v-if="!messages.length && !pending" class="sk-meta text-center mt-8">
      메시지를 보내 대화를 시작하세요.
    </p>
  </div>
</template>
```

- [ ] **Step 7: chat.vue (page — orchestrates everything)**

Create `front-dev-home/app/pages/chat.vue`:

```vue
<script setup lang="ts">
import type { ChatMessage, ChatModel, ThreadDetail, ThreadSummary } from '~/composables/useChatApi'

const api = useChatApi()

const models = ref<ChatModel[]>([])
const selectedModel = ref<string>('')
const threads = ref<ThreadSummary[]>([])
const active = ref<ThreadDetail | null>(null)
const systemPrompt = ref('')
const pending = ref(false)
const errorMessage = ref<string | null>(null)
const lastSent = ref<string | null>(null)

const activeId = computed(() => active.value?.id ?? null)

const loadThreads = async () => {
  threads.value = await api.fetchThreads()
}

const openThread = async (id: string) => {
  errorMessage.value = null
  active.value = await api.fetchThread(id)
  systemPrompt.value = active.value.system_prompt ?? ''
  selectedModel.value = active.value.model
}

const newThread = async () => {
  const t = await api.createThread(selectedModel.value || models.value[0]?.id || '', systemPrompt.value)
  active.value = t
  await loadThreads()
}

const removeThread = async (id: string) => {
  await api.deleteThread(id)
  if (active.value?.id === id) active.value = null
  await loadThreads()
}

const send = async (text: string) => {
  if (!active.value) await newThread()
  const thread = active.value!
  errorMessage.value = null
  lastSent.value = text
  active.value!.messages.push({
    id: `local-${Date.now()}`, thread_id: thread.id, role: 'user',
    content: text, created_at: new Date().toISOString()
  })
  pending.value = true
  try {
    const reply: ChatMessage = await api.sendMessage(thread.id, text)
    active.value!.messages.push(reply)
    lastSent.value = null
    await loadThreads()
  } catch (e: unknown) {
    const err = e as { data?: { error?: { message?: string } } }
    errorMessage.value = err?.data?.error?.message ?? '응답을 받지 못했습니다.'
  } finally {
    pending.value = false
  }
}

const retry = () => {
  if (lastSent.value) send(lastSent.value)
}

onMounted(async () => {
  models.value = await api.fetchModels()
  selectedModel.value = models.value[0]?.id ?? ''
  await loadThreads()
})
</script>

<template>
  <div class="flex h-[calc(100vh-4rem)]">
    <ChatSidebar
      :threads="threads"
      :active-id="activeId"
      @select="openThread"
      @create="newThread"
      @remove="removeThread"
    />
    <section class="flex-1 flex flex-col min-w-0">
      <div class="flex items-center gap-3 border-b border-default px-4 py-2">
        <h1 class="sk-page-title text-base flex items-center gap-2">
          <UIcon name="i-lucide-message-square" class="text-sky-500" />
          채팅
        </h1>
        <div class="ml-auto">
          <ChatModelPicker v-model="selectedModel" :models="models" :disabled="!!active" />
        </div>
      </div>
      <ChatSystemPromptField v-model="systemPrompt" />
      <ChatThread
        :messages="active?.messages ?? []"
        :pending="pending"
        :error-message="errorMessage"
        @retry="retry"
      />
      <ChatComposer :disabled="pending || !selectedModel" @send="send" />
    </section>
  </div>
</template>
```

> Note: NuxtUI auto-imports components by path; `components/chat/ChatModelPicker.vue` would be `<ChatModelPicker>`. The files are named `ModelPicker.vue` etc. under `components/chat/`, so their auto-import names are `<ChatModelPicker>`, `<ChatSystemPromptField>`, `<ChatSidebar>`, `<ChatThread>`, `<ChatComposer>`, `<ChatMessage>`. Confirm your Nuxt `components` config uses path-prefixed names (default). If your project disables prefixing, use `<ModelPicker>` etc. instead.

- [ ] **Step 8: Typecheck**

Run: `cd front-dev-home && npx nuxi typecheck 2>&1 | tail -20`
Expected: no new errors in `pages/chat.vue` or `components/chat/*`.

- [ ] **Step 9: Verify in the running app**

Use the `verify` skill (Flask mock on :5050 + Nuxt on :3000). With `CHAT_API_KEY` set in `back_dev_home/.env` and internet available, navigate to `/chat`:
- Create a new chat, pick a free model, send "hello" → assistant reply renders with latency/token meta.
- Reload → the thread persists in the sidebar; reopen it and the history is intact.
- Delete a thread → it disappears.
- Set a wrong model id (or disconnect) → error bubble + 다시 시도 works and your typed message is preserved.

- [ ] **Step 10: Commit**

```bash
git add front-dev-home/app/components/chat/ front-dev-home/app/pages/chat.vue
git commit -m "feat(chat): add chat page, sidebar, thread view, and composer"
```

---

### Task 8: Navigation entry

**Files:**
- Modify: `front-dev-home/app/components/nav/AppHeader.vue`

**Interfaces:**
- Consumes: the `/chat` route from Task 7.

- [ ] **Step 1: Add a header link**

In `front-dev-home/app/components/nav/AppHeader.vue`, add a header action button next to the existing `/activity` and `/settings` links, following the exact same pattern (`to`, `icon`, `aria-label`, `:aria-current`, `:class="headerActionClass('/chat')"`):

```vue
      <NuxtLink
        to="/chat"
        icon="i-lucide-message-square"
        aria-label="채팅"
        :aria-current="isActivePath('/chat') ? 'page' : undefined"
        :class="headerActionClass('/chat')"
      />
```

Match the surrounding element type — if the existing links are `<UButton>`/`<UChip>` rather than bare `<NuxtLink>`, copy that exact element with these prop values. (The grep in planning showed `to=` / `icon=` / `aria-label=` / `:aria-current=` / `:class` props on each entry.)

- [ ] **Step 2: Verify in the running app**

Reload the app. The chat icon appears in the header; clicking it routes to `/chat` and highlights as active.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/components/nav/AppHeader.vue
git commit -m "feat(chat): add chat link to app header"
```

---

## Self-Review notes

- **Spec coverage:** config/env (T1), LLM client + non-streaming + error taxonomy (T2), SQLite store + contracts + seam + retention (T3), endpoints + persist-before-LLM orchestration (T4), dotenv + gitignore + boot (T5), composable (T6), page/sidebar/thread/composer/model-picker/system-prompt (T7), nav (T8). RAG, streaming, memory-into-prompt, new auth = out of scope (unchanged).
- **Type consistency:** `send_chat` returns `{content, prompt_tokens, completion_tokens, latency_ms}` — consumed identically in T4; `data.*` signatures identical across T3 definition and T4 calls; frontend `ChatMessage`/`ThreadDetail` shapes match backend contract keys.
- **Known follow-ups (deferred, per spec):** auto-title (threads stay "New chat" until renamed), streaming, copy-message button.
