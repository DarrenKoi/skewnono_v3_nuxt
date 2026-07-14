"""Resolve the data adapter used by a backend feature.

The deployment location and the data source are separate decisions. In
particular, an office-local Flask process is not a cloud process, but it still
needs real office data.
"""

import os
from typing import Literal, cast


DataProvider = Literal["mock", "office"]

_GLOBAL_ENV = "SKEWNONO_DATA_PROVIDER"
_VALID_PROVIDERS = frozenset({"mock", "office"})


def _feature_env_name(feature: str) -> str:
    normalized = feature.strip().upper().replace("-", "_")
    return f"SKEWNONO_{normalized}_PROVIDER"


def get_data_provider(feature: str) -> DataProvider:
    """Return a feature override, the global provider, or the home-safe default."""
    feature_env = _feature_env_name(feature)
    raw = os.environ.get(feature_env) or os.environ.get(_GLOBAL_ENV) or "mock"
    provider = raw.strip().lower()

    if provider not in _VALID_PROVIDERS:
        raise RuntimeError(
            f"Invalid data provider {raw!r} for {feature!r}. "
            f"Set {feature_env} or {_GLOBAL_ENV} to 'mock' or 'office'."
        )

    return cast(DataProvider, provider)
