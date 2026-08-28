import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from back_dev_home.chat import data
from back_dev_home.chat.providers import mock


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "mock")


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

    conn = mock._connect()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(message_sources)")}
    conn.close()

    assert "figure_id" in columns


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

    stored = data.get_thread("u1", "thread-legacy")

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
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    first = data.append_user_message(thread["id"], "same text", request_id)
    second = data.append_user_message(thread["id"], "same text", request_id)
    assert second["id"] == first["id"]


def test_same_text_with_new_request_id_creates_new_turn(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = data.create_thread("u1", "m1")
    first = data.append_user_message(
        thread["id"], "same text", "64d35cd4-9e07-4be8-90a3-683f94c29408"
    )
    second = data.append_user_message(
        thread["id"], "same text", "a61a0778-52d8-4fb6-a430-04a24fa9454c"
    )
    assert second["id"] != first["id"]


def test_complete_turn_hydrates_sources_traces_and_feedback(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    data.append_user_message(thread["id"], "alarm", request_id)
    assistant = data.complete_turn(
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
    data.put_feedback("u1", assistant["id"], {
        "rating": "down",
        "reasons": ["insufficient_evidence"],
        "comment": "Need the newest revision.",
    })
    stored = data.get_thread("u1", thread["id"])["messages"][-1]
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
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    data.append_user_message(thread["id"], "alarm", request_id)
    decision = {
        "status": "out_of_scope",
        "reason_code": "unsupported_domain",
        "supported_query": None,
    }

    user_message = data.set_scope_decision(thread["id"], request_id, decision)
    assistant = data.complete_turn(
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
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    data.append_user_message(thread["id"], "alarm", request_id)
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

    first = data.complete_turn(thread["id"], request_id, result)
    second = data.complete_turn(
        thread["id"], request_id, {**result, "content": "replacement"}
    )

    assert second["id"] == first["id"]
    assert second["content"] == "first answer"
    assert data.get_message_by_request(
        thread["id"], request_id, "assistant"
    )["id"] == first["id"]


def test_complete_turn_rolls_back_partial_rows(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    data.append_user_message(thread["id"], "alarm", request_id)

    with pytest.raises(sqlite3.IntegrityError):
        data.complete_turn(
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

    assert data.get_message_by_request(
        thread["id"], request_id, "assistant"
    ) is None
    conn = sqlite3.connect(str(tmp_path / "chat.db"))
    source_count = conn.execute("SELECT count(*) FROM message_sources").fetchone()[0]
    conn.close()
    assert source_count == 0


def test_feedback_requires_assistant_ownership(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    user_message = data.append_user_message(thread["id"], "alarm", request_id)
    assistant = data.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "answer",
            "runtime": "direct",
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

    assert data.put_feedback("u2", assistant["id"], feedback) is None
    assert data.put_feedback("u1", user_message["id"], feedback) is None
    assert data.put_feedback("u1", assistant["id"], feedback)["rating"] == "up"
    assert data.delete_feedback("u2", assistant["id"]) is False
    assert data.get_thread("u1", thread["id"])["messages"][-1]["feedback"] is not None
    assert data.delete_feedback("u1", assistant["id"]) is True
    assert data.get_thread("u1", thread["id"])["messages"][-1]["feedback"] is None


def test_get_owned_message_hides_other_users_and_preserves_role():
    thread = data.create_thread("u1", "m1")
    user_message = data.append_user_message(
        thread["id"], "alarm", "64d35cd4-9e07-4be8-90a3-683f94c29408"
    )

    assert data.get_owned_message("u1", user_message["id"])["role"] == "user"
    assert data.get_owned_message("u2", user_message["id"]) is None
    assert data.get_owned_message("u1", "missing") is None


@pytest.mark.parametrize("cleanup", ["delete", "purge"])
def test_thread_cleanup_removes_message_children(monkeypatch, tmp_path, cleanup):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    data.append_user_message(thread["id"], "alarm", request_id)
    assistant = data.complete_turn(
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
    data.put_feedback("u1", assistant["id"], {
        "rating": "down",
        "reasons": ["wrong_source"],
        "comment": None,
    })

    if cleanup == "delete":
        assert data.delete_thread("u1", thread["id"]) is True
    else:
        old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        conn = sqlite3.connect(str(tmp_path / "chat.db"))
        conn.execute("UPDATE threads SET updated_at=? WHERE id=?", (old, thread["id"]))
        conn.commit()
        conn.close()
        assert data.purge_expired(30) == 1

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
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    lookups_complete = threading.Barrier(2)
    original_lookup = mock._get_message_by_request

    def synchronized_lookup(conn, thread_id, candidate_request_id, role):
        message = original_lookup(conn, thread_id, candidate_request_id, role)
        if role == "user" and message is None:
            lookups_complete.wait(timeout=5)
        return message

    monkeypatch.setattr(mock, "_get_message_by_request", synchronized_lookup)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                data.append_user_message, thread["id"], "same text", request_id
            )
            for _ in range(2)
        ]
        messages = [future.result(timeout=5) for future in futures]

    assert messages[0]["id"] == messages[1]["id"]


def test_concurrent_assistant_replay_returns_winning_completion(monkeypatch, tmp_path):
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    data.append_user_message(thread["id"], "alarm", request_id)
    lookups_complete = threading.Barrier(2)
    original_lookup = mock._get_message_by_request

    def synchronized_lookup(conn, thread_id, candidate_request_id, role):
        message = original_lookup(conn, thread_id, candidate_request_id, role)
        if role == "assistant" and message is None:
            lookups_complete.wait(timeout=5)
        return message

    monkeypatch.setattr(mock, "_get_message_by_request", synchronized_lookup)
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
            executor.submit(data.complete_turn, thread["id"], request_id, result)
            for _ in range(2)
        ]
        messages = [future.result(timeout=5) for future in futures]

    assert messages[0]["id"] == messages[1]["id"]


def test_feedback_write_cannot_outlive_owned_message(monkeypatch, tmp_path):
    db_path = tmp_path / "chat.db"
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(db_path))
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    data.append_user_message(thread["id"], "alarm", request_id)
    assistant = data.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "answer",
            "runtime": "direct",
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

    monkeypatch.setattr(mock, "_connect", coordinated_connect)
    feedback = {"rating": "up", "reasons": [], "comment": None}

    with ThreadPoolExecutor(
        max_workers=1, thread_name_prefix="feedback-writer"
    ) as executor:
        future = executor.submit(
            data.put_feedback, "u1", assistant["id"], feedback
        )
        assert ownership_window_open.wait(timeout=5)
        assert data.delete_thread("u1", thread["id"]) is True
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
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    user = data.append_user_message(thread["id"], "alarm", request_id)
    data.complete_turn(
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

    stored = data.get_thread("u1", thread["id"])["messages"]
    assert stored[-1]["rewrite"] == "alarm (알람, alarm recovery)"
    assert stored[-1]["follow_ups"] == ["다음 질문", "Next question"]
    # User turns and pre-rewrite runtimes carry the neutral values.
    assert user["rewrite"] is None and user["follow_ups"] == []
    assert stored[0]["follow_ups"] == []


def test_complete_turn_tolerates_a_result_without_the_new_keys(monkeypatch, tmp_path):
    """Direct-runtime results carry neither key; the store must not KeyError."""
    monkeypatch.setenv("SKEWNONO_CHAT_DB", str(tmp_path / "chat.db"))
    thread = data.create_thread("u1", "m1")
    request_id = "64d35cd4-9e07-4be8-90a3-683f94c29408"
    data.append_user_message(thread["id"], "alarm", request_id)

    assistant = data.complete_turn(
        thread["id"],
        request_id,
        {
            "content": "pong", "runtime": "direct", "model": "m1",
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

    thread = data.create_thread("u1", "m1")
    message = data.append_user_message(
        thread["id"], "alarm", "64d35cd4-9e07-4be8-90a3-683f94c29408"
    )

    assert message["follow_ups"] == []
    assert message["rewrite"] is None
