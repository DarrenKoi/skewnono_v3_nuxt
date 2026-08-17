"""SWAP SURFACE — tttm-check provider selection.

Routes import only this module. Phase-specific wiring lives in
`providers/mock.py` (fixture) or `providers/office.py` (real stats).
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.tttm.contracts import TttmCheckPayload


def get_tttm_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
    parameter: str | None,
) -> TttmCheckPayload:
    if get_data_provider("tttm") == "office":
        from back_dev_home.ebeam.tttm.providers.office import (
            get_tttm_check as load_tttm_check,
        )
    else:
        from back_dev_home.ebeam.tttm.providers.mock import (
            get_tttm_check as load_tttm_check,
        )

    # Positional and undefaulted, deliberately: office.py is a gitignored COPY
    # of office_example.py, so a copy made before this axis existed would
    # otherwise keep serving 200s computed over every parameter while the UI
    # labelled them with the one the user picked. A TypeError says so instead.
    return load_tttm_check(tool_slug, fab_name, recipe_id, parameter)
