"""SWAP SURFACE for activity tracking.

Routes, _logging middleware, and the app factory import only this module.
The selected adapter lives in providers/mock.py or providers/office.py.
``seed_demo_users`` is demo seeding and always uses mock.
"""

from back_dev_home._runtime.data_provider import get_data_provider


__all__ = [
    "get_me",
    "get_summary",
    "get_fab_page_usage",
    "get_users_list",
    "get_user_history",
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
    feature: str,
    activity_kind: str,
    fab_name_list: list[str],
) -> None:
    return _provider().record_request(
        user_id,
        feature,
        activity_kind,
        fab_name_list,
    )


def seed_demo_users() -> None:
    # Imported lazily so office mode never loads the mock module.
    from back_dev_home.activity.providers.mock import (
        seed_demo_users as _seed_demo_users,
    )

    _seed_demo_users()
