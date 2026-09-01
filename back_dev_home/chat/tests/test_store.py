import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from back_dev_home.chat import store


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))


def test_existing_db_gains_new_source_columns(tmp_path):
    """Catches a source column added to the DDL but not migrated.

    CREATE TABLE IF NOT EXISTS never revisits an existing table, so a dev or
    an office host carrying a chat.db from before the column would keep a
    table without it and fail on the next INSERT — long after the change
    looked green on a fresh database.
    """
    legacy = sqlite3.connect(str(tmp_path / "chat.db"))
    legacy.executescript(
        """
        CREATE TABLE message_sources (
          message_id TEXT NOT NULL, position INTEGER NOT NULL,
          source_id TEXT NOT NULL, source_type TEXT NOT NULL,
          title TEXT NOT NULL, snippet TEXT NOT NULL, revision TEXT,
          occurred_at TEXT, section TEXT, page INTEGER, region TEXT,
          locator TEXT, score REAL, PRIMARY KEY (message_id, position)
        );
        """
    )
    legacy.commit()
    legacy.close()

    conn = store._connect()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(message_sources)")}
    conn.close()

    assert "figure_id" in columns


def test_create_and_list_thread():
    t = store.create_thread("u1")
    assert t["title"] == "New chat"
    # No model and no system prompt: both belong to the RAG.
    assert set(t) == {"id", "user_id", "title", "created_at", "updated_at"}
    rows = store.list_threads("u1")
    assert [r["id"] for r in rows] == [t["id"]]
    assert set(rows[0]) == {"id", "title", "updated_at"}


def test_threads_scoped_by_user():
    store.create_thread("u1")
    store.create_thread("u2")
    assert len(store.list_threads("u1")) == 1
    assert len(store.list_threads("u2")) == 1


def test_get_thread_returns_messages_in_order():
    t = store.create_thread("u1")
    store.append_message(t["id"], "user", "hello")
    store.append_message(t["id"], "assistant", "hi", meta={"latency_ms": 10, "model": "m1"})
    detail = store.get_thread("u1", t["id"])
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["latency_ms"] == 10


def test_get_thread_wrong_user_is_none():
    t = store.create_thread("u1")
    assert store.get_thread("u2", t["id"]) is None


def test_rename_and_delete():
    t = store.create_thread("u1")
    assert store.rename_thread("u1", t["id"], "Renamed") is True
    assert store.get_thread("u1", t["id"])["title"] == "Renamed"
    assert store.delete_thread("u1", t["id"]) is True
    assert store.get_thread("u1", t["id"]) is None
    assert store.rename_thread("u1", t["id"], "x") is False


def test_purge_expired_removes_old_threads(tmp_path, monkeypatch):
    t_old = store.create_thread("u1")
    t_new = store.create_thread("u1")
    # backdate t_old past the 30-day window
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    conn = sqlite3.connect(str(tmp_path / "chat.db"))
    conn.execute("UPDATE threads SET updated_at=? WHERE id=?", (old, t_old["id"]))
    conn.commit()
    conn.close()
    removed = store.purge_expired(30)
    assert removed == 1
    remaining = [r["id"] for r in store.list_threads("u1")]
    assert remaining == [t_new["id"]]


def test_opening_legacy_database_adds_schema_without_losing_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "chat.db"
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(db_path))
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE threads (
          id TEXT PRIMARY KEY, user_id TEXT, title TEXT,
          model TEXT, system_prompt TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE messages (
          id TEXT PRIMARY KEY, thread_id TEXT, role TEXT, content TEXT,
          model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
          latency_ms INTEGER, created_at TEXT
        );
        INSERT INTO threads VALUES (
          'thread-legacy', 'u1', 'Legacy chat', 'm1', NULL,
          '2026-08-01T00:00:00+00:00', '2026-08-01T00:00:00+00:00'
        );
        INSERT INTO messages VALUES (
          'message-legacy', 'thread-legacy', 'assistant', 'preserve me',
          'm1', 2, 1, 5, '2026-08-01T00:00:01+00:00'
        );
        """
    )
    conn.close()

    stored = store.get_thread("u1", "thread-legacy")

    assert stored["messages"][0]["content"] == "preserve me"
    assert stored["messages"][0]["request_id"] is None
    assert stored["messages"][0]["sources"] == []
    assert stored["messages"][0]["feedback"] is None
    conn = sqlite3.connect(str(db_path))
    columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    objects = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
        )
    }
    conn.close()
    assert {"request_id", "runtime", "scope_status", "scope_reason_code"} <= columns
    assert {
        "ux_message_request_role",
        "message_sources",
        "message_tool_traces",
        "message_feedback",
    } <= objects


def test_same_request_id_reuses_user_message(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    first = store.append_user_message(thread["id"], "same text", request_id)
    second = store.append_user_message(thread["id"], "same text", request_id)
    assert second["id"] == first["id"]


def test_same_text_with_new_request_id_creates_new_turn(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    first = store.append_user_message(
        thread["id"], "same text", "64d35cd4-9e07-4be8-90a3-683f94c29408"
    )
    second = store.append_user_message(
        thread["id"], "same text", "a61a0778-52d8-4fb6-a430-04a24fa9454c"
    )
    assert second["id"] != first["id"]


def test_complete_turn_hydrates_sources_traces_and_feedback(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)
    assistant = store.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "Use the reset procedure.",
            "runtime": "agent",
            "model": "m1",
            "prompt_tokens": 4,
            "completion_tokens": 3,
            "latency_ms": 9,
            "sources": [{
                "source_id": "manual-1",
                "source_type": "manual",
                "title": "Synthetic Alarm Manual",
                "snippet": "Reset the alarm.",
                "revision": "R2",
                "occurred_at": None,
                "section": "Alarm reset",
                "page": 12,
                "region": None,
                "locator": "manual-1#page=12",
                "figure_id": "fig-manual-1-p12",
                "score": 0.9,
            }],
            "tool_traces": [{
                "tool_name": "search_manuals",
                "query": "alarm reset",
                "result_count": 1,
                "duration_ms": 2,
                "status": "success",
            }],
        },
    )
    store.put_feedback("u1", assistant["id"], {
        "rating": "down",
        "reasons": ["insufficient_evidence"],
        "comment": "Need the newest revision.",
    })
    stored = store.get_thread("u1", thread["id"])["messages"][-1]
    assert stored["sources"][0]["source_id"] == "manual-1"
    # Catches a source field that survives the response but not the reload:
    # complete_turn returns its input, so only a re-read proves the column
    # exists in the INSERT, the SELECT and the table.
    assert stored["sources"][0]["figure_id"] == "fig-manual-1-p12"
    assert stored["feedback"]["rating"] == "down"
    conn = sqlite3.connect(str(tmp_path / "chat.db"))
    trace = conn.execute(
        "SELECT tool_name, query, result_count, duration_ms, status "
        "FROM message_tool_traces WHERE message_id=?",
        (assistant["id"],),
    ).fetchone()
    conn.close()
    assert trace == ("search_manuals", "alarm reset", 1, 2, "success")


def test_scope_decision_is_copied_to_assistant(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)
    decision = {
        "status": "out_of_scope",
        "reason_code": "unsupported_domain",
    }

    user_message = store.set_scope_decision(thread["id"], request_id, decision)
    assistant = store.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "That request is outside the supported scope.",
            "runtime": "scope_rejection",
            "model": "m1",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "latency_ms": 1,
            "sources": [],
            "tool_traces": [],
        },
    )

    assert user_message["scope_status"] == "out_of_scope"
    assert user_message["scope_reason_code"] == "unsupported_domain"
    assert assistant["scope_status"] == "out_of_scope"
    assert assistant["scope_reason_code"] == "unsupported_domain"


def test_complete_turn_is_idempotent_for_same_request(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)
    result = {
        "content": "first answer",
        "runtime": "agent",
        "model": "m1",
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "latency_ms": 1,
        "sources": [],
        "tool_traces": [],
    }

    first = store.complete_turn(thread["id"], request_id, result)
    second = store.complete_turn(
        thread["id"], request_id, {**result, "content": "replacement"}
    )

    assert second["id"] == first["id"]
    assert second["content"] == "first answer"
    assert store.get_message_by_request(
        thread["id"], request_id, "assistant"
    )["id"] == first["id"]


def test_complete_turn_rolls_back_partial_rows(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)

    with pytest.raises(sqlite3.IntegrityError):
        store.complete_turn(
            thread["id"],
            request_id,
            {
                "content": "must roll back",
                "runtime": "agent",
                "model": "m1",
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "latency_ms": 1,
                "sources": [{
                    "source_id": "manual-1",
                    "source_type": None,
                    "title": "Synthetic Alarm Manual",
                    "snippet": "Reset the alarm.",
                    "revision": None,
                    "occurred_at": None,
                    "section": None,
                    "page": None,
                    "region": None,
                    "locator": None,
                    "figure_id": None,
                    "score": None,
                }],
                "tool_traces": [],
            },
        )

    # The reserved row survives, still pending: the UPDATE that would have
    # marked it done is in the same transaction as the citation insert that
    # failed, so the turn stays retryable rather than half-answered.
    assistant = store.get_message_by_request(thread["id"], request_id, "assistant")
    assert assistant["status"] == "pending"
    assert assistant["content"] == ""
    conn = sqlite3.connect(str(tmp_path / "chat.db"))
    source_count = conn.execute("SELECT count(*) FROM message_sources").fetchone()[0]
    conn.close()
    assert source_count == 0


def test_feedback_requires_assistant_ownership(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    user_message = store.append_user_message(thread["id"], "alarm", request_id)
    assistant = store.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "answer",
            "runtime": "rag",
            "model": "m1",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "latency_ms": 1,
            "sources": [],
            "tool_traces": [],
        },
    )
    feedback = {
        "rating": "up",
        "reasons": [],
        "comment": None,
    }

    assert store.put_feedback("u2", assistant["id"], feedback) is None
    assert store.put_feedback("u1", user_message["id"], feedback) is None
    assert store.put_feedback("u1", assistant["id"], feedback)["rating"] == "up"
    assert store.delete_feedback("u2", assistant["id"]) is False
    assert store.get_thread("u1", thread["id"])["messages"][-1]["feedback"] is not None
    assert store.delete_feedback("u1", assistant["id"]) is True
    assert store.get_thread("u1", thread["id"])["messages"][-1]["feedback"] is None


def test_get_owned_message_hides_other_users_and_preserves_role():
    thread = store.create_thread("u1")
    user_message = store.append_user_message(
        thread["id"], "alarm", "64d35cd4-9e07-4be8-90a3-683f94c29408"
    )

    assert store.get_owned_message("u1", user_message["id"])["role"] == "user"
    assert store.get_owned_message("u2", user_message["id"]) is None
    assert store.get_owned_message("u1", "missing") is None


@pytest.mark.parametrize("cleanup", ["delete", "purge"])
def test_thread_cleanup_removes_message_children(monkeypatch, tmp_path, cleanup):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)
    assistant = store.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "answer",
            "runtime": "agent",
            "model": "m1",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "latency_ms": 1,
            "sources": [{
                "source_id": "manual-1",
                "source_type": "manual",
                "title": "Synthetic Alarm Manual",
                "snippet": "Reset the alarm.",
                "revision": None,
                "occurred_at": None,
                "section": None,
                "page": None,
                "region": None,
                "locator": None,
                "figure_id": None,
                "score": None,
            }],
            "tool_traces": [{
                "tool_name": "search_manuals",
                "query": "alarm reset",
                "result_count": 1,
                "duration_ms": 1,
                "status": "success",
            }],
        },
    )
    store.put_feedback("u1", assistant["id"], {
        "rating": "down",
        "reasons": ["wrong_source"],
        "comment": None,
    })

    if cleanup == "delete":
        assert store.delete_thread("u1", thread["id"]) is True
    else:
        old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        conn = sqlite3.connect(str(tmp_path / "chat.db"))
        conn.execute("UPDATE threads SET updated_at=? WHERE id=?", (old, thread["id"]))
        conn.commit()
        conn.close()
        assert store.purge_expired(30) == 1

    conn = sqlite3.connect(str(tmp_path / "chat.db"))
    counts = [
        conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in (
            "message_sources",
            "message_tool_traces",
            "message_feedback",
            "messages",
        )
    ]
    conn.close()
    assert counts == [0, 0, 0, 0]


def test_concurrent_user_replay_returns_winning_message(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    lookups_complete = threading.Barrier(2)
    original_lookup = store._get_message_by_request

    def synchronized_lookup(conn, thread_id, candidate_request_id, role):
        message = original_lookup(conn, thread_id, candidate_request_id, role)
        if role == "user" and message is None:
            lookups_complete.wait(timeout=5)
        return message

    monkeypatch.setattr(store, "_get_message_by_request", synchronized_lookup)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                store.append_user_message, thread["id"], "same text", request_id
            )
            for _ in range(2)
        ]
        messages = [future.result(timeout=5) for future in futures]

    assert messages[0]["id"] == messages[1]["id"]


def test_concurrent_assistant_replay_returns_winning_completion(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)
    lookups_complete = threading.Barrier(2)
    original_lookup = store._get_message_by_request

    def synchronized_lookup(conn, thread_id, candidate_request_id, role):
        message = original_lookup(conn, thread_id, candidate_request_id, role)
        if role == "assistant" and message is None:
            lookups_complete.wait(timeout=5)
        return message

    monkeypatch.setattr(store, "_get_message_by_request", synchronized_lookup)
    result = {
        "content": "answer",
        "runtime": "agent",
        "model": "m1",
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "latency_ms": 1,
        "sources": [],
        "tool_traces": [],
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(store.complete_turn, thread["id"], request_id, result)
            for _ in range(2)
        ]
        messages = [future.result(timeout=5) for future in futures]

    assert messages[0]["id"] == messages[1]["id"]


def test_feedback_write_cannot_outlive_owned_message(monkeypatch, tmp_path):
    db_path = tmp_path / "chat.db"
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(db_path))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)
    assistant = store.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "answer",
            "runtime": "rag",
            "model": "m1",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "latency_ms": 1,
            "sources": [],
            "tool_traces": [],
        },
    )
    ownership_window_open = threading.Event()
    allow_feedback_write = threading.Event()

    class CoordinatedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            normalized = " ".join(sql.split())
            is_feedback_thread = threading.current_thread().name.startswith(
                "feedback-writer"
            )
            is_atomic_upsert = (
                normalized.startswith("INSERT INTO message_feedback")
                and " SELECT " in normalized
            )
            if is_feedback_thread and is_atomic_upsert:
                ownership_window_open.set()
                assert allow_feedback_write.wait(timeout=5)
                return super().execute(sql, parameters)

            is_separate_ownership_read = normalized.startswith(
                "SELECT messages.id FROM messages JOIN threads"
            )
            if is_feedback_thread and is_separate_ownership_read:
                cursor = super().execute(sql, parameters)
                owned_row = cursor.fetchone()
                cursor.close()
                ownership_window_open.set()
                assert allow_feedback_write.wait(timeout=5)

                class BufferedResult:
                    def fetchone(self):
                        return owned_row

                return BufferedResult()
            return super().execute(sql, parameters)

    def coordinated_connect():
        conn = sqlite3.connect(str(db_path), factory=CoordinatedConnection)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(store, "_connect", coordinated_connect)
    feedback = {"rating": "up", "reasons": [], "comment": None}

    with ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="feedback-writer"
    ) as executor:
        future = executor.submit(
            store.put_feedback, "u1", assistant["id"], feedback
        )
        assert ownership_window_open.wait(timeout=5)
        assert store.delete_thread("u1", thread["id"]) is True
        allow_feedback_write.set()
        stored_feedback = future.result(timeout=5)

    assert stored_feedback is None
    conn = sqlite3.connect(str(db_path))
    feedback_count = conn.execute(
        "SELECT count(*) FROM message_feedback"
    ).fetchone()[0]
    conn.close()
    assert feedback_count == 0


def test_complete_turn_persists_rewrite_and_follow_ups(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    user = store.append_user_message(thread["id"], "alarm", request_id)
    store.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "Use the reset procedure.",
            "runtime": "agent",
            "model": "m1",
            "prompt_tokens": 4,
            "completion_tokens": 3,
            "latency_ms": 9,
            "sources": [],
            "tool_traces": [],
            "rewrite": "alarm (알람, alarm recovery)",
            "follow_ups": ["다음 질문", "Next question"],
        },
    )

    stored = store.get_thread("u1", thread["id"])["messages"]
    assert stored[-1]["rewrite"] == "alarm (알람, alarm recovery)"
    assert stored[-1]["follow_ups"] == ["다음 질문", "Next question"]
    # User turns and pre-rewrite runtimes carry the neutral values.
    assert user["rewrite"] is None and user["follow_ups"] == []
    assert stored[0]["follow_ups"] == []


def test_complete_turn_tolerates_a_result_without_the_new_keys(monkeypatch, tmp_path):
    """Direct-runtime results carry neither key; the store must not KeyError."""
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)

    assistant = store.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "pong", "runtime": "rag", "model": "m1",
            "prompt_tokens": 1, "completion_tokens": 1, "latency_ms": 1,
            "sources": [], "tool_traces": [],
        },
    )

    assert assistant["rewrite"] is None
    assert assistant["follow_ups"] == []


def test_existing_db_gains_rewrite_and_follow_up_columns(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    legacy = sqlite3.connect(str(tmp_path / "chat.db"))
    legacy.executescript(
        """
        CREATE TABLE messages (
          id TEXT PRIMARY KEY, thread_id TEXT, role TEXT, content TEXT,
          model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
          latency_ms INTEGER, created_at TEXT
        );
        """
    )
    legacy.commit()
    legacy.close()

    thread = store.create_thread("u1")
    message = store.append_user_message(
        thread["id"], "alarm", "64d35cd4-9e07-4be8-90a3-683f94c29408"
    )

    assert message["follow_ups"] == []
    assert message["rewrite"] is None


# -- turn lifecycle ----------------------------------------------------


def _result(content="답변"):
    return {
        "content": content, "runtime": "rag", "model": None,
        "prompt_tokens": None, "completion_tokens": None, "latency_ms": 12,
        "sources": [], "tool_traces": [], "rewrite": None, "follow_ups": [],
    }


def _started(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = store.create_thread("u1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    store.append_user_message(thread["id"], "alarm", request_id)
    return thread["id"], request_id


def test_only_one_caller_owns_a_turn(monkeypatch, tmp_path):
    """Two POSTs with one request id must not ask the RAG twice.

    ``mine`` is what tells a caller to run the answer, so a second POST that
    also got True would mean two workers, two RAG calls and two bills for one
    question the user asked once.
    """
    thread_id, request_id = _started(monkeypatch, tmp_path)

    first, first_mine = store.begin_turn(thread_id, request_id)
    second, second_mine = store.begin_turn(thread_id, request_id)

    assert first_mine is True
    assert second_mine is False
    assert second["id"] == first["id"]
    assert second["status"] == "pending"


def test_a_reserved_turn_starts_empty_and_carries_the_scope_decision(
    monkeypatch, tmp_path
):
    thread_id, request_id = _started(monkeypatch, tmp_path)
    store.set_scope_decision(
        thread_id,
        request_id,
        {"status": "in_scope", "reason_code": "off_topic_clause_ignored"},
    )

    assistant, _mine = store.begin_turn(thread_id, request_id)

    assert assistant["status"] == "pending"
    assert assistant["content"] == ""
    assert assistant["runtime"] is None
    assert assistant["scope_status"] == "in_scope"


def test_a_failed_turn_is_retaken_in_place(monkeypatch, tmp_path):
    """The SPA's retry reuses the request id, so the row has to be reusable."""
    thread_id, request_id = _started(monkeypatch, tmp_path)
    reserved, _mine = store.begin_turn(thread_id, request_id)
    store.fail_turn(thread_id, request_id, "gateway_timeout", "너무 오래 걸렸습니다")

    failed = store.get_message_by_request(thread_id, request_id, "assistant")
    retaken, mine = store.begin_turn(thread_id, request_id)

    assert failed["status"] == "failed"
    assert failed["error_code"] == "gateway_timeout"
    assert mine is True
    assert retaken["id"] == reserved["id"], "one row per turn, not one per attempt"
    assert retaken["status"] == "pending"
    assert retaken["error_code"] is None


def test_completing_a_settled_turn_changes_nothing(monkeypatch, tmp_path):
    """A worker that finishes after the turn already settled must not overwrite it."""
    thread_id, request_id = _started(monkeypatch, tmp_path)
    store.begin_turn(thread_id, request_id)
    store.complete_turn(thread_id, request_id, _result("첫 답변"))

    again = store.complete_turn(thread_id, request_id, _result("늦은 답변"))

    assert again["content"] == "첫 답변"


def test_failing_a_settled_turn_changes_nothing(monkeypatch, tmp_path):
    thread_id, request_id = _started(monkeypatch, tmp_path)
    store.begin_turn(thread_id, request_id)
    store.complete_turn(thread_id, request_id, _result("답변"))

    after = store.fail_turn(thread_id, request_id, "runtime_unavailable", "늦은 실패")

    assert after["status"] == "done"
    assert after["content"] == "답변"


def test_a_pending_turn_that_outlived_its_budget_reads_as_failed(
    monkeypatch, tmp_path
):
    """The worker died with the turn — a uWSGI restart, a harakiri, a deploy.

    Judged on read rather than swept by a job or a boot hook: ``lazy-apps``
    means each worker boots on its own, so a boot hook would mark another
    worker's in-flight turn as failed.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_TIMEOUT", "60")
    thread_id, request_id = _started(monkeypatch, tmp_path)
    store.begin_turn(thread_id, request_id)

    fresh = store.get_message_by_request(thread_id, request_id, "assistant")
    assert fresh["status"] == "pending"

    long_ago = (
        datetime.now(timezone.utc) - timedelta(seconds=60 + 30 + 5)
    ).isoformat()
    conn = sqlite3.connect(str(tmp_path / "chat.db"))
    with conn:
        conn.execute(
            "UPDATE messages SET created_at=? WHERE request_id=? AND role='assistant'",
            (long_ago, request_id),
        )
    conn.close()

    stale = store.get_message_by_request(thread_id, request_id, "assistant")
    assert stale["status"] == "failed"
    assert stale["error_code"] == "gateway_timeout"


def test_a_late_worker_can_still_land_its_answer(monkeypatch, tmp_path):
    """Staleness is a reading, not a write — the row is still pending.

    Persistence no longer belongs to a request that already returned, so an
    answer that arrives after the reader gave up is saved rather than thrown
    away. The next poll or reload shows it.
    """
    monkeypatch.setenv("SKEWNONO_CHAT_ANSWER_TIMEOUT", "60")
    thread_id, request_id = _started(monkeypatch, tmp_path)
    store.begin_turn(thread_id, request_id)
    long_ago = (datetime.now(timezone.utc) - timedelta(seconds=200)).isoformat()
    conn = sqlite3.connect(str(tmp_path / "chat.db"))
    with conn:
        conn.execute(
            "UPDATE messages SET created_at=? WHERE request_id=? AND role='assistant'",
            (long_ago, request_id),
        )
    conn.close()
    assert store.get_message_by_request(
        thread_id, request_id, "assistant"
    )["status"] == "failed"

    landed = store.complete_turn(thread_id, request_id, _result("늦었지만 도착"))

    assert landed["status"] == "done"
    assert landed["content"] == "늦었지만 도착"


def test_rows_written_before_turns_had_a_lifecycle_read_as_done(
    monkeypatch, tmp_path
):
    """An existing chat.db has no status column; every row in it is finished."""
    db = tmp_path / "chat.db"
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(db))
    legacy = sqlite3.connect(str(db))
    with legacy:
        legacy.executescript(
            """
            CREATE TABLE threads (
              id TEXT PRIMARY KEY, user_id TEXT, title TEXT,
              created_at TEXT, updated_at TEXT
            );
            CREATE TABLE messages (
              id TEXT PRIMARY KEY, thread_id TEXT, role TEXT, content TEXT,
              model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
              latency_ms INTEGER, created_at TEXT
            );
            INSERT INTO threads VALUES ('t1','u1','old','2026-08-01','2026-08-01');
            INSERT INTO messages (id,thread_id,role,content,created_at)
            VALUES ('m1','t1','assistant','옛 답변','2026-08-01T00:00:00+00:00');
            """
        )
    legacy.close()

    thread = store.get_thread("u1", "t1")

    assert thread["messages"][0]["status"] == "done"
    assert thread["messages"][0]["content"] == "옛 답변"
