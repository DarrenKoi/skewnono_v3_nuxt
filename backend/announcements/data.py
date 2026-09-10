"""SWAP SURFACE for announcements. Routes import only this module."""

from backend._runtime.data_provider import get_data_provider


__all__ = ["get_announcements"]


def _provider():
    if get_data_provider("announcements") == "office":
        from backend.announcements.providers import office
        return office
    from backend.announcements.providers import mock
    return mock


def get_announcements():
    return _provider().get_announcements()
