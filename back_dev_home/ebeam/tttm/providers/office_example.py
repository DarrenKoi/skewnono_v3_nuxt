# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office skew provider — wired against real statistics during Phase-2/3 swap."""

from back_dev_home.ebeam.tttm.contracts import TttmCheckPayload


def get_tttm_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
    parameter: str | None,
) -> TttmCheckPayload:
    # `parameter` narrows the MSR rows the pairwise skew is computed from to one
    # measured feature of `recipe_id`, and is None only when the caller wants
    # every feature folded together. It is never meaningful on its own — the
    # route refuses it without a recipe — so the adapter may assume that when
    # `parameter` is set, `recipe_id` is too.
    #
    # Echo BOTH back on the payload, including on the unavailable branch. The
    # client files the response under the pair it asked for, so an adapter that
    # dropped either key would label one feature's group with another's name.
    raise NotImplementedError(
        "office skew provider is wired during the office data swap (Phase-2/3)"
    )