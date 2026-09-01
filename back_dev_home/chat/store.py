"""Chat thread store: SQLite, at home and at the office alike.

There is no provider seam here and no dispatcher above it — the
2026-08-28 decision was that threads live in SQLite at the office too, so
a ``providers/`` directory with one adapter in it was a swap surface that
could never swap. Callers import this module directly.

That absence is also why ``chat`` no longer appears in the provider boot
table: the registry lists features by ``providers/mock.py``, and chat has
none. Which provider ANSWERS is a different question, on a different axis
— ``answer/data.py``, keyed on the RAG checkout — and the boot log prints
that one as its own ``chat/answer`` row.

Survives restart; queryable 30-day archive.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


_MESSAGE_COLUMNS = (
    "id,thread_id,request_id,role,content,model,runtime,scope_status,"
    "scope_reason_code,prompt_tokens,completion_tokens,latency_ms,created_at,"
    "rewrite,follow_ups_json,status,error_code,error_message"
)

# How long past the turn budget a `pending` row may sit before a reader stops
# believing in it. The worker enforces no deadline of its own (the RAG raises
# TimeoutError on its budget), so a row still pending well past the budget
# means the worker died with it — a uWSGI restart, a harakiri, a deploy. The
# slack keeps clock jitter and a slow final write from flipping a turn that is
# about to land.
_STALE_SLACK_SECONDS = 30


def _db_path() -> str:
    override = os.environ.get("SKEWNONO_CHAT_DB")
    if override:
        return override
    return str(Path(__file__).resolve().parent / "chat.db")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_column(
    conn: sqlite3.Connection, table: str, column_name: str, declaration: str
) -> None:
    """Additively migrate an existing chat.db — CREATE TABLE IF NOT EXISTS
    never revisits a table that already exists, so a column added to the DDL
    alone would be missing from every database created before it."""
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {declaration}")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    # A turn is now written by a background thread while the SPA polls this
    # same file every two seconds, and uWSGI runs four such processes. WAL is
    # what stops a write from blocking those reads. Failure is swallowed on
    # purpose: WAL needs shared memory the filesystem may not offer (a network
    # mount is the known case), and the rollback journal is still correct
    # there — only slower. A chat store that refuses to open would be a far
    # worse outcome than one that serializes.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS threads (
          id TEXT PRIMARY KEY, user_id TEXT, title TEXT,
          created_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
          id TEXT PRIMARY KEY, thread_id TEXT, role TEXT, content TEXT,
          model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
          latency_ms INTEGER, created_at TEXT
        );
        """
    )
    with conn:
        _ensure_column(conn, "messages", "request_id", "TEXT")
        _ensure_column(conn, "messages", "runtime", "TEXT")
        _ensure_column(conn, "messages", "scope_status", "TEXT")
        _ensure_column(conn, "messages", "scope_reason_code", "TEXT")
        _ensure_column(conn, "messages", "rewrite", "TEXT")
        _ensure_column(conn, "messages", "follow_ups_json", "TEXT")
        # DEFAULT 'done' backfills every row written before turns had a
        # lifecycle: they are all finished, by definition. Only assistant rows
        # carry meaning here — a user row is done the moment it exists.
        _ensure_column(conn, "messages", "status", "TEXT DEFAULT 'done'")
        _ensure_column(conn, "messages", "error_code", "TEXT")
        _ensure_column(conn, "messages", "error_message", "TEXT")
        conn.executescript(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_message_request_role
            ON messages(thread_id, request_id, role)
            WHERE request_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS message_sources (
              message_id TEXT NOT NULL,
              position INTEGER NOT NULL,
              source_id TEXT NOT NULL,
              source_type TEXT NOT NULL,
              title TEXT NOT NULL,
              snippet TEXT NOT NULL,
              revision TEXT,
              occurred_at TEXT,
              section TEXT,
              page INTEGER,
              region TEXT,
              locator TEXT,
              figure_id TEXT,
              score REAL,
              PRIMARY KEY (message_id, position)
            );

            CREATE TABLE IF NOT EXISTS message_tool_traces (
              message_id TEXT NOT NULL,
              position INTEGER NOT NULL,
              tool_name TEXT NOT NULL,
              query TEXT NOT NULL,
              result_count INTEGER NOT NULL,
              duration_ms INTEGER NOT NULL,
              status TEXT NOT NULL,
              PRIMARY KEY (message_id, position)
            );

            CREATE TABLE IF NOT EXISTS message_feedback (
              message_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              rating TEXT NOT NULL,
              reasons_json TEXT NOT NULL,
              comment TEXT,
              updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(conn, "message_sources", "figure_id", "TEXT")
    return conn


def _stale_pending(message: dict) -> bool:
    """Whether a pending turn has outlived the worker that was to finish it.

    Judged on read rather than swept by a job: the state is a function of
    ``created_at`` and the budget, so computing it needs no scheduler entry and
    no boot hook. A boot hook would be actively wrong — ``lazy-apps`` means
    each uWSGI worker boots on its own, so worker 4 starting up would mark
    worker 1's in-flight turn as failed.
    """
    if message.get("status") != "pending":
        return False
    from back_dev_home.chat.config import get_answer_timeout

    try:
        started = datetime.fromisoformat(message["created_at"])
    except (TypeError, ValueError):
        return False
    age = (datetime.now(timezone.utc) - started).total_seconds()
    return age > get_answer_timeout() + _STALE_SLACK_SECONDS


def _hydrate_message(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    message = dict(row)
    message["follow_ups"] = json.loads(message.pop("follow_ups_json") or "[]")
    if _stale_pending(message):
        message["status"] = "failed"
        message["error_code"] = "gateway_timeout"
        message["error_message"] = (
            "답변을 만들던 작업이 응답하지 않았습니다. 다시 시도해 주세요."
        )
    source_rows = conn.execute(
        "SELECT source_id,source_type,title,snippet,revision,occurred_at,section,"
        "page,region,locator,figure_id,score FROM message_sources "
        "WHERE message_id=? ORDER BY position ASC",
        (message["id"],),
    ).fetchall()
    feedback_row = conn.execute(
        "SELECT rating,reasons_json,comment,updated_at FROM message_feedback "
        "WHERE message_id=?",
        (message["id"],),
    ).fetchone()
    message["sources"] = [dict(source) for source in source_rows]
    message["feedback"] = None
    if feedback_row is not None:
        message["feedback"] = {
            "rating": feedback_row["rating"],
            "reasons": json.loads(feedback_row["reasons_json"]),
            "comment": feedback_row["comment"],
            "updated_at": feedback_row["updated_at"],
        }
    return message


def _get_message_by_request(
    conn: sqlite3.Connection, thread_id: str, request_id: str, role: str
) -> dict | None:
    row = conn.execute(
        f"SELECT {_MESSAGE_COLUMNS} FROM messages "
        "WHERE thread_id=? AND request_id=? AND role=?",
        (thread_id, request_id, role),
    ).fetchone()
    if row is None:
        return None
    return _hydrate_message(conn, row)


def _delete_message_children(conn: sqlite3.Connection, message_ids: list[str]) -> None:
    if not message_ids:
        return
    placeholders = ",".join("?" for _ in message_ids)
    for table in ("message_sources", "message_tool_traces", "message_feedback"):
        conn.execute(
            f"DELETE FROM {table} WHERE message_id IN ({placeholders})",
            message_ids,
        )


def create_thread(user_id):
    tid = uuid.uuid4().hex
    now = _now()
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO threads (id,user_id,title,created_at,updated_at)"
            " VALUES (?,?,?,?,?)",
            (tid, user_id, "New chat", now, now),
        )
    conn.close()
    return {
        "id": tid, "user_id": user_id, "title": "New chat",
        "created_at": now, "updated_at": now,
    }


def list_threads(user_id):
    conn = _connect()
    rows = conn.execute(
        "SELECT id,title,updated_at FROM threads WHERE user_id=? "
        "ORDER BY updated_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_thread(user_id, thread_id):
    conn = _connect()
    thread_row = conn.execute(
        # Explicit columns, not *: an older chat.db still carries the model and
        # system_prompt columns this app no longer owns (the RAG does), and
        # SELECT * would put them back in the payload on those machines alone.
        "SELECT id,user_id,title,created_at,updated_at FROM threads "
        "WHERE id=? AND user_id=?",
        (thread_id, user_id),
    ).fetchone()
    if thread_row is None:
        conn.close()
        return None
    message_rows = conn.execute(
        f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE thread_id=? "
        "ORDER BY created_at ASC, rowid ASC",
        (thread_id,),
    ).fetchall()
    thread = dict(thread_row)
    thread["messages"] = [
        _hydrate_message(conn, message_row) for message_row in message_rows
    ]
    conn.close()
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
        owned_thread = conn.execute(
            "SELECT id FROM threads WHERE id=? AND user_id=?", (thread_id, user_id)
        ).fetchone()
        if owned_thread is None:
            changed = False
        else:
            message_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM messages WHERE thread_id=?", (thread_id,)
                )
            ]
            _delete_message_children(conn, message_ids)
            conn.execute("DELETE FROM messages WHERE thread_id=?", (thread_id,))
            conn.execute("DELETE FROM threads WHERE id=?", (thread_id,))
            changed = True
    conn.close()
    return changed


def append_message(thread_id, role, content, meta=None):
    meta = meta or {}
    mid = uuid.uuid4().hex
    now = _now()
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO messages (id,thread_id,request_id,role,content,model,runtime,"
            "scope_status,scope_reason_code,prompt_tokens,completion_tokens,latency_ms,"
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                mid, thread_id, meta.get("request_id"), role, content,
                meta.get("model"), meta.get("runtime"), meta.get("scope_status"),
                meta.get("scope_reason_code"), meta.get("prompt_tokens"),
                meta.get("completion_tokens"), meta.get("latency_ms"), now,
            ),
        )
        conn.execute("UPDATE threads SET updated_at=? WHERE id=?", (now, thread_id))
    row = conn.execute(
        f"SELECT {_MESSAGE_COLUMNS} FROM messages WHERE id=?", (mid,)
    ).fetchone()
    message = _hydrate_message(conn, row)
    conn.close()
    return message


def get_message_by_request(thread_id, request_id, role):
    conn = _connect()
    message = _get_message_by_request(conn, thread_id, request_id, role)
    conn.close()
    return message


def get_owned_message(user_id, message_id):
    conn = _connect()
    row = conn.execute(
        f"SELECT {_MESSAGE_COLUMNS} FROM messages "
        "WHERE id=? AND thread_id IN (SELECT id FROM threads WHERE user_id=?)",
        (message_id, user_id),
    ).fetchone()
    message = None if row is None else _hydrate_message(conn, row)
    conn.close()
    return message


def append_user_message(thread_id, content, request_id):
    conn = _connect()
    existing = _get_message_by_request(conn, thread_id, request_id, "user")
    if existing is not None:
        conn.close()
        return existing
    message_id = uuid.uuid4().hex
    now = _now()
    with conn:
        cur = conn.execute(
            "INSERT INTO messages (id,thread_id,request_id,role,content,created_at) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(thread_id,request_id,role) "
            "WHERE request_id IS NOT NULL DO NOTHING",
            (message_id, thread_id, request_id, "user", content, now),
        )
        if cur.rowcount > 0:
            conn.execute("UPDATE threads SET updated_at=? WHERE id=?", (now, thread_id))
    message = _get_message_by_request(conn, thread_id, request_id, "user")
    conn.close()
    return message


def set_scope_decision(thread_id, request_id, decision):
    conn = _connect()
    with conn:
        conn.execute(
            "UPDATE messages SET scope_status=?, scope_reason_code=? "
            "WHERE thread_id=? AND request_id=? AND role='user'",
            (
                decision["status"], decision["reason_code"], thread_id, request_id,
            ),
        )
    message = _get_message_by_request(conn, thread_id, request_id, "user")
    conn.close()
    return message


def begin_turn(thread_id, request_id):
    """Reserve the assistant row for this turn and say who owns it.

    Returns ``(message, mine)``. ``mine`` is True only for the caller that
    actually moved the row into ``pending`` — that caller runs the answer.
    Everyone else gets the row as it stands and runs nothing, which is what
    makes a retried POST join the turn already in flight instead of asking
    the RAG the same question twice.

    A ``failed`` turn is retried in place. The SPA's retry reuses the same
    ``request_id`` (MIGRATION.md: a retry keeps the UUID, a new question gets
    a new one), so refusing here would leave the retry button doing nothing.

    ``created_at`` is set when the turn STARTS, not when it finishes: it is
    what the elapsed-time display counts from, and what
    :func:`_stale_pending` measures. It doubles as the compare-and-set token
    on a retake, so two workers cannot both claim the same failed turn.
    """
    conn = _connect()
    try:
        now = _now()
        existing = _get_message_by_request(conn, thread_id, request_id, "assistant")
        if existing is not None:
            if existing["status"] != "failed":
                return existing, False
            with conn:
                cur = conn.execute(
                    "UPDATE messages SET status='pending', error_code=NULL, "
                    "error_message=NULL, content='', created_at=? "
                    "WHERE id=? AND created_at=?",
                    (now, existing["id"], existing["created_at"]),
                )
            mine = cur.rowcount > 0
            return _get_message_by_request(
                conn, thread_id, request_id, "assistant"
            ), mine

        scope = conn.execute(
            "SELECT scope_status,scope_reason_code FROM messages "
            "WHERE thread_id=? AND request_id=? AND role='user'",
            (thread_id, request_id),
        ).fetchone()
        with conn:
            cur = conn.execute(
                "INSERT INTO messages (id,thread_id,request_id,role,content,"
                "scope_status,scope_reason_code,created_at,status) "
                "VALUES (?,?,?,'assistant','',?,?,?,'pending') "
                "ON CONFLICT(thread_id,request_id,role) "
                "WHERE request_id IS NOT NULL DO NOTHING",
                (
                    uuid.uuid4().hex, thread_id, request_id,
                    scope["scope_status"] if scope is not None else None,
                    scope["scope_reason_code"] if scope is not None else None,
                    now,
                ),
            )
            if cur.rowcount > 0:
                conn.execute(
                    "UPDATE threads SET updated_at=? WHERE id=?", (now, thread_id)
                )
        mine = cur.rowcount > 0
        return _get_message_by_request(conn, thread_id, request_id, "assistant"), mine
    finally:
        conn.close()


def complete_turn(thread_id, request_id, result):
    """Fill in the reserved row with the answer. No-op once it is not pending.

    Reserves the row itself when nobody did, so the function stays a plain
    upsert: a caller that has an answer and no reservation (a turn settled
    without a worker, a row purged mid-flight) still lands it.
    """
    if get_message_by_request(thread_id, request_id, "assistant") is None:
        begin_turn(thread_id, request_id)
    conn = _connect()
    try:
        row = _get_message_by_request(conn, thread_id, request_id, "assistant")
        if row is None or row["status"] == "done":
            return row
        now = _now()
        message_id = row["id"]
        with conn:
            cur = conn.execute(
                "UPDATE messages SET content=?, model=?, runtime=?, prompt_tokens=?, "
                "completion_tokens=?, latency_ms=?, rewrite=?, follow_ups_json=?, "
                "status='done', error_code=NULL, error_message=NULL "
                "WHERE id=? AND status='pending'",
                (
                    result["content"], result["model"], result["runtime"],
                    result["prompt_tokens"], result["completion_tokens"],
                    result["latency_ms"], result.get("rewrite"),
                    json.dumps(list(result.get("follow_ups") or []), ensure_ascii=False),
                    message_id,
                ),
            )
            if cur.rowcount > 0:
                # Children are written only by the winner, so a late second
                # writer cannot double the citations under one message.
                for position, source in enumerate(result["sources"]):
                    conn.execute(
                        "INSERT INTO message_sources (message_id,position,source_id,"
                        "source_type,title,snippet,revision,occurred_at,section,page,region,"
                        "locator,figure_id,score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            message_id, position, source["source_id"],
                            source["source_type"], source["title"], source["snippet"],
                            source["revision"], source["occurred_at"], source["section"],
                            source["page"], source["region"], source["locator"],
                            source["figure_id"], source["score"],
                        ),
                    )
                for position, trace in enumerate(result["tool_traces"]):
                    conn.execute(
                        "INSERT INTO message_tool_traces "
                        "(message_id,position,tool_name,query,result_count,duration_ms,"
                        "status) VALUES (?,?,?,?,?,?,?)",
                        (
                            message_id, position, trace["tool_name"], trace["query"],
                            trace["result_count"], trace["duration_ms"], trace["status"],
                        ),
                    )
                conn.execute(
                    "UPDATE threads SET updated_at=? WHERE id=?", (now, thread_id)
                )
        return _get_message_by_request(conn, thread_id, request_id, "assistant")
    finally:
        conn.close()


def fail_turn(thread_id, request_id, error_code, error_message):
    """Record why the turn produced no answer, on the row it reserved.

    A failure is NOT stored as an assistant answer whose content happens to be
    an error sentence: the 30-day archive and the conversation index would
    then count it as a turn the RAG answered. ``error_code`` is the same
    string ``routes.py`` puts in an error body, so the SPA reads one
    vocabulary whether the failure arrived synchronously or through a poll.
    """
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "UPDATE messages SET status='failed', error_code=?, error_message=? "
                "WHERE thread_id=? AND request_id=? AND role='assistant' "
                "AND status='pending'",
                (error_code, error_message, thread_id, request_id),
            )
        return _get_message_by_request(conn, thread_id, request_id, "assistant")
    finally:
        conn.close()


def put_feedback(user_id, message_id, feedback):
    conn = _connect()
    updated_at = _now()
    reasons_json = json.dumps(feedback["reasons"], ensure_ascii=False)
    with conn:
        cur = conn.execute(
            "INSERT INTO message_feedback "
            "(message_id,user_id,rating,reasons_json,comment,updated_at) "
            "SELECT ?,?,?,?,?,? FROM messages JOIN threads "
            "ON threads.id=messages.thread_id "
            "WHERE messages.id=? AND messages.role='assistant' AND threads.user_id=? "
            "ON CONFLICT(message_id) DO UPDATE SET "
            "user_id=excluded.user_id,rating=excluded.rating,"
            "reasons_json=excluded.reasons_json,comment=excluded.comment,"
            "updated_at=excluded.updated_at",
            (
                message_id, user_id, feedback["rating"], reasons_json,
                feedback.get("comment"), updated_at, message_id, user_id,
            ),
        )
    stored = cur.rowcount > 0
    conn.close()
    if not stored:
        return None
    return {
        "rating": feedback["rating"],
        "reasons": feedback["reasons"],
        "comment": feedback.get("comment"),
        "updated_at": updated_at,
    }


def delete_feedback(user_id, message_id):
    conn = _connect()
    with conn:
        cur = conn.execute(
            "DELETE FROM message_feedback WHERE message_id IN ("
            "SELECT messages.id FROM messages JOIN threads "
            "ON threads.id=messages.thread_id "
            "WHERE messages.id=? AND messages.role='assistant' AND threads.user_id=?"
            ")",
            (message_id, user_id),
        )
    changed = cur.rowcount > 0
    conn.close()
    return changed


def purge_expired(days=30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = _connect()
    with conn:
        thread_ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM threads WHERE updated_at < ?", (cutoff,)
            )
        ]
        if thread_ids:
            placeholders = ",".join("?" for _ in thread_ids)
            message_ids = [
                row["id"]
                for row in conn.execute(
                    f"SELECT id FROM messages WHERE thread_id IN ({placeholders})",
                    thread_ids,
                )
            ]
            _delete_message_children(conn, message_ids)
            conn.execute(
                f"DELETE FROM messages WHERE thread_id IN ({placeholders})", thread_ids
            )
        cur = conn.execute("DELETE FROM threads WHERE updated_at < ?", (cutoff,))
    removed = cur.rowcount
    conn.close()
    return removed
