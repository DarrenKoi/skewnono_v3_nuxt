# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office adapter for announcements — NOT CONNECTED YET.

Implement get_announcements in announcements/MIGRATION.md against the
office operator-announcement source. Normalize results to
announcements/contracts.py shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The announcements office adapter has not been connected yet. "
        "Set SKEWNONO_ANNOUNCEMENTS_PROVIDER=mock until it is ready."
    )


def get_announcements(*args, **kwargs):
    return _not_connected()