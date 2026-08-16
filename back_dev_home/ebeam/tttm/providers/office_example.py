# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office skew provider — wired against real statistics during Phase-2/3 swap."""

from back_dev_home.ebeam.tttm.contracts import TttmCheckPayload


def get_tttm_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
) -> TttmCheckPayload:
    raise NotImplementedError(
        "office skew provider is wired during the office data swap (Phase-2/3)"
    )