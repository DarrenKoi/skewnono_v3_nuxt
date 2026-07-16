"""SWAP SURFACE for cdsem device_statistics.

Routes and other features import only this module. The selected adapter
lives in providers/mock.py or providers/office.py.

`_lot_index` and `BASE_TIME` are intentionally NOT exposed here.
`recipe_tat`'s mock provider imports `_lot_index` directly from
`providers.mock` (mock fixtures interlocking with mock fixtures) so that
office mode for device_statistics never breaks recipe_tat's mock — routing
that import through this switch would defeat the point.
"""

from back_dev_home._runtime.data_provider import get_data_provider


__all__ = [
    "get_r3_device_grp",
    "get_device_desc",
    "get_recipe_params",
    "get_weekly_trend_data",
    "get_rules",
]


def _provider():
    if get_data_provider("device_statistics") == "office":
        from back_dev_home.ebeam.cdsem.device_statistics.providers import office
        return office
    from back_dev_home.ebeam.cdsem.device_statistics.providers import mock
    return mock


def get_r3_device_grp():
    return _provider().get_r3_device_grp()


def get_device_desc(fac_ids: list[str] | None = None):
    return _provider().get_device_desc(fac_ids)


def get_recipe_params(lot_cds: list[str] | None = None):
    return _provider().get_recipe_params(lot_cds)


def get_weekly_trend_data(
    lot_cds: list[str] | None = None,
    points: int = 8,
    interval_days: int = 7,
    include_recipes: bool = True,
):
    return _provider().get_weekly_trend_data(lot_cds, points, interval_days, include_recipes)


def get_rules(fab: str):
    return _provider().get_rules(fab)
