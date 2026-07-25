"""The deploy-path primitives: is_cloud(), project_root(), spa_dir().

One filesystem question — "does this file resolve under /project/workSpace?" —
decides three unrelated things at once: SSO auth, the SPA mount, and office
site detection. Nothing else in the app can compensate for it being wrong,
because a misplaced bundle still answers HTTP 200.

These tests copy the real env.py into a throwaway tree and load THAT copy,
rather than stubbing the function out. is_cloud() is a statement about where a
file lives, so relocating the file is the only way to exercise it; a stub would
assert nothing about the mechanism the deploy actually depends on. The real
prefix is an absolute host path no test may create, so each copy gets
CLOUD_PREFIX repointed at its own tmp_path — which leaves the prefix VALUE
unexercised, hence the constants section.

One test does stub: the precedence test at the bottom, where the point is that
is_cloud() is never reached at all.

Each copy is loaded outside sys.modules and carries its own lru_cache, so no
test here can poison another's is_cloud() — nor the real module's, which the
app factory memoizes at boot.
"""

import importlib.util
from pathlib import Path

import pytest

from back_dev_home._runtime import env, site

# env.py's location relative to the repo root. preflight_cloud.check_layout()
# hardcodes the same segments to check a bundle; the constants section below
# pins the two together.
ENV_PY_REL = Path("back_dev_home") / "_runtime" / "env.py"


def _relocate(root: Path, prefix: Path):
    """Copy the real env.py to root/back_dev_home/_runtime/env.py and load it.

    Mirrors what pack_deploy.copy_bundle() writes, so the loaded module sees
    exactly the depth a deployed bundle has. env.py imports nothing from the
    package, so loading it standalone is faithful.
    """
    target = root / ENV_PY_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(env.__file__).read_bytes())

    spec = importlib.util.spec_from_file_location("skewnono_relocated_env", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # not registered in sys.modules
    module.CLOUD_PREFIX = prefix  # nothing has called is_cloud() yet
    return module


def _write_spa(root: Path) -> Path:
    """The one file spa_dir() has to land on for any SPA route to resolve."""
    spa = root / "front-dev-home" / ".output" / "public"
    spa.mkdir(parents=True)
    spa.joinpath("index.html").write_text("<!doctype html>")
    return spa


# ------------------------------------------------------------------ constants

def test_the_cloud_prefix_is_the_documented_deploy_path():
    """Every other test here repoints CLOUD_PREFIX at tmp_path, so nothing else
    exercises the literal — and it is the whole contract: DEPLOY.md, CLAUDE.md
    and docs/deployment.md all tell the operator to copy the bundle to exactly
    this path because the check is filesystem-based, not configuration."""
    assert env.CLOUD_PREFIX == Path("/project/workSpace")


def test_the_cloud_prefix_agrees_with_the_bundles_own_preflight():
    """preflight_cloud.py is STDLIB ONLY — it runs before pip install and so
    cannot import env.py — which means it keeps a second copy of the prefix.
    Two copies that disagree give a bundle that passes preflight and then boots
    without auth, or the reverse. Imported locally: back_dev_home must not
    depend on scripts/ anywhere but here.
    """
    from scripts import preflight_cloud

    assert preflight_cloud.CLOUD_PREFIX == env.CLOUD_PREFIX


# ------------------------------------------------------------------- is_cloud

def test_a_bundle_unpacked_into_the_cloud_prefix_is_cloud(tmp_path):
    """The Phase 3 layout: the bundle's contents land directly in the prefix,
    so env.py resolves under it."""
    workspace = tmp_path / "workSpace"
    relocated = _relocate(workspace, prefix=workspace)

    assert relocated.is_cloud() is True


def test_a_bundle_unpacked_anywhere_else_is_not_cloud(tmp_path):
    """The deploy's central gotcha. Landing the bundle in a home directory
    instead of the prefix gives no SSO auth, no SPA and mock data — while
    still serving HTTP 200."""
    relocated = _relocate(tmp_path / "home" / "skewnono", prefix=tmp_path / "workSpace")

    assert relocated.is_cloud() is False


def test_a_sibling_whose_name_starts_with_the_prefix_is_not_cloud(tmp_path):
    """/project/workSpace-old must not read as /project/workSpace. The check is
    path-component-wise for this reason; a string startswith() would pass a
    rollback copy off as the live deploy."""
    relocated = _relocate(tmp_path / "workSpace-old", prefix=tmp_path / "workSpace")

    assert relocated.is_cloud() is False


def test_a_bundle_nested_below_the_prefix_is_still_cloud(tmp_path):
    """Copying the whole `skewnono-<stamp>/` folder in, rather than its
    contents, keeps cloud mode on — is_relative_to() is not depth-limited. It
    breaks spa_dir() instead, which is what preflight.py checks."""
    workspace = tmp_path / "workSpace"
    relocated = _relocate(workspace / "skewnono-20260724-1530", prefix=workspace)

    assert relocated.is_cloud() is True


def test_is_cloud_is_decided_once_per_process(tmp_path):
    """Memoized on purpose: the answer cannot change while a process runs, and
    auth/SPA/site all ask it repeatedly. Pinned because it is a footgun for
    whoever writes the next test here — repointing CLOUD_PREFIX after the
    first call does nothing, which is why these tests load fresh copies."""
    workspace = tmp_path / "workSpace"
    relocated = _relocate(workspace, prefix=tmp_path / "elsewhere")
    assert relocated.is_cloud() is False

    relocated.CLOUD_PREFIX = workspace

    assert relocated.is_cloud() is False
    relocated.is_cloud.cache_clear()
    assert relocated.is_cloud() is True


# -------------------------------------------------- project_root / spa_dir

def test_project_root_is_the_repo_root():
    """parents[2] is the depth invariant, asserted here against real marker
    files. Move env.py one directory and this fails loudly at test time
    instead of as a 404 on every SPA route on the cloud host."""
    root = env.project_root()

    assert (root / ENV_PY_REL).resolve() == Path(env.__file__).resolve()
    assert (root / "index.py").is_file()  # the WSGI entry lives at the root
    assert (root / "front-dev-home").is_dir()


def test_spa_dir_is_the_nuxt_output_under_the_repo_root():
    """The path pack_deploy.INCLUDED_ROOTS ships verbatim; both must name the
    same three segments or the bundle mounts nothing."""
    assert env.spa_dir().relative_to(env.project_root()) == Path(
        "front-dev-home/.output/public"
    )


def test_a_relocated_bundle_reports_its_own_root_and_spa(tmp_path):
    """project_root() follows the file, not the packing machine — the bundle
    is unpacked on a host that has never seen this checkout."""
    workspace = tmp_path / "workSpace"
    relocated = _relocate(workspace, prefix=workspace)
    spa = _write_spa(workspace)

    assert relocated.project_root() == workspace
    assert relocated.spa_dir() == spa
    assert relocated.spa_dir().joinpath("index.html").is_file()


def test_env_py_one_level_too_deep_loses_the_spa(tmp_path):
    """Why depth is load-bearing, stated as one assertion triple.

    parents[2] is a count, not a search: put env.py one directory deeper than
    the SPA — a package refactor here, or a copy that keeps back_dev_home
    under a wrapper directory — and it still resolves under the prefix, so
    cloud mode is on and the SPA is expected to mount. project_root() then
    names the wrapper and spa_dir() finds nothing: every route 404s with
    nothing having failed at pack time. This is the shape verify_bundle() and
    preflight.py exist to reject — pinned here at the source, so a layout
    change fails in this suite rather than on the cloud host.
    """
    workspace = tmp_path / "workSpace"
    relocated = _relocate(workspace / "extra", prefix=workspace)
    _write_spa(workspace)

    assert relocated.is_cloud() is True
    assert relocated.project_root() == workspace / "extra"
    assert not relocated.spa_dir().exists()


# ------------------------------------------------------- is_cloud precedence

def test_an_invalid_site_env_raises_before_the_cloud_path_is_consulted(monkeypatch):
    """A typo in SKEWNONO_SITE must not be swallowed by production.

    is_cloud() answers "office" for the cloud deploy path, so a check ordered
    the other way round would let `SKEWNONO_SITE=offcie` boot silently on the
    one host where nobody is watching a terminal. Lives with the is_cloud()
    tests because it is a statement about that function's precedence.
    """
    consulted = []

    def spy_is_cloud() -> bool:
        consulted.append("is_cloud")
        return True

    monkeypatch.setattr(site, "is_cloud", spy_is_cloud)
    monkeypatch.setenv("SKEWNONO_SITE", "offcie")

    with pytest.raises(RuntimeError) as exc:
        site.detect_site()

    assert "SKEWNONO_SITE" in str(exc.value)
    assert consulted == []
