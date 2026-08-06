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
_LAZY_SUB_PROVIDER_ENVS = frozenset({
    "SKEWNONO_CHAT_KNOWLEDGE_PROVIDER",
    "SKEWNONO_CHAT_SCOPE_PROVIDER",
})


class FeatureResolution(NamedTuple):
    """One row of the boot log and of /api/health/providers."""

    feature: str
    provider: DataProvider
    reason: str


def _slug(feature: str) -> str:
    """Canonical feature key: the providers/ parent directory name.

    Directory names use underscores, so a hyphenated caller ("sem-list") must
    normalize the same way the env var does — otherwise the env lookup and the
    registry lookup would disagree about the same feature.
    """
    return feature.strip().lower().replace("-", "_")


def _feature_env_name(feature: str) -> str:
    return f"{_PREFIX}{_slug(feature).upper()}{_SUFFIX}"


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


def _validate_chat_knowledge_sources_at_boot() -> None:
    """Raise the same RuntimeError-at-startup shape for a bad source list.

    ``SKEWNONO_CHAT_KNOWLEDGE_SOURCES`` is otherwise read lazily, per request,
    by ``available_sources()`` -> ``agent._build_tools()`` — so a typo'd value
    used to boot clean and only fail with a 500 on the first chat message,
    after the user turn was already persisted. Validated here, alongside the
    other lazy chat selectors, only when the knowledge provider is actually
    ``office`` — mock stays exactly as unvalidated as before.

    Imported locally rather than at module scope: this module is shared
    plumbing with no reason to hard-depend on the chat feature package at
    import time.
    """
    from back_dev_home.chat.config import get_knowledge_sources

    try:
        get_knowledge_sources()
    except ValueError as error:
        raise RuntimeError(str(error)) from error


def _unhonorable(slug: str, env_name: str) -> RuntimeError:
    """The one message for "=office cannot be served".

    Shared by the request path and the boot check so the two can never
    disagree about what went wrong or how to fix it.
    """
    known = features()
    if slug not in known:
        return RuntimeError(
            f"{env_name}=office names an unknown feature {slug!r}. "
            f"Known features: {', '.join(sorted(known))}."
        )
    directory = repo_path(known[slug])
    return RuntimeError(
        f"{env_name}=office, but {directory}/providers/office.py does not "
        f"exist on this machine. Create it with:\n"
        f"  cp {directory}/providers/office_example.py "
        f"{directory}/providers/office.py\n"
        f"Or remove {env_name} to let this feature stay on mock."
    )


def _resolve(feature: str, mode: DataProvider | None = None) -> FeatureResolution:
    """The resolution cascade, written once.

    ``mode`` is passed in by ``resolve_all`` so a 20-feature table does not
    re-read the environment and re-run hostname detection per row.
    """
    slug = _slug(feature)
    env_name = _feature_env_name(slug)

    raw = os.environ.get(env_name)
    if raw is not None:
        provider = _validated(raw, env_name)
        if provider == "office" and slug not in office_ready():
            # Checked here, not only at boot: the contract-test command in
            # every MIGRATION.md runs pytest without an app factory, so this
            # is the path most likely to hit a missing adapter. Raising the
            # cp-command error beats a bare ModuleNotFoundError from data.py.
            raise _unhonorable(slug, env_name)
        return FeatureResolution(slug, provider, f"forced by {env_name}={provider}")

    mode = get_mode() if mode is None else mode
    if mode != "office":
        return FeatureResolution(slug, "mock", f"mode={mode}")
    if slug in office_ready():
        return FeatureResolution(slug, "office", "providers/office.py found")
    return FeatureResolution(slug, "mock", "no providers/office.py")


def get_data_provider(feature: str) -> DataProvider:
    """The adapter this feature should use right now."""
    return _resolve(feature).provider


def resolve_all() -> list[FeatureResolution]:
    """Every feature's provider AND why — the whole point of the boot log.

    With presence detection there is no .env line and no tracked set to read,
    so a feature quietly serving mock at the office would otherwise be
    invisible. The reason string is what makes it visible.
    """
    mode = get_mode()
    return [_resolve(slug, mode) for slug in sorted(features())]


def validate_env() -> None:
    """Refuse to start when an explicit ``=office`` cannot be honored.

    An explicit, deliberate request for real fab data must never be silently
    answered with fabricated numbers — the same principle as the ``exc.name``
    guard in hardware's per-tab dispatcher, applied to configuration instead
    of imports. Called by the app factory right after load_dotenv.

    ``_resolve`` enforces the same rule per feature; this sweeps every
    variable up front so a misconfigured feature fails at boot rather than
    when someone first opens its page.
    """
    ready = office_ready()
    for name in sorted(os.environ):
        if not (name.startswith(_PREFIX) and name.endswith(_SUFFIX)):
            continue
        if name in _LAZY_SUB_PROVIDER_ENVS:
            provider = _validated(os.environ[name], name)
            if name == "SKEWNONO_CHAT_KNOWLEDGE_PROVIDER" and provider == "office":
                # The knowledge provider choice gates a second, otherwise-lazy
                # selector (which sources are ready) — validate it in the
                # same sweep so a typo fails at boot, not on the first chat
                # message. Only reachable when office is actually selected,
                # so mock's boot behaviour is unchanged.
                _validate_chat_knowledge_sources_at_boot()
            continue  # lazy selectors name no generic feature
        if name == _GLOBAL_ENV:
            continue  # mode selector names no generic feature
        if _validated(os.environ[name], name) != "office":
            continue
        slug = name[len(_PREFIX):-len(_SUFFIX)].lower()
        if slug not in ready:
            raise _unhonorable(slug, name)
