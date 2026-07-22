# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office BM/PM adapter — NOT CONNECTED YET.

Source: BM/PM work-order table (past work history + scheduled jobs). Return
the same shape as ``bm_pm/mock.py``'s ``build_bm_pm_data``: a dict with
``past`` rows, ``future`` rows, and derived summary ``cards``; the top-level
``providers/office.py`` dispatcher hands those to
``normalizers.bm_pm_history_payload``. ``anchor`` is the request's ``end``
datetime — past rows are before it, future rows after.
"""

from datetime import datetime


def build_bm_pm_data(eqp_id: str, anchor: datetime) -> dict[str, object]:
    raise NotImplementedError(
        "hardware/bm_pm office adapter not connected yet — implement "
        "build_bm_pm_data against the BM/PM work-order table "
        "(see hardware/MIGRATION.md)."
    )
