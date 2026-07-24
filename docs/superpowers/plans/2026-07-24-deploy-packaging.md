# Deployment Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a self-contained deployment folder from the working tree that boots on the cloud host at `/project/workSpace`, and remove the known boot blocker before the first deploy.

**Architecture:** Three independent deliverables. Task 1 fixes an application bug (`hcputil` module path) that would kill the deploy at boot. Task 2 builds `scripts/preflight_cloud.py`, a dependency-free checker that ships inside the bundle and diagnoses the cloud host. Tasks 3–7 build `scripts/pack_deploy.py`: preflight → copy → prune → verify → manifest.

**Tech Stack:** Python 3.14 stdlib only (`pathlib`, `shutil`, `argparse`, `subprocess`, `importlib`), pytest 8. No new dependencies.

## Global Constraints

- **This is a feasibility deploy.** Block only what guarantees a dead deploy; everything else is advisory. A bundle serving mock data is a success.
- **Bundle depth is load-bearing.** `back_dev_home/_runtime/env.py` must sit exactly 2 levels below the bundle root, or `spa_dir()` and `is_cloud()` both break.
- **Read the working tree, never `git archive`.** `providers/office.py`, `minio_handler/minio_config.py`, and `back_dev_home/.env` are gitignored and must ship.
- **Run scripts from the repo root** as `.venv/bin/python -m scripts.<name>`, matching `scripts/sync_office_adapters.py`. `scripts/` has no `__init__.py` — namespace packages handle it.
- **Tests:** `.venv/bin/python -m pytest tests/ -q`. New test files go in `tests/` (which has `__init__.py`), except the auth test which goes beside the code it tests.
- **`preflight_cloud.py` imports stdlib only** — it must run before `pip install` succeeds.
- **Markdown:** run `npm run lint:md` after editing any `.md`. Tables use markdownlint `MD060` `compact` style.
- **Bundle root layout is fixed:** `index.py`, `wsgi.ini`, `preflight.py`, `DEPLOY.md`, `MANIFEST.txt`, `back_dev_home/`, `front-dev-home/.output/public/`, `ops_store/`, `minio_handler/`, `ftp_handler/`.

---

### Task 1: Fix the `hcputil` SSO import

**Files:**

- Modify: `back_dev_home/_auth/provider.py:25-37`
- Create: `back_dev_home/_auth/tests/__init__.py`
- Test: `back_dev_home/_auth/tests/test_provider.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `back_dev_home._auth.provider._load_sso_class() -> type`. Raises `ImportError` when neither module path resolves. `CloudIdentityProvider.__init__` calls it and assigns the result to `self._SSO_cls`.

**Why this is first:** `create_app()` constructs `CloudIdentityProvider()` unconditionally when `is_cloud()` is true, with no `try`/`except`, and `wsgi.ini` sets `need-app = true`. A wrong module name means uwsgi refuses to start. Nothing else in this plan matters if the app cannot boot.

- [ ] **Step 1: Create the test package marker**

```bash
mkdir -p back_dev_home/_auth/tests
touch back_dev_home/_auth/tests/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `back_dev_home/_auth/tests/test_provider.py`:

```python
"""`hcputil` lives only on the cloud image, so these tests inject stub
modules into sys.modules rather than importing the real library.

The module path is genuinely uncertain: the in-house requirements doc
(afm_data_platform/개발요구.txt:31) spells it `auto`, the library spells it
`auth`. The loader accepts either, and these tests pin that behaviour.
"""

import sys
import types

import pytest

from back_dev_home._auth.provider import _load_sso_class


class _FakeSSO:
    pass


@pytest.fixture
def stub_hcputil(monkeypatch):
    """Install hcputil.<variant>.sso stubs; yields an installer function."""

    def install(*variants):
        for variant in variants:
            pkg = types.ModuleType("hcputil")
            pkg.__path__ = []
            sub = types.ModuleType(f"hcputil.{variant}")
            sub.__path__ = []
            sso_mod = types.ModuleType(f"hcputil.{variant}.sso")
            sso_mod.SSO = _FakeSSO
            monkeypatch.setitem(sys.modules, "hcputil", pkg)
            monkeypatch.setitem(sys.modules, f"hcputil.{variant}", sub)
            monkeypatch.setitem(sys.modules, f"hcputil.{variant}.sso", sso_mod)

    return install


def test_prefers_auth_spelling(stub_hcputil):
    stub_hcputil("auth")
    assert _load_sso_class() is _FakeSSO


def test_falls_back_to_auto_spelling(stub_hcputil):
    stub_hcputil("auto")
    assert _load_sso_class() is _FakeSSO


def test_raises_naming_both_paths_when_neither_exists(monkeypatch):
    for name in list(sys.modules):
        if name == "hcputil" or name.startswith("hcputil."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "path", [])

    with pytest.raises(ImportError) as excinfo:
        _load_sso_class()

    message = str(excinfo.value)
    assert "hcputil.auth.sso" in message
    assert "hcputil.auto.sso" in message
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_provider.py -v`

Expected: FAIL — `ImportError: cannot import name '_load_sso_class' from 'back_dev_home._auth.provider'`

- [ ] **Step 4: Implement the loader**

In `back_dev_home/_auth/provider.py`, add `import importlib` to the imports at the top of the file, then replace the class body header (lines 25-37) with:

```python
def _load_sso_class():
    """Return the cloud image's SSO class, accepting either module spelling.

    `hcputil` is supplied by the cloud image, never by requirements.txt. The
    in-house doc this code was written from (afm_data_platform/개발요구.txt:31)
    spells the module `auto`; the library spells it `auth`. Trying both costs
    one failed import and removes an entire class of boot failure from a
    deploy that cannot be iterated on quickly — create_app() builds
    CloudIdentityProvider() with no try/except, and wsgi.ini sets
    need-app=true, so a wrong name means uwsgi never starts.
    """
    errors = []
    for module_path in ("hcputil.auth.sso", "hcputil.auto.sso"):
        try:
            return importlib.import_module(module_path).SSO
        except ImportError as exc:
            errors.append(f"{module_path}: {exc}")
    raise ImportError(
        "hcputil SSO not importable; the cloud image must provide it. Tried:\n  "
        + "\n  ".join(errors)
    )


class CloudIdentityProvider:
    """Cloud production: validate via the cloud image's hcputil SSO. Imported
    lazily because hcputil is provided only by the cloud image."""

    _ID_ATTRS = ("user_id", "member_id", "userId", "memberId", "id")

    def __init__(self) -> None:
        self._SSO_cls = _load_sso_class()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest back_dev_home/_auth/tests/test_provider.py -v`

Expected: PASS — 3 passed

- [ ] **Step 6: Verify nothing else broke**

Run: `.venv/bin/python -m pytest tests/ -q`

Expected: PASS — same count as before this task, no new failures

- [ ] **Step 7: Commit**

```bash
git add back_dev_home/_auth/provider.py back_dev_home/_auth/tests/
git commit -m "fix(auth): accept either hcputil SSO module spelling

back_dev_home/_auth/provider.py imported hcputil.auto.sso, copied from
afm_data_platform/개발요구.txt:31. The library spells it hcputil.auth.sso.

This was a boot blocker, not a warning: create_app() builds
CloudIdentityProvider() unconditionally when is_cloud(), with no
try/except, and wsgi.ini sets need-app=true — so a wrong module name
means uwsgi refuses to start and the deploy fails before serving a
request.

_load_sso_class() tries auth then auto and raises naming both paths if
neither resolves. Trying both costs one failed import and removes the
failure mode entirely from a first cloud deploy that cannot be iterated
on quickly."
```

---

### Task 2: On-cloud preflight checker

**Files:**

- Create: `scripts/preflight_cloud.py`
- Test: `tests/test_preflight_cloud.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `CLOUD_PREFIX: Path` — `Path("/project/workSpace")`
  - `RUNTIME_PACKAGES: tuple[tuple[str, str], ...]` — `(import_name, pip_name)` pairs
  - `check_layout(root: Path) -> list[str]` — returns failure strings, empty when OK
  - `check_imports() -> tuple[list[str], list[str]]` — `(failures, notes)`
  - `check_config(root: Path) -> tuple[list[str], list[str]]` — `(failures, warnings)`
  - `main(argv: list[str] | None = None) -> int` — 0 when no failures

**Why stdlib only:** this runs *before* `pip install` succeeds, so it can report which packages are missing. Importing anything third-party at module scope would defeat its purpose.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_preflight_cloud.py`:

```python
"""The cloud preflight checker must degrade to a report, never an exception.

Its whole job is to run on a host where things are broken, so any check that
raises instead of returning a failure string is a bug.
"""

import sys
import types
from pathlib import Path

import pytest

from scripts import preflight_cloud


def _make_bundle(tmp_path: Path) -> Path:
    root = tmp_path / "bundle"
    (root / "back_dev_home" / "_runtime").mkdir(parents=True)
    (root / "back_dev_home" / "_runtime" / "env.py").write_text("")
    (root / "front-dev-home" / ".output" / "public").mkdir(parents=True)
    (root / "front-dev-home" / ".output" / "public" / "index.html").write_text("<!doctype html>")
    (root / "back_dev_home" / ".env").write_text("SKEWNONO_SECRET_KEY=real-key\n")
    (root / "back_dev_home" / "requirements.txt").write_text("Flask>=3.0\n")
    (root / "index.py").write_text("")
    return root


def test_layout_passes_on_a_well_formed_bundle(tmp_path):
    root = _make_bundle(tmp_path)
    assert preflight_cloud.check_layout(root) == []


def test_layout_reports_missing_spa(tmp_path):
    root = _make_bundle(tmp_path)
    (root / "front-dev-home" / ".output" / "public" / "index.html").unlink()

    failures = preflight_cloud.check_layout(root)

    assert any("index.html" in f for f in failures)


def test_layout_reports_broken_depth_invariant(tmp_path):
    """env.py must sit exactly 2 levels below the root or spa_dir() misses."""
    root = _make_bundle(tmp_path)
    nested = root / "extra" / "back_dev_home" / "_runtime"
    nested.mkdir(parents=True)
    nested.joinpath("env.py").write_text("")
    (root / "back_dev_home" / "_runtime" / "env.py").unlink()

    failures = preflight_cloud.check_layout(root)

    assert any("env.py" in f for f in failures)


def test_imports_report_missing_package_by_pip_name(monkeypatch):
    monkeypatch.setattr(
        preflight_cloud, "RUNTIME_PACKAGES", (("definitely_not_installed", "some-pip-name"),)
    )

    failures, _notes = preflight_cloud.check_imports()

    assert any("some-pip-name" in f for f in failures)


def test_imports_accept_either_hcputil_spelling(monkeypatch):
    monkeypatch.setattr(preflight_cloud, "RUNTIME_PACKAGES", ())
    pkg = types.ModuleType("hcputil")
    pkg.__path__ = []
    sub = types.ModuleType("hcputil.auto")
    sub.__path__ = []
    sso = types.ModuleType("hcputil.auto.sso")
    sso.SSO = object
    monkeypatch.setitem(sys.modules, "hcputil", pkg)
    monkeypatch.setitem(sys.modules, "hcputil.auto", sub)
    monkeypatch.setitem(sys.modules, "hcputil.auto.sso", sso)

    failures, notes = preflight_cloud.check_imports()

    assert failures == []
    assert any("hcputil.auto.sso" in n for n in notes)


def test_config_warns_on_default_secret_key(tmp_path):
    root = _make_bundle(tmp_path)
    (root / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=dev-only-not-for-prod\n"
    )

    failures, warnings = preflight_cloud.check_config(root)

    assert failures == []
    assert any("SKEWNONO_SECRET_KEY" in w for w in warnings)


def test_config_fails_when_env_missing(tmp_path):
    root = _make_bundle(tmp_path)
    (root / "back_dev_home" / ".env").unlink()

    failures, _warnings = preflight_cloud.check_config(root)

    assert any(".env" in f for f in failures)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_preflight_cloud.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.preflight_cloud'`

- [ ] **Step 3: Implement the checker**

Create `scripts/preflight_cloud.py`:

```python
"""Will this bundle boot? Run this on the cloud host BEFORE starting uwsgi.

`wsgi.ini` sets `need-app = true`, so every boot problem surfaces as a uwsgi
crash log — a poor diagnostic on a host with a slow iteration loop. This
script turns each of those failures into one line naming the remedy.

Run it TWICE:

    cd /project/workSpace
    python preflight.py                                  # before pip install
    pip install -r back_dev_home/requirements.txt
    python preflight.py                                  # after

The first pass proves the transfer landed at the right path with the right
layout — the failure with the most confusing symptoms, because the app still
returns HTTP 200 while silently running with auth off, no SPA, and mock data.
The second proves the dependency install completed.

STDLIB ONLY. This must run before `pip install` succeeds, or it cannot report
which packages are missing.
"""

import argparse
import importlib
import sys
from pathlib import Path

CLOUD_PREFIX = Path("/project/workSpace")
DEFAULT_SECRET_KEY = "dev-only-not-for-prod"

# (import name, pip name) — the two differ often enough to be worth pairing,
# because the remedy the operator needs is the pip name.
RUNTIME_PACKAGES = (
    ("flask", "Flask"),
    ("flask_cors", "flask-cors"),
    ("flask_limiter", "flask-limiter"),
    ("pandas", "pandas"),
    ("pyarrow", "pyarrow"),
    ("redis", "redis"),
    ("minio", "minio"),
    ("opensearchpy", "opensearch-py"),
    ("apscheduler", "apscheduler"),
    ("dotenv", "python-dotenv"),
)

# The cloud image supplies these; requirements.txt deliberately does not.
HCPUTIL_PATHS = ("hcputil.auth.sso", "hcputil.auto.sso")


def check_layout(root: Path) -> list[str]:
    """Structural checks. Depth matters as much as presence."""
    failures = []

    env_py = root / "back_dev_home" / "_runtime" / "env.py"
    if not env_py.is_file():
        failures.append(
            f"MISSING {env_py} — back_dev_home/ did not survive the transfer."
        )
    elif env_py.resolve().parents[2] != root.resolve():
        # spa_dir() is parents[2] / front-dev-home / .output / public.
        failures.append(
            f"DEPTH {env_py} is not exactly 2 levels below {root}; "
            "spa_dir() will resolve to the wrong place and the UI will 404."
        )

    index_html = root / "front-dev-home" / ".output" / "public" / "index.html"
    if not index_html.is_file():
        failures.append(
            f"MISSING {index_html} — the SPA is absent; every page returns 404."
        )

    for name in ("index.py", "wsgi.ini"):
        if not (root / name).is_file():
            failures.append(f"MISSING {root / name}")

    if not root.resolve().is_relative_to(CLOUD_PREFIX):
        failures.append(
            f"PATH bundle is at {root.resolve()}, not under {CLOUD_PREFIX}. "
            "is_cloud() will be False: no SSO auth, no SPA mount, mock data. "
            f"Move the bundle so it sits under {CLOUD_PREFIX}."
        )

    return failures


def check_imports() -> tuple[list[str], list[str]]:
    """Returns (failures, notes). Notes record which hcputil spelling worked."""
    failures = []
    notes = []

    for import_name, pip_name in RUNTIME_PACKAGES:
        try:
            importlib.import_module(import_name)
        except ImportError as exc:
            failures.append(
                f"IMPORT {import_name} unavailable ({exc}); "
                f"run: pip install -r back_dev_home/requirements.txt  [{pip_name}]"
            )

    for module_path in HCPUTIL_PATHS:
        try:
            importlib.import_module(module_path)
        except ImportError:
            continue
        notes.append(f"hcputil resolved as {module_path}")
        break
    else:
        failures.append(
            "IMPORT hcputil SSO unavailable; tried "
            + " and ".join(HCPUTIL_PATHS)
            + ". This is supplied by the cloud image, NOT by requirements.txt. "
            "Without it create_app() raises and uwsgi refuses to start."
        )

    return failures, notes


def _parse_env(text: str) -> dict[str, str]:
    """Minimal .env reader — python-dotenv may not be installed yet."""
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def check_config(root: Path) -> tuple[list[str], list[str]]:
    """Returns (failures, warnings)."""
    failures = []
    warnings = []

    env_path = root / "back_dev_home" / ".env"
    if not env_path.is_file():
        failures.append(
            f"MISSING {env_path} — create_app() calls load_dotenv on this path; "
            "without it the app boots unconfigured."
        )
        return failures, warnings

    try:
        values = _parse_env(env_path.read_text(encoding="utf-8"))
    except OSError as exc:
        failures.append(f"UNREADABLE {env_path}: {exc}")
        return failures, warnings

    secret = values.get("SKEWNONO_SECRET_KEY", "")
    if not secret or secret == DEFAULT_SECRET_KEY:
        warnings.append(
            "SKEWNONO_SECRET_KEY is unset or still the default "
            f"({DEFAULT_SECRET_KEY!r}); sessions are signed with a known key. "
            "Acceptable for a feasibility deploy, not for skewnono.skhynix.com."
        )

    return failures, warnings


def _adapter_roster(root: Path) -> list[str]:
    backend = root / "back_dev_home"
    if not backend.is_dir():
        return []
    return sorted(
        str(p.relative_to(backend).parent.parent)
        for p in backend.rglob("providers/office.py")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check whether this bundle will boot on the cloud host."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Bundle root (default: this file's directory).",
    )
    args = parser.parse_args(argv)
    root = args.root

    print(f"SKEWNONO cloud preflight — {root}\n")

    failures = check_layout(root)
    import_failures, notes = check_imports()
    failures += import_failures
    config_failures, warnings = check_config(root)
    failures += config_failures

    for note in notes:
        print(f"  ok   {note}")

    roster = _adapter_roster(root)
    if roster:
        print(f"  ok   {len(roster)} office adapter(s): {', '.join(roster)}")
    else:
        warnings.append(
            "No providers/office.py found — every feature will serve mock data."
        )

    for warning in warnings:
        print(f"  WARN {warning}")

    if not failures:
        print("\nPASS — uwsgi should start. Next: uwsgi --ini wsgi.ini")
        return 0

    print("")
    for failure in failures:
        print(f"  FAIL {failure}")
    print(f"\nFAIL — {len(failures)} blocking problem(s). Do not start uwsgi yet.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_preflight_cloud.py -v`

Expected: PASS — 7 passed

- [ ] **Step 5: Smoke-run it against the repo itself**

Run: `.venv/bin/python -m scripts.preflight_cloud --root .`

Expected: exit 1, with a `FAIL PATH bundle is at ... not under /project/workSpace` line. That is correct — the repo is not a cloud bundle. Confirm the other checks pass and the adapter roster lists 6 adapters.

- [ ] **Step 6: Commit**

```bash
git add scripts/preflight_cloud.py tests/test_preflight_cloud.py
git commit -m "feat(deploy): add on-cloud preflight checker

Ships inside the deploy bundle as preflight.py and answers 'will uwsgi
start' in one command. wsgi.ini sets need-app=true, so every boot problem
otherwise surfaces only as a uwsgi crash log.

Checks layout (including the parents[2] depth invariant spa_dir() relies
on), the /project/workSpace prefix is_cloud() tests, every runtime import
by pip name, both hcputil SSO spellings, and .env presence plus secret-key
default.

Stdlib only, so it runs before pip install succeeds and can report which
packages are missing."
```

---

### Task 3: Bundle spec — the include/exclude rules

**Files:**

- Create: `scripts/pack_deploy.py`
- Test: `tests/test_pack_deploy.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `INCLUDED_ROOTS: tuple[str, ...]` — repo-relative paths copied into the bundle
  - `PRUNE_DIRS: frozenset[str]` — directory names removed anywhere in the tree
  - `PRUNE_SUFFIXES: tuple[str, ...]` — file suffixes removed anywhere
  - `should_prune(path: Path) -> bool`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pack_deploy.py`:

```python
"""Packing rules for the office → cloud bundle."""

from pathlib import Path

from scripts import pack_deploy


def test_includes_the_three_vendored_packages_the_app_imports():
    for name in ("ops_store", "minio_handler", "ftp_handler"):
        assert name in pack_deploy.INCLUDED_ROOTS


def test_excludes_packages_the_app_never_imports():
    """afm_data_platform is 1.8MB of spec; ops_index_mgmt is index tooling."""
    for name in ("afm_data_platform", "ops_index_mgmt", "docs", "openwiki"):
        assert name not in pack_deploy.INCLUDED_ROOTS


def test_includes_the_built_spa_at_its_exact_path():
    assert "front-dev-home/.output/public" in pack_deploy.INCLUDED_ROOTS


def test_prunes_pycache_and_tests():
    assert pack_deploy.should_prune(Path("back_dev_home/__pycache__"))
    assert pack_deploy.should_prune(Path("back_dev_home/sem_list/tests"))
    assert pack_deploy.should_prune(Path("back_dev_home/conftest.py"))


def test_prunes_markdown_and_compiled_files():
    assert pack_deploy.should_prune(Path("back_dev_home/sem_list/MIGRATION.md"))
    assert pack_deploy.should_prune(Path("back_dev_home/x.pyc"))
    assert pack_deploy.should_prune(Path("back_dev_home/.DS_Store"))


def test_keeps_the_files_that_must_ship():
    """office.py and .env are gitignored — losing them is the failure mode."""
    assert not pack_deploy.should_prune(Path("back_dev_home/sem_list/providers/office.py"))
    assert not pack_deploy.should_prune(Path("back_dev_home/.env"))
    assert not pack_deploy.should_prune(Path("back_dev_home/requirements.txt"))
    assert not pack_deploy.should_prune(Path("minio_handler/minio_config.py"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pack_deploy.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.pack_deploy'`

- [ ] **Step 3: Implement the rules**

Create `scripts/pack_deploy.py`:

```python
"""Pack the working tree into a folder ready to copy to /project/workSpace.

Run FROM THE REPO ROOT, at the office, after building the frontend:

    npm --prefix front-dev-home run build
    .venv/bin/python -m scripts.pack_deploy

Two properties of this repository shape everything here.

**Depth is load-bearing.** _runtime/env.py defines is_cloud() as "does this
file resolve under /project/workSpace" and spa_dir() as parents[2]/
front-dev-home/.output/public. Cloud mode — auth blueprint, SPA mount, office
site detection — is a property of the filesystem path, not of configuration.
A re-nested bundle loses all three while still answering HTTP 200.

**The files that matter most are untracked.** providers/office.py,
minio_handler/minio_config.py and back_dev_home/.env are gitignored by design,
so this reads the working tree. A git-archive approach would produce a bundle
that boots cleanly and serves mock data in production — the worst available
failure mode, because nothing announces it.
"""

from pathlib import Path

# Repo-relative paths copied wholesale into the bundle. Order is display order.
# Only ops_store, minio_handler and ftp_handler are actually imported by the
# app; ops_index_mgmt (index-creation tooling) and afm_data_platform (1.8MB,
# referenced only in a mock docstring) are deliberately absent.
INCLUDED_ROOTS = (
    "index.py",
    "wsgi.ini",
    "back_dev_home",
    "front-dev-home/.output/public",
    "ops_store",
    "minio_handler",
    "ftp_handler",
)

# Directory names removed anywhere in the copied tree.
PRUNE_DIRS = frozenset({"__pycache__", "tests", ".pytest_cache", ".ruff_cache"})

# File suffixes removed anywhere. .md covers 22 MIGRATION.md files plus
# READMEs — office-migration notes with no runtime role.
PRUNE_SUFFIXES = (".pyc", ".pyo", ".md", ".log")

# Exact file names removed anywhere.
PRUNE_NAMES = frozenset({"conftest.py", ".DS_Store", "Thumbs.db"})


def should_prune(path: Path) -> bool:
    """True when this path must not appear in the bundle."""
    if path.name in PRUNE_NAMES:
        return True
    if path.name in PRUNE_DIRS:
        return True
    if any(part in PRUNE_DIRS for part in path.parts):
        return True
    return path.suffix in PRUNE_SUFFIXES
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pack_deploy.py -v`

Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/pack_deploy.py tests/test_pack_deploy.py
git commit -m "feat(deploy): define the cloud bundle include/exclude rules

Only ops_store, minio_handler and ftp_handler are imported by the app, so
ops_index_mgmt and afm_data_platform (1.8MB, referenced only in a mock
docstring) stay out. Prunes __pycache__, tests/, conftest.py and the 22
MIGRATION.md files.

Keeps the gitignored files that must ship — providers/office.py, .env,
minio_config.py — which is why this reads the working tree rather than
git archive."
```

---

### Task 4: Office-side preflight checks

**Files:**

- Modify: `scripts/pack_deploy.py`
- Test: `tests/test_pack_deploy.py`

**Interfaces:**

- Consumes: `INCLUDED_ROOTS` from Task 3.
- Produces:
  - `Check` — `dataclass(name: str, ok: bool, message: str, blocking: bool)`
  - `run_preflight(repo_root: Path, strict: bool = False) -> list[Check]`
  - `blocking_failures(checks: list[Check]) -> list[Check]`

**Severity rule (from the spec's feasibility framing):** block only what guarantees a dead deploy. An incomplete mock→office transition is *expected* right now, so it warns. `--strict` promotes every advisory to blocking, for use after the transition completes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pack_deploy.py`:

```python
import pytest


def _make_repo(tmp_path: Path) -> Path:
    """A minimal tree that passes every blocking check."""
    root = tmp_path / "repo"
    (root / "back_dev_home" / "_runtime").mkdir(parents=True)
    (root / "back_dev_home" / "_runtime" / "env.py").write_text("")
    (root / "back_dev_home" / ".env").write_text("SKEWNONO_SECRET_KEY=real\n")
    (root / "back_dev_home" / "requirements.txt").write_text("Flask>=3.0\n")
    (root / "front-dev-home" / ".output" / "public").mkdir(parents=True)
    (root / "front-dev-home" / ".output" / "public" / "index.html").write_text("<x>")
    (root / "front-dev-home" / "app").mkdir(parents=True)
    for name in ("ops_store", "minio_handler", "ftp_handler"):
        (root / name).mkdir()
        (root / name / "__init__.py").write_text("")
    (root / "index.py").write_text("")
    (root / "wsgi.ini").write_text("")
    return root


def test_preflight_passes_on_a_complete_tree(tmp_path):
    checks = pack_deploy.run_preflight(_make_repo(tmp_path))
    assert pack_deploy.blocking_failures(checks) == []


def test_missing_spa_blocks(tmp_path):
    root = _make_repo(tmp_path)
    (root / "front-dev-home" / ".output" / "public" / "index.html").unlink()

    failures = pack_deploy.blocking_failures(pack_deploy.run_preflight(root))

    assert any("index.html" in f.message for f in failures)


def test_missing_env_blocks(tmp_path):
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").unlink()

    failures = pack_deploy.blocking_failures(pack_deploy.run_preflight(root))

    assert any(".env" in f.message for f in failures)


def test_no_office_adapters_is_advisory_not_blocking(tmp_path):
    """The transition is deliberately incomplete during the feasibility deploy."""
    root = _make_repo(tmp_path)

    checks = pack_deploy.run_preflight(root)

    adapter = next(c for c in checks if c.name == "office_adapters")
    assert not adapter.ok
    assert not adapter.blocking
    assert pack_deploy.blocking_failures(checks) == []


def test_strict_promotes_advisories_to_blocking(tmp_path):
    root = _make_repo(tmp_path)

    failures = pack_deploy.blocking_failures(
        pack_deploy.run_preflight(root, strict=True)
    )

    assert any(f.name == "office_adapters" for f in failures)


def test_default_secret_key_is_advisory(tmp_path):
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=dev-only-not-for-prod\n"
    )

    checks = pack_deploy.run_preflight(root)

    secret = next(c for c in checks if c.name == "secret_key")
    assert not secret.ok
    assert not secret.blocking
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pack_deploy.py -v`

Expected: FAIL — `AttributeError: module 'scripts.pack_deploy' has no attribute 'run_preflight'`

- [ ] **Step 3: Implement the checks**

Add to `scripts/pack_deploy.py`, after the pruning rules:

```python
from dataclasses import dataclass

DEFAULT_SECRET_KEY = "dev-only-not-for-prod"


@dataclass(frozen=True)
class Check:
    """One preflight result.

    `blocking` is the whole point: this deploy is a feasibility check, so an
    incomplete mock→office transition must warn rather than refuse. Only a
    guaranteed-dead deploy blocks.
    """

    name: str
    ok: bool
    message: str
    blocking: bool


def _newest_mtime(root: Path) -> float:
    return max(
        (p.stat().st_mtime for p in root.rglob("*") if p.is_file()), default=0.0
    )


def _read_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def office_adapters(repo_root: Path) -> list[str]:
    """Feature slugs that have a providers/office.py, i.e. serve real data."""
    backend = repo_root / "back_dev_home"
    if not backend.is_dir():
        return []
    return sorted(
        str(p.relative_to(backend).parent.parent)
        for p in backend.rglob("providers/office.py")
    )


def run_preflight(repo_root: Path, strict: bool = False) -> list[Check]:
    checks = []

    def add(name, ok, message, blocking):
        checks.append(Check(name, ok, message, blocking or strict))

    spa_index = repo_root / "front-dev-home" / ".output" / "public" / "index.html"
    add(
        "spa_built",
        spa_index.is_file(),
        f"{spa_index} missing — run: npm --prefix front-dev-home run build",
        True,
    )

    env_path = repo_root / "back_dev_home" / ".env"
    add(
        "env_present",
        env_path.is_file(),
        f"{env_path} missing — create_app() load_dotenv()s this path",
        True,
    )

    reqs = repo_root / "back_dev_home" / "requirements.txt"
    add(
        "requirements_present",
        reqs.is_file(),
        f"{reqs} missing — nothing to pip install on the cloud",
        True,
    )

    missing_roots = [r for r in INCLUDED_ROOTS if not (repo_root / r).exists()]
    add(
        "roots_present",
        not missing_roots,
        f"missing from the working tree: {', '.join(missing_roots)}",
        True,
    )

    app_dir = repo_root / "front-dev-home" / "app"
    build_fresh = True
    if spa_index.is_file() and app_dir.is_dir():
        build_fresh = spa_index.stat().st_mtime >= _newest_mtime(app_dir)
    add(
        "build_fresh",
        build_fresh,
        "the built SPA is older than front-dev-home/app/ — rebuild, or you "
        "will ship yesterday's UI",
        False,
    )

    secret = _read_env(env_path).get("SKEWNONO_SECRET_KEY", "")
    add(
        "secret_key",
        bool(secret) and secret != DEFAULT_SECRET_KEY,
        "SKEWNONO_SECRET_KEY is unset or still the default; sessions are "
        "signed with a known key. Fine for a feasibility deploy, not for "
        "skewnono.skhynix.com",
        False,
    )

    adapters = office_adapters(repo_root)
    add(
        "office_adapters",
        bool(adapters),
        "no providers/office.py found — every feature will serve mock data",
        False,
    )

    return checks


def blocking_failures(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.ok and c.blocking]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pack_deploy.py -v`

Expected: PASS — 12 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/pack_deploy.py tests/test_pack_deploy.py
git commit -m "feat(deploy): office-side preflight checks with feasibility severity

Blocking checks cover only what guarantees a dead deploy: missing built
SPA, missing .env, missing requirements.txt, missing include roots.

Everything else is advisory, because the first cloud deploy happens while
the mock→office transition is deliberately incomplete — refusing to pack an
incomplete transition would block exactly the deploy we want. A stale build,
a default SKEWNONO_SECRET_KEY and a total absence of office adapters all
warn and continue.

--strict promotes every advisory to blocking, for use once the transition
is complete and a mock-serving bundle should fail the build."
```

---

### Task 5: Copy and verify the bundle

**Files:**

- Modify: `scripts/pack_deploy.py`
- Test: `tests/test_pack_deploy.py`

**Interfaces:**

- Consumes: `INCLUDED_ROOTS`, `should_prune` from Task 3.
- Produces:
  - `copy_bundle(repo_root: Path, dest: Path) -> int` — returns files copied
  - `verify_bundle(dest: Path) -> list[str]` — failure strings, empty when OK

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pack_deploy.py`:

```python
def test_copy_preserves_the_depth_invariant(tmp_path):
    """env.py exactly 2 levels below root, or spa_dir() resolves wrong."""
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"

    pack_deploy.copy_bundle(repo, dest)

    env_py = dest / "back_dev_home" / "_runtime" / "env.py"
    assert env_py.is_file()
    assert env_py.resolve().parents[2] == dest.resolve()


def test_copy_places_the_spa_at_its_exact_path(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"

    pack_deploy.copy_bundle(repo, dest)

    assert (dest / "front-dev-home" / ".output" / "public" / "index.html").is_file()


def test_copy_prunes_pycache_and_tests(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "back_dev_home" / "__pycache__").mkdir()
    (repo / "back_dev_home" / "__pycache__" / "x.pyc").write_text("")
    (repo / "back_dev_home" / "sem_list" / "tests").mkdir(parents=True)
    (repo / "back_dev_home" / "sem_list" / "tests" / "test_x.py").write_text("")
    dest = tmp_path / "bundle"

    pack_deploy.copy_bundle(repo, dest)

    assert not list(dest.rglob("__pycache__"))
    assert not list(dest.rglob("test_x.py"))


def test_copy_keeps_gitignored_files_that_must_ship(tmp_path):
    repo = _make_repo(tmp_path)
    adapter = repo / "back_dev_home" / "sem_list" / "providers"
    adapter.mkdir(parents=True)
    (adapter / "office.py").write_text("# real adapter\n")
    dest = tmp_path / "bundle"

    pack_deploy.copy_bundle(repo, dest)

    assert (dest / "back_dev_home" / "sem_list" / "providers" / "office.py").is_file()
    assert (dest / "back_dev_home" / ".env").is_file()


def test_spa_output_is_copied_verbatim(tmp_path):
    """Nuxt output is opaque to our naming rules — a build asset named
    tests/ or ending in .md must not be pruned, or the SPA 404s at runtime
    with nothing failing at pack time."""
    repo = _make_repo(tmp_path)
    spa = repo / "front-dev-home" / ".output" / "public"
    (spa / "tests").mkdir()
    (spa / "tests" / "fixture.json").write_text("{}")
    (spa / "readme.md").write_text("# content")
    dest = tmp_path / "bundle"

    pack_deploy.copy_bundle(repo, dest)

    out = dest / "front-dev-home" / ".output" / "public"
    assert (out / "tests" / "fixture.json").is_file()
    assert (out / "readme.md").is_file()


def test_verify_passes_on_a_well_formed_bundle(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"
    pack_deploy.copy_bundle(repo, dest)

    assert pack_deploy.verify_bundle(dest) == []


def test_verify_catches_a_mangled_bundle(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"
    pack_deploy.copy_bundle(repo, dest)
    (dest / "front-dev-home" / ".output" / "public" / "index.html").unlink()

    assert pack_deploy.verify_bundle(dest) != []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pack_deploy.py -v`

Expected: FAIL — `AttributeError: module 'scripts.pack_deploy' has no attribute 'copy_bundle'`

- [ ] **Step 3: Implement copy and verify**

Add `import shutil` to the imports, then append to `scripts/pack_deploy.py`:

```python
def _ignore(directory: str, names: list[str]) -> set[str]:
    """shutil.copytree callback — drop pruned entries during the walk."""
    parent = Path(directory)
    return {name for name in names if should_prune(parent / name)}


# The Nuxt build output is already exactly what should ship, and it is opaque
# to our naming rules: a content file could legitimately be called tests/ or
# end in .md, and pruning it would break the SPA silently — the page would
# 404 an asset at runtime with nothing failing at pack time. So it is copied
# verbatim. Everything else goes through should_prune().
VERBATIM_ROOTS = frozenset({"front-dev-home/.output/public"})


def copy_bundle(repo_root: Path, dest: Path) -> int:
    """Copy every included root into `dest`, preserving relative depth."""
    dest.mkdir(parents=True, exist_ok=True)

    for rel in INCLUDED_ROOTS:
        source = repo_root / rel
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            ignore = None if rel in VERBATIM_ROOTS else _ignore
            shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)
        elif source.is_file():
            shutil.copy2(source, target)

    return sum(1 for p in dest.rglob("*") if p.is_file())


def verify_bundle(dest: Path) -> list[str]:
    """Check the bundle we just wrote, rather than trusting the copy logic.

    Catching a layout mistake here costs seconds; catching it on the cloud
    costs a full transfer round-trip.
    """
    failures = []

    env_py = dest / "back_dev_home" / "_runtime" / "env.py"
    if not env_py.is_file():
        failures.append(f"missing {env_py}")
    elif env_py.resolve().parents[2] != dest.resolve():
        failures.append(
            f"{env_py} is not 2 levels below the bundle root; spa_dir() will miss"
        )

    index_html = dest / "front-dev-home" / ".output" / "public" / "index.html"
    if not index_html.is_file():
        failures.append(f"missing {index_html}")

    for name in ("index.py", "wsgi.ini"):
        if not (dest / name).is_file():
            failures.append(f"missing {dest / name}")

    if list(dest.rglob("__pycache__")):
        failures.append("__pycache__ survived the prune")

    return failures
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pack_deploy.py -v`

Expected: PASS — 19 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/pack_deploy.py tests/test_pack_deploy.py
git commit -m "feat(deploy): copy the bundle and verify its layout

copy_bundle() preserves relative depth, which is load-bearing: is_cloud()
tests whether _runtime/env.py resolves under /project/workSpace and
spa_dir() walks parents[2], so a re-nested bundle loses auth, the SPA
mount and office detection while still answering 200.

verify_bundle() re-checks the tree that was actually written rather than
trusting the copy logic. Catching a layout mistake here costs seconds;
catching it on the cloud costs a transfer round-trip."
```

---

### Task 6: Manifest, runbook, and the CLI

**Files:**

- Modify: `scripts/pack_deploy.py`
- Test: `tests/test_pack_deploy.py`

**Interfaces:**

- Consumes: `Check`, `run_preflight`, `office_adapters`, `copy_bundle`, `verify_bundle`.
- Produces:
  - `git_provenance(repo_root: Path) -> dict[str, str]` — keys `sha`, `branch`, `dirty`
  - `write_manifest(dest, repo_root, checks, file_count, stamp) -> Path`
  - `write_runbook(dest: Path) -> Path`
  - `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pack_deploy.py`:

```python
def test_manifest_records_the_adapter_roster(tmp_path):
    repo = _make_repo(tmp_path)
    adapter = repo / "back_dev_home" / "sem_list" / "providers"
    adapter.mkdir(parents=True)
    (adapter / "office.py").write_text("")
    dest = tmp_path / "bundle"
    pack_deploy.copy_bundle(repo, dest)

    path = pack_deploy.write_manifest(
        dest, repo, pack_deploy.run_preflight(repo), 10, "20260724-1530"
    )

    assert "sem_list" in path.read_text()


def test_manifest_records_advisory_warnings(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"
    pack_deploy.copy_bundle(repo, dest)

    path = pack_deploy.write_manifest(
        dest, repo, pack_deploy.run_preflight(repo), 10, "20260724-1530"
    )

    assert "office_adapters" in path.read_text()


def test_runbook_names_preflight_before_uwsgi(tmp_path):
    dest = tmp_path / "bundle"
    dest.mkdir()

    text = pack_deploy.write_runbook(dest).read_text()

    assert text.index("preflight.py") < text.index("uwsgi --ini")


def test_main_exits_nonzero_when_a_blocking_check_fails(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "back_dev_home" / ".env").unlink()
    monkeypatch.chdir(repo)

    assert pack_deploy.main(["--out", str(tmp_path / "out")]) != 0


def test_main_writes_a_complete_bundle(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "preflight_cloud.py").write_text("# checker\n")
    monkeypatch.chdir(repo)
    out = tmp_path / "out"

    assert pack_deploy.main(["--out", str(out)]) == 0

    bundle = next(out.iterdir())
    assert (bundle / "preflight.py").is_file()
    assert (bundle / "MANIFEST.txt").is_file()
    assert (bundle / "DEPLOY.md").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pack_deploy.py -v`

Expected: FAIL — `AttributeError: module 'scripts.pack_deploy' has no attribute 'write_manifest'`

- [ ] **Step 3: Implement manifest, runbook, and CLI**

Add `import argparse`, `import os`, `import socket`, `import subprocess`, `import sys`, and `from datetime import datetime` to the imports, then append to `scripts/pack_deploy.py`:

```python
# Indented code blocks, not fenced ones: this string lives inside a fenced
# block in the plan document, and nested fences break the outer one.
RUNBOOK = """# Deploy this bundle

1. Copy this whole folder to `/project/workSpace/` on the cloud host.
   The path matters: `is_cloud()` tests whether `back_dev_home/_runtime/env.py`
   resolves under `/project/workSpace`. Anywhere else and the app starts with
   no SSO auth, no SPA mount, and mock data — while still answering HTTP 200.

2. Check the transfer landed correctly, before installing anything:

       cd /project/workSpace && python preflight.py

3. Install dependencies:

       pip install -r back_dev_home/requirements.txt

4. Run preflight again. Imports should now resolve, and it reports which
   `hcputil` module spelling this image provides:

       python preflight.py

5. Start the app:

       uwsgi --ini wsgi.ini        # or: python index.py

6. Verify which data providers actually engaged:

       curl localhost:5000/api/health/providers

   This endpoint deliberately bypasses the provider swap mechanism, so it is
   the honest answer to whether office mode is on.

`MANIFEST.txt` records what this bundle contains and any warnings raised
when it was packed.
"""


def git_provenance(repo_root: Path) -> dict[str, str]:
    """Best-effort. A bundle packed from a non-git export still packs."""
    def run(*args):
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return "unknown"
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    status = run("status", "--porcelain")
    return {
        "sha": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": "yes" if status not in ("", "unknown") else "no",
    }


def write_manifest(dest, repo_root, checks, file_count, stamp) -> Path:
    """Provenance record. The adapter roster is the point.

    Presence detection leaves no configuration line to read afterwards, so
    without this file there is no way to answer "what is actually running up
    there?" without shell access to the cloud host.
    """
    git = git_provenance(repo_root)
    adapters = office_adapters(repo_root)
    total_bytes = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    warnings = [c for c in checks if not c.ok]

    lines = [
        "SKEWNONO deployment bundle",
        f"packed:      {stamp}",
        f"host:        {socket.gethostname()}",
        f"git sha:     {git['sha']}",
        f"git branch:  {git['branch']}",
        f"uncommitted: {git['dirty']}",
        f"files:       {file_count}",
        f"size:        {total_bytes / 1_048_576:.1f} MiB",
        "",
        f"office adapters ({len(adapters)}) — these features serve real data:",
    ]
    lines += [f"  {name}" for name in adapters] or ["  (none — all mock)"]

    lines += ["", f"warnings at pack time ({len(warnings)}):"]
    lines += [f"  {c.name}: {c.message}" for c in warnings] or ["  (none)"]

    path = dest / "MANIFEST.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_runbook(dest: Path) -> Path:
    path = dest / "DEPLOY.md"
    path.write_text(RUNBOOK, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pack the working tree into a cloud deployment folder."
    )
    parser.add_argument("--out", type=Path, default=Path("dist"))
    parser.add_argument(
        "--build",
        action="store_true",
        help="run `npm run build` in front-dev-home/ first",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="promote every advisory check to blocking",
    )
    args = parser.parse_args(argv)

    repo_root = Path.cwd()

    if args.build:
        print("building the frontend...")
        result = subprocess.run(
            ["npm", "--prefix", str(repo_root / "front-dev-home"), "run", "build"]
        )
        if result.returncode != 0:
            print("FAIL frontend build failed")
            return 1

    checks = run_preflight(repo_root, strict=args.strict)
    for check in checks:
        if not check.ok:
            label = "FAIL" if check.blocking else "WARN"
            print(f"  {label} {check.name}: {check.message}")

    failures = blocking_failures(checks)
    if failures:
        print(f"\nFAIL — {len(failures)} blocking problem(s); nothing written.")
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    dest = args.out / f"skewnono-{stamp}"
    if dest.exists():
        shutil.rmtree(dest)

    file_count = copy_bundle(repo_root, dest)

    checker = repo_root / "scripts" / "preflight_cloud.py"
    if checker.is_file():
        shutil.copy2(checker, dest / "preflight.py")

    problems = verify_bundle(dest)
    if problems:
        print("\nFAIL — the bundle written is not well formed:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    write_manifest(dest, repo_root, checks, file_count, stamp)
    write_runbook(dest)

    os.chmod(dest, 0o700)

    warned = [c for c in checks if not c.ok]
    print(f"\nPASS — {file_count} files -> {dest}")
    if warned:
        print(f"  {len(warned)} warning(s) recorded in MANIFEST.txt:")
        for check in warned:
            print(f"    - {check.name}")
    print("\n  This bundle contains credentials:")
    print("    back_dev_home/.env")
    print("    minio_handler/minio_config.py")
    print("  The folder is chmod 700. Do not place it on shared storage.")
    print(f"\n  Next: copy {dest}/ to /project/workSpace/ then read DEPLOY.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pack_deploy.py -v`

Expected: PASS — 24 passed

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest tests/ back_dev_home/ -q`

Expected: PASS, no new failures

- [ ] **Step 6: Commit**

```bash
git add scripts/pack_deploy.py tests/test_pack_deploy.py
git commit -m "feat(deploy): manifest, runbook, and pack_deploy CLI

MANIFEST.txt records git provenance plus the roster of features with a
providers/office.py — which tabs will serve real data. Presence detection
leaves no config line to read afterwards, so this file is the only way to
answer 'what is actually running up there' without cloud shell access.
Pack-time warnings are copied into it verbatim.

DEPLOY.md orders preflight.py before uwsgi, and runs it twice: once before
pip install to prove the transfer landed at the right path, once after to
prove the install completed.

The output folder is chmod 700 and the run ends by naming the credential
files it copied."
```

---

### Task 7: Real bundle smoke test and deployment doc

**Files:**

- Create: `docs/deployment.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Pack a real bundle**

Run: `.venv/bin/python -m scripts.pack_deploy --out /tmp/skewnono-deploy-test`

Expected: exit 0. Warnings about `office_adapters` are normal only if no `office.py` exists locally; on the office PC 6 should be listed.

- [ ] **Step 2: Inspect what was produced**

```bash
BUNDLE=$(ls -d /tmp/skewnono-deploy-test/skewnono-*)
cat "$BUNDLE/MANIFEST.txt"
du -sh "$BUNDLE"
find "$BUNDLE" -name "__pycache__" -o -name "MIGRATION.md" -o -name "test_*.py" | head
```

Expected: manifest lists the adapter roster; size is roughly 10–11 MiB; the `find` prints nothing.

- [ ] **Step 3: Confirm the excluded packages really are absent**

```bash
BUNDLE=$(ls -d /tmp/skewnono-deploy-test/skewnono-*)
test ! -e "$BUNDLE/afm_data_platform" && test ! -e "$BUNDLE/ops_index_mgmt" && echo OK
```

Expected: `OK`

- [ ] **Step 4: Run the bundled preflight against the bundle**

```bash
BUNDLE=$(ls -d /tmp/skewnono-deploy-test/skewnono-*)
cd "$BUNDLE" && python preflight.py; cd -
```

Expected: exit 1 with exactly one `FAIL PATH` line, because `/tmp/...` is not under `/project/workSpace`. Every other check passes. This is the correct result and confirms the path check works.

- [ ] **Step 5: Confirm the app imports from inside the bundle**

```bash
BUNDLE=$(ls -d /tmp/skewnono-deploy-test/skewnono-*)
cd "$BUNDLE" && "$OLDPWD/.venv/bin/python" -c "
from back_dev_home._runtime.env import spa_dir
assert spa_dir().joinpath('index.html').is_file(), spa_dir()
print('spa_dir resolves inside the bundle:', spa_dir())
"; cd -
```

Expected: prints the bundle's SPA path. This proves the depth invariant end to end.

- [ ] **Step 6: Write the deployment doc**

Create `docs/deployment.md` in Korean, per the CLAUDE.md rule that `docs/` intended for teammate sharing is written in Korean with `~입니다.` / `~합니다.` endings. Cover: the three-step flow, what the bundle contains and why `afm_data_platform`/`ops_index_mgmt` are excluded, the `/project/workSpace` path requirement, the four cloud-side setup items (unpack path, `hcputil` availability, SSO hostname registration, `SKEWNONO_SECRET_KEY`), the two-URL note that no rebuild is needed at cutover, and the `preflight.py` → `pip install` → `preflight.py` → `uwsgi` order. Use markdownlint `MD060` `compact` table style.

- [ ] **Step 7: Add a deployment section to CLAUDE.md**

Add under "Development Notes", after the Git Workflow section:

```markdown
### Deployment (Phase 3)

Pack at the office, from the repo root, after building the frontend:

    npm --prefix front-dev-home run build
    .venv/bin/python -m scripts.pack_deploy

Produces `dist/skewnono-<stamp>/`. Copy it to `/project/workSpace/` on the
cloud host — that exact path, because `is_cloud()` is a filesystem check, not
a config flag — then follow the bundle's `DEPLOY.md`. Run its `preflight.py`
before starting uwsgi. See `docs/deployment.md`.
```

- [ ] **Step 8: Lint the markdown**

Run: `npm run lint:md`

Expected: `Summary: 0 error(s)`

- [ ] **Step 9: Clean up and commit**

```bash
rm -rf /tmp/skewnono-deploy-test
git add docs/deployment.md CLAUDE.md
git commit -m "docs(deploy): office→cloud deployment runbook

Documents the build → pack → copy → run flow, what the bundle carries and
why afm_data_platform and ops_index_mgmt are excluded, and the four
cloud-side setup items found while tracing the auth path: unpack at
/project/workSpace, confirm hcputil is on the image, register each hostname
with SSO, and set a real SKEWNONO_SECRET_KEY.

Also records that the SPA calls /api relative and Flask serves it
same-origin, so one bundle works on both the aipp01 test host and
skewnono.skhynix.com with no rebuild at cutover."
```

---

## Verification Checklist

After all tasks:

- [ ] `.venv/bin/python -m pytest tests/ back_dev_home/ -q` passes
- [ ] `npm run lint:md` reports 0 errors
- [ ] A real bundle packs, and `spa_dir()` resolves inside it
- [ ] `preflight.py` fails only on the `/project/workSpace` check when run locally
- [ ] `MANIFEST.txt` lists the office adapters present on the packing machine
