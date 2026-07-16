"""SWAP SURFACE for health. Routes import only this module."""

from back_dev_home._runtime.data_provider import get_data_provider


__all__ = ["get_services_health"]


def _provider():
    if get_data_provider("health") == "office":
        from back_dev_home.health.providers import office
        return office
    from back_dev_home.health.providers import mock
    return mock


def get_services_health():
    return _provider().get_services_health()
