"""SWAP SURFACE for pm_planning. Routes import only this module.

The selected adapter lives in providers/mock.py or providers/office.py.
"""

from back_dev_home._runtime.data_provider import get_data_provider


__all__ = ["get_pm_planning_fleet"]


def _provider():
    if get_data_provider("pm_planning") == "office":
        from back_dev_home.ebeam.hitachi.pm_planning.providers import office
        return office
    from back_dev_home.ebeam.hitachi.pm_planning.providers import mock
    return mock


def get_pm_planning_fleet(fab_name: str):
    return _provider().get_pm_planning_fleet(fab_name)
