"""Office fail-issue adapter hookup point."""


def _not_connected():
    raise NotImplementedError(
        "The fail_issue office adapter has not been connected. "
        "Configure the approved measurement-history source before selecting office mode."
    )


def get_anchor_time(*args, **kwargs):
    return _not_connected()


def get_summary(*args, **kwargs):
    return _not_connected()


def get_daily_trend(*args, **kwargs):
    return _not_connected()


def get_align_ranking(*args, **kwargs):
    return _not_connected()


def get_meas_ranking(*args, **kwargs):
    return _not_connected()


def get_devices(*args, **kwargs):
    return _not_connected()
