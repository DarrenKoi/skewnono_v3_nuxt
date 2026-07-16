"""Office adapter for admin_logs — NOT CONNECTED YET.

Implement query_logs in admin_logs/MIGRATION.md against the office
OpenSearch logging index. Normalize results to admin_logs/contracts.py
shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The admin_logs office adapter has not been connected yet. "
        "Set SKEWNONO_ADMIN_LOGS_PROVIDER=mock until it is ready."
    )


def query_logs(*args, **kwargs):
    return _not_connected()
