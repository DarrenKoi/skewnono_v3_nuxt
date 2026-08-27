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

# Features whose OFFICE adapter reads another feature's data through that
# feature's own dispatcher — so the two must resolve to the same provider.
#
# storage joins every row against the live ``sem_list`` by ``eqp_ip``, because
# the storage collection pipeline writes fac-level fab names (``M16``) that the
# sidebar's fab_name filter (``M16A``) never matches. With storage=office and
# sem_list=mock the two sides of that join come from different universes: no IP
# matches, every row falls back, and the 스토리지 table renders EMPTY behind a
# 200 with nothing in the log.
#
# pm_planning and tttm take their ROSTER from sem_list (``sem_list/roster.py``'s
# ``fleet_rows``) and then look every tool up in meas_hist by ``eqp_id``. On a
# mock roster those ids are fabricated, so no run is ever found: both pages
# answer 200 with an empty fleet. Worse than storage's case, in fact — the
# pm-planning screen JOINS the two payloads by ``eqp_id``, so a mock roster on one
# side and a real one on the other intersects to nothing while each response
# looks individually fine.
#
# Declared here rather than checked inside the adapters because office.py is a
# gitignored copy — a rule that lives only there is a rule that ships to
# exactly one machine.
_OFFICE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "pm_planning": ("sem_list",),
    "storage": ("sem_list",),
    "tttm": ("sem_list",),
}


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


def _mismatched_office_dependency(
    resolved: dict[str, DataProvider],
) -> RuntimeError | None:
    """The first office feature whose declared dependency is still on mock.

    Checked against what actually RESOLVED, not against the environment: the
    dangerous pairing is reachable with no env var at all. At the office,
    ``cp``ing storage's adapter without sem_list's gives storage=office (its
    office.py exists) and sem_list=mock (its office.py does not) — presence
    detection resolves each independently, exactly as designed, and the join
    silently empties.
    """
    for feature, dependencies in sorted(_OFFICE_DEPENDENCIES.items()):
        if resolved.get(feature) != "office":
            continue
        for dependency in dependencies:
            if resolved.get(dependency) == "office":
                continue
            known = features()
            if dependency not in known:
                # A declared dependency that is not a feature is a typo in the
                # table above, not a deployment mistake — say so plainly rather
                # than printing a cp command for a directory that isn't there.
                return RuntimeError(
                    f"_OFFICE_DEPENDENCIES names {dependency!r} as a "
                    f"dependency of {feature}, but no such feature exists. "
                    f"Known features: {', '.join(sorted(known))}."
                )
            directory = repo_path(known[dependency])
            return RuntimeError(
                f"{feature} resolves to 'office' but {dependency} resolves to "
                f"'{resolved.get(dependency)}'. {feature}'s office adapter "
                f"joins against {dependency}'s live data, so this pairing "
                f"serves an EMPTY table behind a 200 rather than an error.\n"
                f"Put {dependency} on office too:\n"
                f"  cp {directory}/providers/office_example.py "
                f"{directory}/providers/office.py\n"
                f"Or put {feature} back on mock with "
                f"{_feature_env_name(feature)}=mock."
            )
    return None


def validate_env() -> None:
    """Refuse to start when an explicit ``=office`` cannot be honored.

    An explicit, deliberate request for real fab data must never be silently
    answered with fabricated numbers — the same principle as the ``exc.name``
    guard in hardware's per-tab dispatcher, applied to configuration instead
    of imports. Called by the app factory right after load_dotenv.

    ``_resolve`` enforces the same rule per feature; this sweeps every
    variable up front so a misconfigured feature fails at boot rather than
    when someone first opens its page.

    Then the same principle one step out: a feature can be perfectly
    configured on its own and still be unable to answer honestly because a
    feature it JOINS AGAINST is on mock. Those pairings
    (``_OFFICE_DEPENDENCIES``) are checked against the resolved table, after
    the per-variable sweep, so the more specific error wins when both apply.
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

    mismatch = _mismatched_office_dependency(
        {row.feature: row.provider for row in resolve_all()}
    )
    if mismatch is not None:
        raise mismatch
