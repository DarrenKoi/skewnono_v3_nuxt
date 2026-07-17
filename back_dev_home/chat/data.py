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
