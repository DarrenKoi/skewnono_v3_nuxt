"""SWAP SURFACE for admin logs. Routes import only this module."""

from collections.abc import Mapping
from typing import Any

from back_dev_home._runtime.data_provider import get_data_provider


__all__ = ["query_logs"]


def _provider():
    if get_data_provider("admin_logs") == "office":
        from back_dev_home.admin_logs.providers import office
        return office
    from back_dev_home.admin_logs.providers import mock
    return mock


def query_logs(params: Mapping[str, Any]):
    return _provider().query_logs(params)
