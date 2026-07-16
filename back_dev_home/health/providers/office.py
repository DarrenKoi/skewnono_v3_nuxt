"""Office adapter for health — NOT CONNECTED YET.

Implement get_services_health in health/MIGRATION.md against the office
Redis/OpenSearch/MinIO live probes. Normalize results to
health/contracts.py shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The health office adapter has not been connected yet. "
        "Set SKEWNONO_HEALTH_PROVIDER=mock until it is ready."
    )


def get_services_health(*args, **kwargs):
    return _not_connected()
