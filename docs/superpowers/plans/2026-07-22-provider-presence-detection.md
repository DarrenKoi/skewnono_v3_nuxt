# Provider Presence Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existence of `<feature>/providers/office.py` the single signal that a feature serves office data, deleting the per-feature `.env` and `OFFICE_READY` bookkeeping.

**Architecture:** Split provider resolution into two independent decisions — *mode* (a property of the machine, from `detect_site()` or `SKEWNONO_DATA_PROVIDER`) and *readiness* (a property of the filesystem, from a glob for `providers/office.py`). A new `_runtime/office_registry.py` owns discovery; `_runtime/data_provider.py` owns everything env-related; the app factory validates config against the filesystem at boot and logs the resolved table; `/api/health/providers` serves the same table live.

**Tech Stack:** Python 3.14, Flask, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-22-provider-presence-detection-design.md`

## Global Constraints

- Python only; no new third-party dependencies.
- `get_data_provider(feature: str) -> Literal["mock", "office"]` **must keep its exact signature** — `chat/guard.py:68`, `hardware/providers/sharpness/office_example.py:133`, and four feature contract-gate tests call it directly and must not be edited.
- Backend test baseline is **169 passed, 2 skipped** (`.venv/bin/pytest back_dev_home -q`). Every task ends at or above this count.
- Run `npm run lint:md` after any Markdown edit; markdownlint `MD060` `compact` table style (`| --- |`, not `| ------- |`).
- Korean docs (`docs/office-migration/`, `MIGRATION.md`) keep formal endings — `~입니다.` / `~합니다.`
- `providers/office.py` is gitignored at every depth; never commit one.
- Commit after each task with a `type(scope): summary` subject plus a body saying what changed.

---

### Task 1: The office registry

Filesystem discovery, isolated from anything env-related so it can be tested against fake package trees.

**Files:**

- Create: `back_dev_home/_runtime/office_registry.py`
- Test: `back_dev_home/_runtime/tests/test_office_registry.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  - `features() -> dict[str, Path]` — slug → absolute feature directory, for every feature with `providers/mock.py`
  - `office_ready() -> dict[str, Path]` — same, for those with `providers/office.py`
  - `repo_path(feature_dir: Path) -> str` — repo-relative POSIX string for error messages
  - `reset_cache() -> None` — clears the memoized scan (tests only)
  - module global `_ROOT: Path` — monkeypatch target for tests

- [ ] **Step 1: Write the failing tests**

Create `back_dev_home/_runtime/tests/test_office_registry.py`:

```python
"""Filesystem discovery of office adapters.

Every test builds a fake package tree under tmp_path rather than reading the
real repo: at home NO providers/office.py exists anywhere (it is gitignored
and only ever created at the office), so the real tree cannot exercise the
office-ready paths at all.
"""

import pytest

from back_dev_home._runtime import office_registry


@pytest.fixture
def fake_tree(tmp_path, monkeypatch):
    """Build back_dev_home/<path>/providers/<files> trees and point _ROOT at it."""
    root = tmp_path / "back_dev_home"

    def build(spec: dict[str, list[str]]):
        for rel, filenames in spec.items():
            providers = root / rel / "providers"
            providers.mkdir(parents=True, exist_ok=True)
            for filename in filenames:
                (providers / filename).write_text("")
        monkeypatch.setattr(office_registry, "_ROOT", root)
        office_registry.reset_cache()
        return root

    yield build
    office_registry.reset_cache()


def test_feature_slug_is_the_directory_name_at_any_depth(fake_tree):
    fake_tree({
        "sem_list": ["mock.py"],
        "ebeam/hitachi/storage": ["mock.py"],
        "ebeam/cdsem/device_statistics": ["mock.py"],
    })
    assert set(office_registry.features()) == {
        "sem_list", "storage", "device_statistics",
    }


def test_office_ready_lists_only_features_with_an_office_adapter(fake_tree):
    fake_tree({
        "sem_list": ["mock.py", "office.py"],
        "chat": ["mock.py"],
    })
    assert set(office_registry.office_ready()) == {"sem_list"}


def test_per_tab_adapters_never_enter_the_global_registry(fake_tree):
    """The feature/tab boundary. hardware/providers/fdc/office.py must NOT
    register 'fdc' — that file is hardware's private business, resolved by
    its own _tab() fallback. The glob enforces this because 'fdc' is not
    literally named 'providers'."""
    root = fake_tree({"ebeam/hitachi/hardware": ["mock.py", "office.py"]})
    tab = root / "ebeam/hitachi/hardware/providers/fdc"
    tab.mkdir(parents=True)
    (tab / "office.py").write_text("")
    (tab / "mock.py").write_text("")
    office_registry.reset_cache()

    assert set(office_registry.office_ready()) == {"hardware"}
    assert "fdc" not in office_registry.features()


def test_underscore_prefixed_directories_are_skipped(fake_tree):
    fake_tree({"_internal/scratch": ["mock.py"], "sem_list": ["mock.py"]})
    assert set(office_registry.features()) == {"sem_list"}


def test_duplicate_slug_raises_with_both_paths(fake_tree):
    fake_tree({
        "ebeam/hitachi/hardware": ["mock.py"],
        "ebeam/cdsem/hardware": ["mock.py"],
    })
    with pytest.raises(RuntimeError) as exc:
        office_registry.features()
    message = str(exc.value)
    assert "hardware" in message
    assert "ebeam/hitachi/hardware" in message
    assert "ebeam/cdsem/hardware" in message


def test_office_adapter_without_a_mock_sibling_raises(fake_tree):
    fake_tree({"orphan": ["office.py"], "sem_list": ["mock.py"]})
    with pytest.raises(RuntimeError) as exc:
        office_registry.office_ready()
    assert "orphan" in str(exc.value)


def test_repo_path_is_relative_to_the_repo_root(fake_tree):
    fake_tree({"ebeam/hitachi/storage": ["mock.py"]})
    directory = office_registry.features()["storage"]
    assert office_registry.repo_path(directory) == (
        "back_dev_home/ebeam/hitachi/storage"
    )


def test_real_repo_finds_every_feature_and_no_office_adapter_at_home():
    """Sanity check against the actual tree, not a fixture."""
    office_registry.reset_cache()
    real = office_registry.features()
    assert {"sem_list", "storage", "hardware", "device_statistics"} <= set(real)
    assert len(real) == 21
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/_runtime/tests/test_office_registry.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'back_dev_home._runtime.office_registry'`

- [ ] **Step 3: Write the implementation**

Create `back_dev_home/_runtime/office_registry.py`:

```python
"""Which features have an office adapter — discovered from the filesystem.

``providers/office.py`` is gitignored and only ever appears because someone
deliberately ran ``cp office_example.py office.py`` while wiring a feature at
the office. Its existence IS the migration record, so nothing else has to
track readiness: no env var per feature, and no tracked set that the home side
would have to commit and push about a file it cannot see.

This mirrors what the app factory already does for blueprints
(``__init__.py`` globs ``routes.py``, then asserts each hit exports a
``Blueprint``): glob to discover, assert the hits are well-formed, fail at
boot rather than at request time.

Kept deliberately free of any ``os.environ`` access — everything env-related
lives in ``data_provider.py``, which imports this module. Splitting them that
way is what keeps the two free of a circular import.
"""

from functools import lru_cache
from pathlib import Path


# back_dev_home/. Monkeypatched by tests to point at a fake package tree.
_ROOT = Path(__file__).resolve().parent.parent


def _discover(filename: str) -> dict[str, Path]:
    """Map feature slug -> feature directory, for each providers/<filename>.

    ``**/providers/<filename>`` requires the file to sit DIRECTLY inside a
    directory literally named ``providers``, so per-tab adapters such as
    ``hardware/providers/fdc/office.py`` are excluded — ``fdc`` is not
    ``providers``. That exclusion is the boundary between feature-level
    resolution (here) and hardware's private per-tab fallback (``_tab()`` in
    ``hardware/providers/office_example.py``). It is load-bearing, and pinned
    by ``test_per_tab_adapters_never_enter_the_global_registry``.
    """
    found: dict[str, Path] = {}
    for path in sorted(_ROOT.glob(f"**/providers/{filename}")):
        feature_dir = path.parent.parent
        relative = feature_dir.relative_to(_ROOT)
        if any(part.startswith("_") for part in relative.parts):
            continue  # mirrors the blueprint scan in __init__.py
        slug = feature_dir.name
        if slug in found:
            raise RuntimeError(
                f"Duplicate feature slug {slug!r}: "
                f"{repo_path(found[slug])} and {repo_path(feature_dir)}. "
                f"Feature directory names must be globally unique — "
                f"SKEWNONO_{slug.upper()}_PROVIDER can only name one of them."
            )
        found[slug] = feature_dir
    return found


@lru_cache(maxsize=1)
def _scan() -> tuple[dict[str, Path], dict[str, Path]]:
    """Scan once per process. Adding an office.py requires a restart.

    Flask's dev reloader restarts on its own; cloud deploys restart anyway.
    """
    all_features = _discover("mock.py")
    ready = _discover("office.py")

    orphans = sorted(set(ready) - set(all_features))
    if orphans:
        paths = ", ".join(repo_path(ready[slug]) for slug in orphans)
        raise RuntimeError(
            f"providers/office.py with no sibling providers/mock.py: {paths}. "
            f"Every feature needs a mock adapter — home development and the "
            f"contract tests both run against it."
        )
    return all_features, ready


def features() -> dict[str, Path]:
    """Every feature, by slug. A feature is a directory with providers/mock.py."""
    return _scan()[0]


def office_ready() -> dict[str, Path]:
    """Features whose providers/office.py exists on this machine."""
    return _scan()[1]


def repo_path(feature_dir: Path) -> str:
    """Repo-relative POSIX path, for error messages a human can paste."""
    return feature_dir.relative_to(_ROOT.parent).as_posix()


def reset_cache() -> None:
    """Drop the memoized scan. Tests only."""
    _scan.cache_clear()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/_runtime/tests/test_office_registry.py -v`

Expected: 8 passed. If `test_real_repo_finds_every_feature_and_no_office_adapter_at_home` reports a count other than 21, confirm with `find back_dev_home -path '*/providers/mock.py' | wc -l` and update the literal — a feature may have been added since this plan was written.

- [ ] **Step 5: Confirm no regression**

Run: `.venv/bin/pytest back_dev_home -q`

Expected: `177 passed, 2 skipped`

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/_runtime/office_registry.py \
        back_dev_home/_runtime/tests/test_office_registry.py
git commit -m "feat(runtime): discover office adapters from the filesystem

Adds _runtime/office_registry.py: globs **/providers/{mock,office}.py to map
feature slug -> directory, so the existence of a gitignored office.py is what
marks a feature office-ready. Guards against duplicate slugs and office.py
without a mock.py sibling, both raising at import. The glob deliberately
excludes per-tab adapters (hardware/providers/fdc/office.py) to keep the
feature/tab boundary intact.

Not yet wired into resolution — that is the next commit."
```

---

### Task 2: Two-step resolution

Rewire `get_data_provider()` onto the registry, delete `OFFICE_READY`, and rewrite the resolution tests.

**Files:**

- Modify: `back_dev_home/_runtime/data_provider.py` (full rewrite, 50 lines)
- Modify: `back_dev_home/_runtime/site.py:41-61` (delete `OFFICE_READY`, update docstring)
- Modify: `back_dev_home/_runtime/tests/test_site_provider.py` (rewrite)

**Interfaces:**

- Consumes: `office_registry.features()`, `office_registry.office_ready()`, `office_registry.repo_path()` from Task 1.
- Produces:
  - `get_data_provider(feature: str) -> DataProvider` — unchanged signature
  - `get_mode() -> DataProvider`
  - `resolve_all() -> list[FeatureResolution]` where `FeatureResolution` is a `NamedTuple(feature: str, provider: DataProvider, reason: str)`
  - `validate_env() -> None` — raises `RuntimeError` on unhonorable config

- [ ] **Step 1: Write the failing tests**

Replace the entire contents of `back_dev_home/_runtime/tests/test_site_provider.py`:

```python
"""Site detection + two-step provider resolution.

The invariant: an explicit per-feature env var always wins; otherwise a
feature serves office data only when the process is in office MODE *and* that
feature has a providers/office.py.

Resolution tests point office_registry at a fake tree, because at home no
office.py exists anywhere in the real repo — office.py is gitignored and only
created at the office.
"""

import pytest

from back_dev_home._runtime import data_provider, office_registry, site


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Neutralize any real provider/site config leaking in from .env."""
    monkeypatch.delenv("SKEWNONO_SITE", raising=False)
    monkeypatch.delenv("SKEWNONO_DATA_PROVIDER", raising=False)
    monkeypatch.delenv("SKEWNONO_OFFICE_HOSTNAMES", raising=False)
    for feature in ("STORAGE", "CHAT", "SEM_LIST", "SKEW"):
        monkeypatch.delenv(f"SKEWNONO_{feature}_PROVIDER", raising=False)


@pytest.fixture
def wired(tmp_path, monkeypatch):
    """A fake tree where sem_list + storage have office.py and chat/skew do not."""
    root = tmp_path / "back_dev_home"
    for rel, filenames in {
        "sem_list": ["mock.py", "office.py"],
        "ebeam/hitachi/storage": ["mock.py", "office.py"],
        "chat": ["mock.py"],
        "ebeam/hitachi/skew": ["mock.py"],
    }.items():
        providers = root / rel / "providers"
        providers.mkdir(parents=True)
        for filename in filenames:
            (providers / filename).write_text("")
        if filenames == ["mock.py"]:
            (providers / "office_example.py").write_text("")
    monkeypatch.setattr(office_registry, "_ROOT", root)
    office_registry.reset_cache()
    yield root
    office_registry.reset_cache()


def _set_host(monkeypatch, name: str) -> None:
    monkeypatch.setattr(site.socket, "gethostname", lambda: name)
    # These tests run outside /project/workSpace, so is_cloud() is already
    # False — no stub needed; the cloud test overrides it explicitly.


# ---------------------------------------------------------------- detect_site

def test_home_hostname_detected_with_suffix_and_case(monkeypatch):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini.local")
    assert site.detect_site() == "home"


def test_unknown_hostname_is_none(monkeypatch):
    _set_host(monkeypatch, "some-random-box")
    assert site.detect_site() is None


def test_pc_prefix_is_office(monkeypatch):
    # Company-issued office PCs are named "PC<...>" — prefix alone suffices.
    _set_host(monkeypatch, "PC0123456.corp.example")
    assert site.detect_site() == "office"


def test_office_hostnames_env_list(monkeypatch):
    _set_host(monkeypatch, "OFFICE-MAC-01.corp.example")
    monkeypatch.setenv("SKEWNONO_OFFICE_HOSTNAMES", "office-mac-01, spare-box")
    assert site.detect_site() == "office"


def test_cloud_deploy_is_office_site(monkeypatch):
    # Phase 3: production must NEVER silently fall back to mock just because
    # the cloud VM hostname isn't in any registry — the deploy path decides.
    _set_host(monkeypatch, "ephemeral-vm-8f3a2")  # unknown hostname
    monkeypatch.setattr(site, "is_cloud", lambda: True)
    assert site.detect_site() == "office"


def test_site_env_overrides_hostname(monkeypatch):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini.local")  # a home machine...
    monkeypatch.setenv("SKEWNONO_SITE", "office")       # ...forced to office
    assert site.detect_site() == "office"


def test_invalid_site_env_raises(monkeypatch):
    monkeypatch.setenv("SKEWNONO_SITE", "moon-base")
    with pytest.raises(RuntimeError):
        site.detect_site()


# ---------------------------------------------------------------------- mode

def test_mode_follows_site_when_global_var_unset(monkeypatch):
    _set_host(monkeypatch, "PC0123456")
    assert data_provider.get_mode() == "office"
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    assert data_provider.get_mode() == "mock"


def test_unknown_host_is_mock_mode(monkeypatch):
    _set_host(monkeypatch, "some-random-box")
    assert data_provider.get_mode() == "mock"


def test_global_var_overrides_site_in_both_directions(monkeypatch):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    assert data_provider.get_mode() == "office"
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    _set_host(monkeypatch, "PC0123456")
    assert data_provider.get_mode() == "mock"


def test_invalid_global_var_raises(monkeypatch):
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "opensearch")
    with pytest.raises(RuntimeError) as exc:
        data_provider.get_mode()
    assert "SKEWNONO_DATA_PROVIDER" in str(exc.value)


# --------------------------------------------------------- get_data_provider

def test_office_mode_flips_only_features_with_an_adapter(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    assert data_provider.get_data_provider("sem_list") == "office"
    assert data_provider.get_data_provider("storage") == "office"
    # No office.py -> mock, silently. A blanket office default would 500 these.
    assert data_provider.get_data_provider("chat") == "mock"
    assert data_provider.get_data_provider("skew") == "mock"


def test_mock_mode_ignores_present_adapters(monkeypatch, wired):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    assert data_provider.get_data_provider("sem_list") == "mock"


def test_kill_switch_returns_the_whole_instance_to_mock(monkeypatch, wired):
    """One line takes an office machine back to a known-good state without
    deleting any adapter."""
    _set_host(monkeypatch, "PC0123456")
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "mock")
    assert data_provider.get_data_provider("sem_list") == "mock"
    assert data_provider.get_data_provider("storage") == "mock"


def test_feature_var_mock_beats_a_present_adapter(monkeypatch, wired):
    """The escape hatch when an office adapter breaks mid-shift."""
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    monkeypatch.setenv("SKEWNONO_STORAGE_PROVIDER", "mock")
    assert data_provider.get_data_provider("storage") == "mock"
    assert data_provider.get_data_provider("sem_list") == "office"


def test_feature_var_office_wins_at_home(monkeypatch, wired):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    monkeypatch.setenv("SKEWNONO_SEM_LIST_PROVIDER", "office")
    assert data_provider.get_data_provider("sem_list") == "office"


def test_invalid_feature_var_raises_naming_that_var(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SEM_LIST_PROVIDER", "redis")
    with pytest.raises(RuntimeError) as exc:
        data_provider.get_data_provider("sem_list")
    assert "SKEWNONO_SEM_LIST_PROVIDER" in str(exc.value)


# --------------------------------------------------------------- resolve_all

def test_resolve_all_reports_provider_and_reason(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    monkeypatch.setenv("SKEWNONO_STORAGE_PROVIDER", "mock")
    by_feature = {r.feature: r for r in data_provider.resolve_all()}

    assert set(by_feature) == {"sem_list", "storage", "chat", "skew"}
    assert by_feature["sem_list"].provider == "office"
    assert by_feature["sem_list"].reason == "providers/office.py found"
    assert by_feature["chat"].provider == "mock"
    assert by_feature["chat"].reason == "no providers/office.py"
    assert by_feature["storage"].provider == "mock"
    assert "SKEWNONO_STORAGE_PROVIDER" in by_feature["storage"].reason


def test_resolve_all_reports_mode_when_not_at_the_office(monkeypatch, wired):
    _set_host(monkeypatch, "Daeyoungs-Mac-mini")
    by_feature = {r.feature: r for r in data_provider.resolve_all()}
    assert by_feature["sem_list"].provider == "mock"
    assert by_feature["sem_list"].reason == "mode=mock"


# -------------------------------------------------------------- validate_env

def test_validate_env_passes_when_config_matches_the_filesystem(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_SEM_LIST_PROVIDER", "office")
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "mock")
    data_provider.validate_env()  # must not raise


def test_validate_env_refuses_office_without_an_adapter(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_CHAT_PROVIDER", "office")
    with pytest.raises(RuntimeError) as exc:
        data_provider.validate_env()
    message = str(exc.value)
    assert "SKEWNONO_CHAT_PROVIDER" in message
    assert "cp back_dev_home/chat/providers/office_example.py" in message
    assert "back_dev_home/chat/providers/office.py" in message


def test_validate_env_flags_an_unknown_feature_as_a_typo(monkeypatch, wired):
    monkeypatch.setenv("SKEWNONO_STORAGES_PROVIDER", "office")
    with pytest.raises(RuntimeError) as exc:
        data_provider.validate_env()
    assert "unknown feature" in str(exc.value)
    monkeypatch.delenv("SKEWNONO_STORAGES_PROVIDER")


def test_validate_env_ignores_the_global_mode_var(monkeypatch, wired):
    """SKEWNONO_DATA_PROVIDER selects the mode; it names no feature, so it can
    never be 'unhonorable'."""
    monkeypatch.setenv("SKEWNONO_DATA_PROVIDER", "office")
    data_provider.validate_env()  # must not raise
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/_runtime/tests/test_site_provider.py -v`

Expected: FAIL — `AttributeError: module 'back_dev_home._runtime.data_provider' has no attribute 'get_mode'` on the mode tests onward.

- [ ] **Step 3: Rewrite `data_provider.py`**

Replace the entire contents of `back_dev_home/_runtime/data_provider.py`:

```python
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
    """Is this process serving office data at all? Read fresh, never cached —
    tests monkeypatch these variables, and env reads are free."""
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
```

- [ ] **Step 4: Delete `OFFICE_READY` from `site.py`**

In `back_dev_home/_runtime/site.py`, replace lines 5-10 of the module docstring:

```python
* home Mac mini  -> everything defaults to mock (Phase 1)
* office machine -> OFFICE_READY features default to office; the rest stay
  mock until their adapter is wired (a blanket office default would 500
  every stub feature)
* unknown host   -> mock (safe: never assume office infrastructure exists)
```

with:

```python
* home Mac mini  -> mock mode (Phase 1)
* office machine -> office mode; which FEATURES that flips is decided
  separately, by whether each has a providers/office.py (office_registry)
* unknown host   -> mock (safe: never assume office infrastructure exists)
```

Then delete the whole `OFFICE_READY` block (lines 48-61, from the `# Features whose office adapter is implemented` comment through the closing `)`), leaving `_normalize_host` immediately after `_OFFICE_HOSTNAMES = frozenset()`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/_runtime -v`

Expected: 8 registry + 23 site/provider tests pass (the old file had 12; it is replaced, not extended).

- [ ] **Step 6: Confirm no regression across the suite**

Run: `.venv/bin/pytest back_dev_home -q`

Expected: `188 passed, 2 skipped`. If `chat/guard.py` or any feature contract gate fails, the signature compatibility promise was broken — fix `data_provider.py`, not the caller.

Then confirm nothing still references the deleted set:

Run: `grep -rn --include='*.py' OFFICE_READY back_dev_home | grep -v __pycache__`

Expected: only the two `recipe_tat` provider docstrings (fixed in Task 5), no imports.

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/_runtime/data_provider.py \
        back_dev_home/_runtime/site.py \
        back_dev_home/_runtime/tests/test_site_provider.py
git commit -m "feat(runtime): resolve providers by office.py presence

get_data_provider() now asks two independent questions: is the process in
office MODE (SKEWNONO_DATA_PROVIDER, else detect_site()), and does this
feature have a providers/office.py. Both must be true. Explicit per-feature
env vars still win in either direction.

Deletes site.OFFICE_READY — a set, tracked in git, caching a fact about a
gitignored file on another machine, which is why it kept going stale.
Promoting a feature is now just the cp that creates its adapter.

SKEWNONO_DATA_PROVIDER changes meaning: =office selects office mode rather
than forcing every feature office (which 500s unwired ones); =mock becomes a
whole-instance kill switch. Adds get_mode(), resolve_all() and validate_env()
for the boot log and health endpoint. get_data_provider()'s signature is
unchanged, so chat/guard.py and the contract gates are untouched."
```

---

### Task 3: Boot validation and the provider table

**Files:**

- Modify: `back_dev_home/__init__.py:116-131` (inside `create_app`)
- Test: `back_dev_home/_runtime/tests/test_boot_providers.py`

**Interfaces:**

- Consumes: `data_provider.validate_env()`, `data_provider.resolve_all()`, `data_provider.get_mode()` from Task 2; `site.detect_site()`.
- Produces: `log_provider_table() -> None` in `back_dev_home/_runtime/boot.py`, and a `"skewnono.providers"` logger.

- [ ] **Step 1: Write the failing tests**

Create `back_dev_home/_runtime/tests/test_boot_providers.py`:

```python
"""The startup provider table, and boot refusal on unhonorable config."""

import logging

import pytest

from back_dev_home._runtime import boot, office_registry


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("SKEWNONO_SITE", raising=False)
    monkeypatch.delenv("SKEWNONO_DATA_PROVIDER", raising=False)
    for feature in ("STORAGE", "CHAT", "SEM_LIST"):
        monkeypatch.delenv(f"SKEWNONO_{feature}_PROVIDER", raising=False)


@pytest.fixture
def wired(tmp_path, monkeypatch):
    root = tmp_path / "back_dev_home"
    for rel, filenames in {
        "sem_list": ["mock.py", "office.py"],
        "chat": ["mock.py"],
    }.items():
        providers = root / rel / "providers"
        providers.mkdir(parents=True)
        for filename in filenames:
            (providers / filename).write_text("")
    monkeypatch.setattr(office_registry, "_ROOT", root)
    office_registry.reset_cache()
    yield root
    office_registry.reset_cache()


def test_table_names_every_feature_with_provider_and_reason(
    monkeypatch, wired, caplog
):
    monkeypatch.setenv("SKEWNONO_SITE", "office")
    with caplog.at_level(logging.INFO, logger="skewnono.providers"):
        boot.log_provider_table()
    text = caplog.text
    assert "mode=office" in text
    assert "sem_list" in text and "providers/office.py found" in text
    assert "chat" in text and "no providers/office.py" in text


def test_table_logs_at_info_on_its_own_logger(monkeypatch, wired, caplog):
    """The logger must carry its own handler+level like skewnono.activity —
    app.logger defaults to WARNING, which would make the table invisible in
    exactly the deployment where it matters."""
    logger = logging.getLogger("skewnono.providers")
    assert logger.level == logging.INFO
    assert logger.handlers
    assert logger.propagate is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest back_dev_home/_runtime/tests/test_boot_providers.py -v`

Expected: FAIL — `ImportError: cannot import name 'boot'`

- [ ] **Step 3: Write `back_dev_home/_runtime/boot.py`**

```python
"""Startup reporting for provider resolution.

With presence detection there is no .env line and no tracked set to read, so
this table is the moment-of-truth record of which pages are serving 사내 data.
It carries its own handler and level, copying the ``skewnono.activity``
pattern in ``_logging/activity.py``: ``app.logger`` inherits WARNING from the
root logger, so an INFO table would be invisible in exactly the deployment
where someone needs it.
"""

import logging

from back_dev_home._runtime.data_provider import get_mode, resolve_all
from back_dev_home._runtime.site import detect_site


logger = logging.getLogger("skewnono.providers")

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_provider_table() -> None:
    rows = resolve_all()
    office = sum(1 for row in rows if row.provider == "office")
    logger.info(
        "data providers: site=%s mode=%s — %d/%d features on office",
        detect_site() or "unknown",
        get_mode(),
        office,
        len(rows),
    )
    width = max((len(row.feature) for row in rows), default=0)
    for row in rows:
        logger.info(
            "  %-*s  %-6s  %s", width, row.feature, row.provider, row.reason
        )
```

- [ ] **Step 4: Wire it into the app factory**

In `back_dev_home/__init__.py`, add to the import block after line 14:

```python
from ._runtime.boot import log_provider_table
from ._runtime.data_provider import validate_env
```

Then in `create_app()`, insert immediately after line 119 (`app.secret_key = ...`) and before the `CORS(` call:

```python
    # Config must agree with the filesystem before we serve anything: an
    # explicit SKEWNONO_<FEATURE>_PROVIDER=office with no providers/office.py
    # is a promise of real fab data we cannot keep, so refuse to start rather
    # than answer it with mock at 2am. Then record what actually resolved —
    # presence detection leaves no .env line to read afterwards.
    validate_env()
    log_provider_table()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/pytest back_dev_home/_runtime/tests/test_boot_providers.py -v`

Expected: 2 passed.

- [ ] **Step 6: Verify the table appears against the real app**

Run: `.venv/bin/python -c "from back_dev_home import create_app; create_app()" 2>&1 | head -30`

Expected: a `data providers: site=... mode=mock — 0/21 features on office` header followed by 21 indented rows, every one `mock  mode=mock` (this is the home Mac mini; no `office.py` exists here).

Then verify boot refusal actually refuses:

Run: `SKEWNONO_CHAT_PROVIDER=office .venv/bin/python -c "from back_dev_home import create_app; create_app()" 2>&1 | tail -6`

Expected: `RuntimeError: SKEWNONO_CHAT_PROVIDER=office, but back_dev_home/chat/providers/office.py does not exist ...` including the `cp` command.

- [ ] **Step 7: Confirm no regression**

Run: `.venv/bin/pytest back_dev_home -q`

Expected: `190 passed, 2 skipped`

- [ ] **Step 8: Commit**

```bash
git add back_dev_home/_runtime/boot.py \
        back_dev_home/_runtime/tests/test_boot_providers.py \
        back_dev_home/__init__.py
git commit -m "feat(runtime): validate provider config and log the table at boot

create_app() now calls validate_env() before serving: an explicit
SKEWNONO_<FEATURE>_PROVIDER=office with no providers/office.py refuses to
start and prints the cp command, instead of answering a deliberate request
for real fab data with mock. Then log_provider_table() records what actually
resolved, with a reason per feature.

The logger carries its own handler at INFO like skewnono.activity —
app.logger inherits WARNING from root, which would hide the table in exactly
the deployment where it is needed."
```

---

### Task 4: `GET /api/health/providers`

**Files:**

- Modify: `back_dev_home/health/routes.py`
- Test: `back_dev_home/health/tests/test_providers_route.py`

**Interfaces:**

- Consumes: `data_provider.resolve_all()`, `data_provider.get_mode()`, `site.detect_site()`.
- Produces: `GET /api/health/providers` returning `{"site": str, "mode": str, "features": [{"feature": str, "provider": str, "reason": str}]}`.

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/health/tests/test_providers_route.py`:

```python
"""The provider introspection endpoint.

Deliberately NOT routed through health/data.py's mock/office swap: this is
runtime introspection, not phase-swappable data. A swappable version could
misreport itself in exactly the situation you would query it.
"""

from back_dev_home import create_app


def test_providers_endpoint_lists_every_feature():
    client = create_app().test_client()
    response = client.get("/api/health/providers")
    assert response.status_code == 200

    body = response.get_json()
    assert body["mode"] in ("mock", "office")
    assert body["site"] in ("home", "office", "unknown")

    features = {row["feature"]: row for row in body["features"]}
    assert {"sem_list", "storage", "hardware"} <= set(features)
    for row in features.values():
        assert row["provider"] in ("mock", "office")
        assert row["reason"]


def test_providers_endpoint_is_not_a_swappable_data_surface():
    """health/data.py must gain no provider function — the endpoint reads the
    runtime directly, so it cannot be swapped out from under itself."""
    from back_dev_home.health import data

    assert not hasattr(data, "get_provider_table")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest back_dev_home/health/tests/test_providers_route.py -v`

Expected: FAIL — 404 on `/api/health/providers`.

- [ ] **Step 3: Add the route**

Replace the contents of `back_dev_home/health/routes.py`:

```python
from flask import Blueprint, jsonify

from back_dev_home._runtime.data_provider import get_mode, resolve_all
from back_dev_home._runtime.site import detect_site
from back_dev_home.health.data import get_services_health

bp = Blueprint("health", __name__)


@bp.get("/health/services")
def services_health():
    return jsonify(get_services_health())


@bp.get("/health/providers")
def providers_health():
    """Which features are serving office data right now, and why.

    Reads the runtime directly rather than going through health/data.py: this
    is introspection, not phase-swappable data, and a swappable version could
    misreport itself in exactly the situation you would query it.
    """
    return jsonify(
        {
            "site": detect_site() or "unknown",
            "mode": get_mode(),
            "features": [row._asdict() for row in resolve_all()],
        }
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest back_dev_home/health/tests/test_providers_route.py -v`

Expected: 2 passed. If the request returns 401/302, the identity middleware is gating it — add the endpoint to the same exemption the existing `/health/services` route uses and re-run.

- [ ] **Step 5: Confirm no regression**

Run: `.venv/bin/pytest back_dev_home -q`

Expected: `192 passed, 2 skipped`

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/health/routes.py \
        back_dev_home/health/tests/test_providers_route.py
git commit -m "feat(health): add GET /api/health/providers

Serves the same feature/provider/reason table the app logs at boot, so the
question 'is this page real 사내 data right now?' has a live answer. Reads
_runtime directly rather than health/data.py — introspection must not itself
be a swappable surface, or it could misreport in exactly the case you would
query it."
```

---

### Task 5: Documentation and `.env.example`

The 21 commented per-feature lines and every "set the env var" instruction become wrong the moment Task 2 lands, so this task is not optional polish.

**Files:**

- Modify: `back_dev_home/.env.example:59-135`
- Modify: `CLAUDE.md` (API Abstraction Layer bullet 3)
- Modify: `docs/office-migration/STATUS.md` (전환 절차 section)
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py:28` and `.../office.py:28` (stale `OFFICE_READY` mention)

- [ ] **Step 1: Replace the `.env.example` provider block**

Replace lines 59-135 (from `# ── Data provider switch` through the closing `# ────...` rule) with:

```text
# ── Data provider switch (home <-> office) ──────────────────────────
# A feature serves office data when TWO things are true:
#
#   1. the process is in OFFICE MODE, and
#   2. that feature has a providers/office.py file.
#
# Neither one is configured here. Office mode is auto-detected
# (back_dev_home/_runtime/site.py): the Phase 3 cloud deploy path
# (/project/workSpace) and hostnames starting with "PC" (company office-PC
# naming) are office; the home Mac mini and unknown hosts are home. And a
# feature becomes office-ready the moment you run
#
#   cp back_dev_home/<feature>/providers/office_example.py \
#      back_dev_home/<feature>/providers/office.py
#
# and restart Flask. office.py is gitignored, so it only ever exists where
# someone deliberately created it — which is why its presence alone is
# trusted. Features without one stay on mock, silently and safely, so a
# half-migrated office machine never 500s its unwired pages.
#
# To see what is actually live right now: GET /api/health/providers, or read
# the provider table Flask logs at startup. Nothing in .env records it.
#
# Site override (rarely needed — e.g. testing an office adapter from home
# over VPN; you must also cp the office.py you want to exercise):
# SKEWNONO_SITE=office
# Extra office hostnames, only for office machines NOT named PC<...>
# (comma-separated, compared lowercase without domain suffix):
# SKEWNONO_OFFICE_HOSTNAMES=office-mac-01
#
# Mode override. `office` forces office MODE (the filesystem still decides
# per feature); `mock` is a whole-instance kill switch that returns every
# page to mock without deleting any adapter:
# SKEWNONO_DATA_PROVIDER=mock
#
# Per-feature override, to pin ONE feature against the mode. The key is the
# same one its data.py passes to get_data_provider("<key>"):
#   =mock    forces mock even though office.py exists — the escape hatch when
#            an adapter breaks mid-shift.
#   =office  is only legal when that feature's office.py exists. Otherwise
#            Flask REFUSES TO START and prints the cp command: an explicit
#            request for real fab data is never silently answered with mock.
# SKEWNONO_STORAGE_PROVIDER=mock
# SKEWNONO_SEM_LIST_PROVIDER=office
#
# Which features are PROVEN against real 사내 data (as opposed to merely
# having an office.py) lives in exactly one place: the 상태/검증일 columns of
# docs/office-migration/STATUS.md.
#
# hardware switches per TAB as well as per feature. Its dispatcher lazily
# imports providers/<tab>/office.py and falls back to that tab's mock.py when
# the file is absent, so hardware can be office-ready while individual tabs
# are still mock. That fallback is NOT marked in the response — check
# `ls back_dev_home/ebeam/hitachi/hardware/providers/*/office.py` or the
# dispatcher's log line. A tab whose office.py exists but fails to import
# raises instead of falling back.
# ────────────────────────────────────────────────────────────────────
```

- [ ] **Step 2: Update `CLAUDE.md`**

Replace this bullet under **API Abstraction Layer**:

```markdown
- Adapter selected at runtime by `SKEWNONO_<FEATURE>_PROVIDER` (e.g. `SKEWNONO_SEM_LIST_PROVIDER`) or global `SKEWNONO_DATA_PROVIDER`, values `mock`|`office`. When neither is set, the site decides: the Phase 3 cloud (detected by deploy path via `is_cloud()`) and recognized office hostnames default `OFFICE_READY` features to `office`; the home Mac mini and unknown hosts default everything to `mock` (selector `_runtime/data_provider.py`, site detection + readiness list `_runtime/site.py` — add a feature to `OFFICE_READY` when its office adapter goes live).
```

with:

```markdown
- Adapter selection is two independent questions. **Mode** — is this process at the office? — comes from `SKEWNONO_DATA_PROVIDER` (`mock`|`office`) when set, else from site detection (`_runtime/site.py`: the Phase 3 cloud deploy path via `is_cloud()`, or a `PC*` hostname, is office; home Mac mini and unknown hosts are home). **Readiness** — is this feature wired? — is whether `<feature>/providers/office.py` exists (`_runtime/office_registry.py`). A feature serves office data only when both hold, so **the `cp office_example.py office.py` that creates an adapter is the same act that switches it on** — there is no list to maintain. `SKEWNONO_<FEATURE>_PROVIDER` still overrides one feature either way; `=office` with no adapter present refuses to boot. `SKEWNONO_DATA_PROVIDER=mock` is a whole-instance kill switch. Inspect what actually resolved via `GET /api/health/providers` or the boot log.
```

- [ ] **Step 3: Update `docs/office-migration/STATUS.md`**

Replace the 전환 절차 numbered list with:

```markdown
1. GLM이 `back_dev_home/<기능>/MIGRATION.md`를 읽고 `providers/office.py`를 구현합니다.
2. 계약 테스트가 office 모드에서 통과해야 합니다. 저장소 루트에서
   `SKEWNONO_<기능>_PROVIDER=office .venv/bin/pytest back_dev_home/<기능>` 형식으로
   실행하며, 이는 각 기능의 `MIGRATION.md` Verify 명령과 동일합니다.
3. Flask를 재시작합니다. `providers/office.py` 파일이 존재하는 것 자체가
   전환 신호이므로, `.env` 수정이나 코드 커밋은 필요하지 않습니다.
4. `GET /api/health/providers` 또는 기동 로그의 provider 표에서 해당 기능이
   `office`로 표시되는지 확인합니다.

이 문서의 상태/검증일 컬럼은 "실제 사내 데이터로 확인되었는가"를 기록합니다.
`office.py`의 존재 여부(= 무엇이 전환되는가)와는 별개이며, 코드가 이 표를
읽지는 않습니다.
```

- [ ] **Step 4: Fix the three stale `OFFICE_READY` references**

In both `back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py:28` and `back_dev_home/ebeam/hitachi/recipe_tat/providers/office.py:28`, replace `(or rely on OFFICE_READY)` with `(or just leave it unset — this file's existence is the switch)`.

Note `office.py` is gitignored, so only `office_example.py` will be staged. Edit both anyway: the local copy is what runs.

Then in `back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md:17-19`, replace:

```markdown
That is a net improvement over leaving the whole feature on `mock` (the
catalog becomes real, detail is synthetic either way), which is why
`recipe_search` is in `_runtime/site.py`'s `OFFICE_READY`. The caveat worth
```

with:

```markdown
That is a net improvement over leaving the whole feature on `mock` (the
catalog becomes real, detail is synthetic either way), which is why
`providers/office.py` is copied for `recipe_search` at all. The caveat worth
```

- [ ] **Step 5: Lint and verify nothing stale remains**

Run: `npm run lint:md`

Expected: `Summary: 0 error(s)`

Run: `grep -rn --include='*.py' --include='*.md' --include='.env.example' OFFICE_READY back_dev_home docs CLAUDE.md | grep -v __pycache__`

Expected: no output.

Run: `.venv/bin/pytest back_dev_home -q`

Expected: `192 passed, 2 skipped`

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/.env.example CLAUDE.md docs/office-migration/STATUS.md \
        back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py
git commit -m "docs: describe provider presence detection, drop the env var list

.env.example loses all 21 commented per-feature lines and its three
readiness groups — none of that is configuration any more. It now explains
the two conditions (office mode + office.py exists), the cp that switches a
feature on, and the two override forms that remain.

CLAUDE.md, STATUS.md and the stale recipe_tat docstrings follow. STATUS.md is
now purely a record of what has been PROVEN against 사내 data; no code reads
it, and the migration procedure loses its env-var step."
```

---

### Task 6: Make hardware's per-tab fallback visible

`_tab()` logs via `logging.getLogger(__name__)`, which inherits WARNING from the root logger — so the INFO fallback line its own docstring calls "the only record" never actually prints. Small fix, directly serving this design's visibility goal.

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/office_example.py:28-41`
- Modify: `back_dev_home/ebeam/hitachi/hardware/providers/office.py` (same edit; gitignored, local only)

- [ ] **Step 1: Point `_tab()` at the configured logger**

In `office_example.py`, replace:

```python
import logging
from datetime import datetime
from importlib import import_module
```

with:

```python
from datetime import datetime
from importlib import import_module
```

and replace:

```python
_LOG = logging.getLogger(__name__)
```

with:

```python
# The module logger inherits WARNING from root, which would silently swallow
# the fallback line below — the one record that a tab is serving mock under
# an office switch. skewnono.providers carries its own INFO handler.
from back_dev_home._runtime.boot import logger as _LOG
```

Move that import up into the import block with the other `back_dev_home` imports.

- [ ] **Step 2: Apply the identical edit to `office.py`**

`office.py` is the file that actually runs and is gitignored. Skip this step if it does not exist on this machine (it will not, at home).

- [ ] **Step 3: Verify the fallback line prints**

Run:

```bash
cp back_dev_home/ebeam/hitachi/hardware/providers/office_example.py \
   back_dev_home/ebeam/hitachi/hardware/providers/office.py
SKEWNONO_SITE=office .venv/bin/python -c "
from datetime import datetime, timedelta
from back_dev_home.ebeam.hitachi.hardware import data
end = datetime.now(); start = end - timedelta(days=7)
data.get_hardware_service('cd-sem', 'sce', 'CDSEM01', 'R3', start, end)
" 2>&1 | grep -c "has no providers"
rm back_dev_home/ebeam/hitachi/hardware/providers/office.py
```

Expected: `1` — the fallback line is now visible. The `rm` matters: leaving `office.py` behind would make the home machine report hardware as office-ready.

- [ ] **Step 4: Confirm no regression**

Run: `.venv/bin/pytest back_dev_home -q`

Expected: `192 passed, 2 skipped`

Run: `git status --short back_dev_home/ebeam/hitachi/hardware/providers/`

Expected: only `office_example.py` modified — no `office.py` (gitignored and removed).

- [ ] **Step 5: Commit and push**

```bash
git add back_dev_home/ebeam/hitachi/hardware/providers/office_example.py
git commit -m "fix(hardware): make the per-tab mock fallback actually log

_tab() logged its fallback through logging.getLogger(__name__), which
inherits WARNING from the root logger — so the INFO line its own docstring
calls 'the only record' of a tab serving mock never printed. Routes it
through skewnono.providers, which carries its own INFO handler."
git push origin main
```

---

## Verification

After Task 6, confirm end to end:

```bash
.venv/bin/pytest back_dev_home -q              # 192 passed, 2 skipped
npm run lint:md                                # 0 errors
grep -rn OFFICE_READY back_dev_home docs CLAUDE.md | grep -v __pycache__   # empty
.venv/bin/python -c "from back_dev_home import create_app; create_app()" | head -5
```

Then start the app and hit the endpoint:

```bash
.venv/bin/python index.py &
curl -s localhost:5050/api/health/providers | python -m json.tool | head -20
```

Expected at home: `"mode": "mock"`, `"site": "home"`, 21 features all `mock` with reason `mode=mock`.
