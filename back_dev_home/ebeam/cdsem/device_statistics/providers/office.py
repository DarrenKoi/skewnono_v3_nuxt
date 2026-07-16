"""Office adapter for cdsem device_statistics — NOT CONNECTED YET.

Implement every function listed in device_statistics/MIGRATION.md against
the office data source. Normalize results to device_statistics/contracts.py
shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The device_statistics office adapter has not been connected yet. "
        "Set SKEWNONO_DEVICE_STATISTICS_PROVIDER=mock until it is ready."
    )


def get_r3_device_grp(*args, **kwargs):
    return _not_connected()


def get_device_desc(*args, **kwargs):
    return _not_connected()


def get_recipe_params(*args, **kwargs):
    return _not_connected()


def get_weekly_trend_data(*args, **kwargs):
    return _not_connected()


def get_rules(*args, **kwargs):
    return _not_connected()
