"""SWAP SURFACE — skew-check provider selection.

Routes import only this module. Phase-specific wiring lives in
`providers/mock.py` (fixture) or `providers/office.py` (real stats).
"""

import os
from typing import Literal

from back_dev_home._runtime.env import is_cloud
from back_dev_home.ebeam.hitachi.skew.contracts import SkewCheckPayload
from back_dev_home.ebeam.hitachi.skew.providers import mock, office

ProviderKey = Literal["mock", "office"]


def _provider_key() -> ProviderKey:
    raw = os.environ.get("SKEWNONO_SKEW_PROVIDER", "").strip().lower()
    if raw in {"mock", "office"}:
        return raw  # type: ignore[return-value]
    return "office" if is_cloud() else "mock"


def get_skew_check(
    tool_slug: str,
    fab_id: str,
    recipe_id: str | None,
) -> SkewCheckPayload:
    provider = office if _provider_key() == "office" else mock
    return provider.get_skew_check(tool_slug, fab_id, recipe_id)
