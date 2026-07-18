# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office adapter for activity tracking — NOT CONNECTED YET.

Implement every function listed in activity/MIGRATION.md against the office
OpenSearch activity index. Normalize results to activity/contracts.py shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The activity office adapter has not been connected yet. "
        "Set SKEWNONO_ACTIVITY_PROVIDER=mock until it is ready."
    )


def get_me(user_id):
    return _not_connected()


def get_summary():
    return _not_connected()


def get_fab_page_usage():
    return _not_connected()


def get_users_list():
    return _not_connected()


def get_user_history(user_id):
    return _not_connected()


def record_request(*args, **kwargs):
    return _not_connected()