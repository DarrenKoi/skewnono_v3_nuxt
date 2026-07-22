"""Resolve the data adapter used by a backend feature.

Two decisions, deliberately kept independent:

* **mode** — a property of the machine. Are we at the office? Comes from
  ``SKEWNONO_DATA_PROVIDER`` when set, else from ``site.detect_site()``.
* **readiness** — a property of the filesystem. Does this feature have a
  ``providers/office.py``? Comes from ``office_registry``.

A feature serves office data when both are true. Resolution order:

1. ``SKEWNONO_<FEATURE>_PROVIDER`` — explicit per-feature override, wins always.
2. Office mode AND an office adapter exists -> ``office``.
3. ``mock``.

Note that ``SKEWNONO_DATA_PROVIDER=office`` no longer FORCES office on every
feature — it selects the mode, and the filesystem decides per feature. The old
meaning was unusable in practice: it 500s every feature whose adapter is not
written yet, which is exactly why a tracked OFFICE_READY set used to be
necessary. Setting it to ``mock`` is now a whole-instance kill switch.
"""

import os
from typing import Literal, NamedTuple, cast

from back_dev_home._runtime.office_registry import (
    features,
    office_ready,
    repo_path,
)
from back_dev_home._runtime.site import detect_site


DataProvider = Literal["mock", "office"]

_GLOBAL_ENV = "SKEWNONO_DATA_PROVIDER"
_PREFIX = "SKEWNONO_"
_SUFFIX = "_PROVIDER"
_VALID_PROVIDERS = frozenset({"mock", "office"})


class FeatureResolution(NamedTuple):
    """One row of the boot log and of /api/health/providers."""

    feature: str
    provider: DataProvider
    reason: str


def _feature_env_name(feature: str) -> str:
    normalized = feature.strip().upper().replace("-", "_")
    return f"{_PREFIX}{normalized}{_SUFFIX}"


def _validated(raw: str, env_name: str) -> DataProvider:
    provider = raw.strip().lower()
    if provider not in _VALID_PROVIDERS:
        raise RuntimeError(
            f"Invalid data provider {raw!r} from {env_name}. "
            f"Expected 'mock' or 'office'."
        )
    return cast(DataProvider, provider)


def get_mode() -> DataProvider:
    """Is this process serving office data at all?

    Read fresh, never cached — tests monkeypatch these variables, and env
    reads are free.
    """
    raw = os.environ.get(_GLOBAL_ENV)
    if raw is not None:
        return _validated(raw, _GLOBAL_ENV)
    return "office" if detect_site() == "office" else "mock"


def get_data_provider(feature: str) -> DataProvider:
    """The adapter this feature should use right now."""
    env_name = _feature_env_name(feature)
    raw = os.environ.get(env_name)
    if raw is not None:
        return _validated(raw, env_name)
    if get_mode() == "office" and feature.strip().lower() in office_ready():
        return "office"
    return "mock"


def resolve_all() -> list[FeatureResolution]:
    """Every feature's provider AND why — the whole point of the boot log.

    With presence detection there is no .env line and no tracked set to read,
    so a feature quietly serving mock at the office would otherwise be
    invisible. The reason string is what makes it visible.
    """
    mode = get_mode()
    ready = office_ready()
    rows: list[FeatureResolution] = []
    for slug in sorted(features()):
        env_name = _feature_env_name(slug)
        raw = os.environ.get(env_name)
        if raw is not None:
            provider = _validated(raw, env_name)
            reason = f"forced by {env_name}={provider}"
        elif mode != "office":
            provider, reason = "mock", f"mode={mode}"
        elif slug in ready:
            provider, reason = "office", "providers/office.py found"
        else:
            provider, reason = "mock", "no providers/office.py"
        rows.append(FeatureResolution(slug, provider, reason))
    return rows


def validate_env() -> None:
    """Refuse to start when an explicit ``=office`` cannot be honored.

    An explicit, deliberate request for real fab data must never be silently
    answered with fabricated numbers — the same principle as the ``exc.name``
    guard in hardware's per-tab dispatcher, applied to configuration instead
    of imports. Called by the app factory right after load_dotenv.
    """
    known = features()
    ready = office_ready()
    for name in sorted(os.environ):
        if not (name.startswith(_PREFIX) and name.endswith(_SUFFIX)):
            continue
        if name == _GLOBAL_ENV:
            continue  # selects the mode; names no feature
        if _validated(os.environ[name], name) != "office":
            continue
        slug = name[len(_PREFIX):-len(_SUFFIX)].lower()
        if slug in ready:
            continue
        if slug not in known:
            raise RuntimeError(
                f"{name}=office names an unknown feature {slug!r}. "
                f"Known features: {', '.join(sorted(known))}."
            )
        directory = repo_path(known[slug])
        raise RuntimeError(
            f"{name}=office, but {directory}/providers/office.py does not "
            f"exist on this machine. Create it with:\n"
            f"  cp {directory}/providers/office_example.py "
            f"{directory}/providers/office.py\n"
            f"Or remove {name} to let this feature stay on mock."
        )
