"""SWAP SURFACE — skew-check provider selection.

Routes import only this module. Phase-specific wiring lives in
`providers/mock.py` (fixture) or `providers/office.py` (real stats).
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.ebeam.hitachi.skew.contracts import SkewCheckPayload


def get_skew_check(
    tool_slug: str,
    fab_name: str,
    recipe_id: str | None,
) -> SkewCheckPayload:
    if get_data_provider("skew") == "office":
        from back_dev_home.ebeam.hitachi.skew.providers.office import (
            get_skew_check as load_skew_check,
        )
    else:
        from back_dev_home.ebeam.hitachi.skew.providers.mock import (
            get_skew_check as load_skew_check,
        )

    return load_skew_check(tool_slug, fab_name, recipe_id)
