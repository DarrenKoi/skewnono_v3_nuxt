# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office measurement-history adapter hookup point."""


def _not_connected():
    raise NotImplementedError(
        "The meas_hist office adapter has not been connected. "
        "Configure the approved OpenSearch source before selecting office mode."
    )


def get_meas_hist(*args, **kwargs):
    return _not_connected()


def find_meas_hist_by_msr(*args, **kwargs):
    return _not_connected()


def search_meas_hist(*args, **kwargs):
    return _not_connected()


def get_meas_hist_facets(*args, **kwargs):
    return _not_connected()