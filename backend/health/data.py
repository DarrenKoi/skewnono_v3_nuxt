"""SWAP SURFACE for health. Routes import only this module."""

from backend._runtime.data_provider import get_data_provider


__all__ = ["get_services_health"]


def _provider():
    if get_data_provider("health") == "office":
        from backend.health.providers import office
        return office
    from backend.health.providers import mock
    return mock


def get_services_health():
    return _provider().get_services_health()
