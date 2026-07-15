"""Office AFM adapter hookup point."""


def _not_connected():
    raise NotImplementedError(
        "The AFM office adapter has not been connected. "
        "Configure the approved AFM data platform before selecting office mode."
    )


def normalize_tool(*args, **kwargs):
    return _not_connected()


def get_tools(*args, **kwargs):
    return _not_connected()


def list_afm_files(*args, **kwargs):
    return _not_connected()


def get_afm_file_detail(*args, **kwargs):
    return _not_connected()


def get_profile_points(*args, **kwargs):
    return _not_connected()


def get_profile_image_svg(*args, **kwargs):
    return _not_connected()


def list_user_activities(*args, **kwargs):
    return _not_connected()


def get_user_analytics(*args, **kwargs):
    return _not_connected()
