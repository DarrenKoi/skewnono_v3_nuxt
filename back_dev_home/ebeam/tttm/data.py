"""SWAP SURFACE — tttm-check provider selection.

Routes import only this module. Phase-specific wiring lives in
`providers/mock.py` (fixture) or `providers/office.py` (real stats).
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.tttm.contracts import TttmCheckPayload, TttmRecipeList


def get_tttm_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
    parameters: tuple[str, ...],
    window_weeks: int,
    eqp_ids: tuple[str, ...],
) -> TttmCheckPayload:
    """`parameters` is the selection — `()` folds every feature of the recipe.

    `eqp_ids` narrows the fleet the comparison is computed over — the tools the
    user picked. `()` means the whole fab fleet, the pre-existing behaviour;
    a non-empty tuple keeps only the requested tools (see
    `contracts.narrow_fleet`). The route folds the repeated `?eqp_id=` key
    into this tuple.
    """
    if get_data_provider("tttm") == "office":
        from back_dev_home.ebeam.tttm.providers.office import (
            get_tttm_check as load_tttm_check,
        )
    else:
        from back_dev_home.ebeam.tttm.providers.mock import (
            get_tttm_check as load_tttm_check,
        )

    # Positional and undefaulted, deliberately: office.py is a gitignored COPY
    # of office_example.py, so a copy made before an axis existed would
    # otherwise keep serving 200s computed over every parameter — or over its
    # own fixed window — while the UI labelled them with what the user picked.
    # A TypeError says so instead. `window_weeks` joined on 2026-08-25; the
    # single `parameter` became the `parameters` tuple on 2026-08-27 (same
    # arity, so a stale copy would NOT raise here — the contract test's
    # `selected_parameters` / `parameter_profile` keys are what catch it);
    # `eqp_ids` joined on 2026-08-28.
    return load_tttm_check(tool_slug, fab_name, recipe_id, parameters, window_weeks, eqp_ids)


def get_tttm_recipes(tool_slug: str, fab_name: str, window_weeks: int) -> TttmRecipeList:
    """The recipes this fab has measured — the picker's source, not the catalogue.

    Separate from `get_tttm_check` on purpose: the picker is fetched once per
    (slug, fab, window) and the check re-runs on every recipe/parameter
    change, so folding the list into the check payload would re-derive it on
    every click. The window is the check's window — a list counted over a
    wider span would offer recipes the check then finds nothing for.
    """
    if get_data_provider("tttm") == "office":
        from back_dev_home.ebeam.tttm.providers.office import (
            get_tttm_recipes as load_tttm_recipes,
        )
    else:
        from back_dev_home.ebeam.tttm.providers.mock import (
            get_tttm_recipes as load_tttm_recipes,
        )

    return load_tttm_recipes(tool_slug, fab_name, window_weeks)
