"""SWAP SURFACE for announcements. Routes import only this module."""

from backend._runtime.data_provider import get_data_provider


__all__ = ["add_announcement", "get_announcements", "list_all", "remove_announcement"]


def _provider():
    if get_data_provider("announcements") == "office":
        from backend.announcements.providers import office
        return office
    from backend.announcements.providers import mock
    return mock


def get_announcements():
    return _provider().get_announcements()


def list_all():
    return _provider().list_all()


def add_announcement(row):
    return _provider().add_announcement(row)


def remove_announcement(announcement_id):
    return _provider().remove_announcement(announcement_id)
