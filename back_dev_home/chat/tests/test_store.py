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
