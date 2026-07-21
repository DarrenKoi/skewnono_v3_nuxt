"""Resolve the data adapter used by a backend feature.

The deployment location and the data source are separate decisions. In
particular, an office-local Flask process is not a cloud process, but it still
needs real office data.

Resolution order (first hit wins):

1. ``SKEWNONO_<FEATURE>_PROVIDER`` — explicit per-feature override.
2. ``SKEWNONO_DATA_PROVIDER``      — explicit global override.
3. Site auto-default — on a recognized office machine (see ``site.py``),
   features in ``site.OFFICE_READY`` default to ``office``.
4. ``mock`` — the home-safe default everywhere else.
"""

import os
from typing import Literal, cast

from back_dev_home._runtime.site import OFFICE_READY, detect_site


DataProvider = Literal["mock", "office"]

_GLOBAL_ENV = "SKEWNONO_DATA_PROVIDER"
_VALID_PROVIDERS = frozenset({"mock", "office"})


def _feature_env_name(feature: str) -> str:
    normalized = feature.strip().upper().replace("-", "_")
    return f"SKEWNONO_{normalized}_PROVIDER"


def get_data_provider(feature: str) -> DataProvider:
    """Return a feature override, the global provider, or the site default."""
    feature_env = _feature_env_name(feature)
    raw = os.environ.get(feature_env) or os.environ.get(_GLOBAL_ENV)
    if raw is None:
        if detect_site() == "office" and feature.strip().lower() in OFFICE_READY:
            return "office"
        return "mock"
    provider = raw.strip().lower()

    if provider not in _VALID_PROVIDERS:
        raise RuntimeError(
            f"Invalid data provider {raw!r} for {feature!r}. "
            f"Set {feature_env} or {_GLOBAL_ENV} to 'mock' or 'office'."
        )

    return cast(DataProvider, provider)
