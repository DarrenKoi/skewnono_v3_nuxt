# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office Recipe-TAT adapter hookup point."""


def _not_connected():
    raise NotImplementedError(
        "The recipe_tat office adapter has not been connected. "
        "Configure the approved measurement-history source before selecting office mode."
    )


def get_anchor_time(*args, **kwargs):
    return _not_connected()


def get_meas_hist(*args, **kwargs):
    return _not_connected()


def get_ranking(*args, **kwargs):
    return _not_connected()


def get_summary(*args, **kwargs):
    return _not_connected()


def get_daily_trend(*args, **kwargs):
    return _not_connected()


def get_devices(*args, **kwargs):
    return _not_connected()