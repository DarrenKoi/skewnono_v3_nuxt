"""Thread storage seam. SQLite everywhere — there is no office adapter.

2026-08-28 decision: threads live in SQLite at the office too, so no
``providers/office_example.py`` exists to copy and the registry reports chat as
"no office adapter planned". The dispatcher keeps its shape anyway: it costs
one branch, and it is the seam a future writable store would land on without
touching any caller.

This is a different axis from which provider ANSWERS — that is
``answer/data.py``, keyed on the RAG checkout.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.chat.contracts import (
    Message, Thread, ThreadDetail, ThreadSummary,
)

__all__ = [
    "Message", "Thread", "ThreadDetail", "ThreadSummary",
    "create_thread", "list_threads", "get_thread",
    "rename_thread", "delete_thread", "append_message",
    "get_message_by_request", "get_owned_message", "append_user_message",
    "set_scope_decision", "complete_turn", "put_feedback", "delete_feedback",
    "purge_expired",
]


def _provider():
    if get_data_provider("chat") == "office":
        from back_dev_home.chat.providers import office
        return office
    from back_dev_home.chat.providers import mock
    return mock


def create_thread(user_id):
    return _provider().create_thread(user_id)


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


def get_message_by_request(thread_id, request_id, role):
    return _provider().get_message_by_request(thread_id, request_id, role)


def get_owned_message(user_id, message_id):
    return _provider().get_owned_message(user_id, message_id)


def append_user_message(thread_id, content, request_id):
    return _provider().append_user_message(thread_id, content, request_id)


def set_scope_decision(thread_id, request_id, decision):
    return _provider().set_scope_decision(thread_id, request_id, decision)


def complete_turn(thread_id, request_id, result):
    return _provider().complete_turn(thread_id, request_id, result)


def put_feedback(user_id, message_id, feedback):
    return _provider().put_feedback(user_id, message_id, feedback)


def delete_feedback(user_id, message_id):
    return _provider().delete_feedback(user_id, message_id)


def purge_expired(days=30):
    return _provider().purge_expired(days)
