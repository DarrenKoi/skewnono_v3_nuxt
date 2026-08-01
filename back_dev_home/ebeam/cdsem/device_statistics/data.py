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
    "write_weekly_snapshot",
    "sweep_weekly_snapshots",
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


def get_rules(fac_id: str):
    return _provider().get_rules(fac_id)


# ── 스케줄러 진입점 ──────────────────────────────────────────────
# 읽기가 아니라 쓰기입니다. 스케줄러가 provider 를 직접 import 하지 않도록
# 여기를 통과시킵니다 — 직접 import 하면 이 dispatcher 가 존재하는 이유인
# home/office swap 을 하드코딩하게 됩니다.


def write_weekly_snapshot(date_key: str | None = None) -> str:
    """이번(또는 지정된) 주차 스냅샷을 적재하고 그 위치를 돌려줍니다."""
    return _provider().write_weekly_snapshot(date_key)


def sweep_weekly_snapshots(keep_weeks: int = 12) -> int:
    """가장 최근 ``keep_weeks`` 주차만 남기고 지웁니다. 지운 개수를 돌려줍니다."""
    return _provider().sweep_weekly_snapshots(keep_weeks)
