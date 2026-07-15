"""Office MSR-file adapter hookup point."""


def _not_connected():
    raise NotImplementedError(
        "The msr_file office adapter has not been connected. "
        "Configure the approved MSR source before selecting office mode."
    )


def get_msr_file(*args, **kwargs):
    return _not_connected()


def get_msr_image(*args, **kwargs):
    return _not_connected()
