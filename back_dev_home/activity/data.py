"""SWAP SURFACE for activity tracking.

Routes, _logging middleware, and the app factory import only this module.
The selected adapter lives in providers/mock.py or providers/office.py.
``is_recordable`` is provider-independent policy and lives here.
``seed_demo_users`` is demo seeding and always uses mock.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.activity.providers.mock import (
    is_recordable,       # pure predicate: same rule in both modes
    seed_demo_users,     # dev/demo seeding: mock-only by design
)


__all__ = [
    "get_me",
    "get_summary",
    "get_fab_page_usage",
    "get_users_list",
    "get_user_history",
    "is_recordable",
    "record_request",
    "seed_demo_users",
]


def _provider():
    if get_data_provider("activity") == "office":
        from back_dev_home.activity.providers import office
        return office
    from back_dev_home.activity.providers import mock
    return mock


def get_me(user_id: str):
    return _provider().get_me(user_id)


def get_summary():
    return _provider().get_summary()


def get_fab_page_usage():
    return _provider().get_fab_page_usage()


def get_users_list():
    return _provider().get_users_list()


def get_user_history(user_id: str):
    return _provider().get_user_history(user_id)


def record_request(
    user_id: str,
    method: str,
    path: str,
    status: int,
    feature: str,
) -> None:
    return _provider().record_request(user_id, method, path, status, feature)
