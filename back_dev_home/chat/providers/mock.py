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
