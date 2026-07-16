"""SWAP SURFACE for announcements. Routes import only this module."""

from back_dev_home._runtime.data_provider import get_data_provider


__all__ = ["get_announcements"]


def _provider():
    if get_data_provider("announcements") == "office":
        from back_dev_home.announcements.providers import office
        return office
    from back_dev_home.announcements.providers import mock
    return mock


def get_announcements():
    return _provider().get_announcements()
