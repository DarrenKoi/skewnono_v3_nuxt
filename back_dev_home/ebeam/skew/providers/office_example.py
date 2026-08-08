# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office skew provider — wired against real statistics during Phase-2/3 swap."""

from back_dev_home.ebeam.skew.contracts import SkewCheckPayload


def get_skew_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
) -> SkewCheckPayload:
    raise NotImplementedError(
        "office skew provider is wired during the office data swap (Phase-2/3)"
    )