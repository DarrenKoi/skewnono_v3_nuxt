"""Packing rules for the office → cloud bundle."""

import os
import stat
from pathlib import Path

from scripts.deploy import pack


def test_includes_the_three_vendored_packages_the_app_imports():
    for name in ("ops_store", "minio_handler", "ftp_handler"):
        assert name in pack.INCLUDED_ROOTS


def test_excludes_packages_the_app_never_imports():
    """afm_data_platform is 1.8MB of spec; ops_index_mgmt is index tooling."""
    for name in ("afm_data_platform", "ops_index_mgmt", "docs", "openwiki"):
        assert name not in pack.INCLUDED_ROOTS


def test_includes_the_built_spa_at_its_exact_path():
    assert "front-dev-home/.output/public" in pack.INCLUDED_ROOTS


def test_excludes_permanent_cloud_root_files():
    for name in ("index.py", "wsgi.ini"):
        assert name not in pack.INCLUDED_ROOTS


def test_prunes_pycache_and_tests():
    assert pack.should_prune(Path("back_dev_home/__pycache__"))
    assert pack.should_prune(Path("back_dev_home/sem_list/tests"))
    assert pack.should_prune(Path("back_dev_home/conftest.py"))


def test_prunes_markdown_and_compiled_files():
    assert pack.should_prune(Path("back_dev_home/sem_list/MIGRATION.md"))
    assert pack.should_prune(Path("back_dev_home/x.pyc"))
    assert pack.should_prune(Path("back_dev_home/.DS_Store"))


def test_keeps_the_files_that_must_ship():
    """office.py and .env are gitignored — losing them is the failure mode."""
    assert not pack.should_prune(Path("back_dev_home/sem_list/providers/office.py"))
    assert not pack.should_prune(Path("back_dev_home/.env"))
    assert not pack.should_prune(Path("back_dev_home/requirements.txt"))
    assert not pack.should_prune(Path("minio_handler/minio_config.py"))


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
    checks = pack.run_preflight(_make_repo(tmp_path))
    assert pack.blocking_failures(checks) == []


def test_preflight_does_not_require_permanent_cloud_root_files(tmp_path):
    root = _make_repo(tmp_path)
    (root / "index.py").unlink()
    (root / "wsgi.ini").unlink()

    assert pack.blocking_failures(pack.run_preflight(root)) == []


def test_missing_spa_blocks(tmp_path):
    root = _make_repo(tmp_path)
    (root / "front-dev-home" / ".output" / "public" / "index.html").unlink()

    failures = pack.blocking_failures(pack.run_preflight(root))

    assert any("index.html" in f.message for f in failures)


def test_missing_env_blocks(tmp_path):
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").unlink()

    failures = pack.blocking_failures(pack.run_preflight(root))

    assert any(".env" in f.message for f in failures)


def test_no_office_adapters_is_advisory_not_blocking(tmp_path):
    """The transition is deliberately incomplete during the feasibility deploy."""
    root = _make_repo(tmp_path)

    checks = pack.run_preflight(root)

    adapter = next(c for c in checks if c.name == "office_adapters")
    assert not adapter.ok
    assert not adapter.blocking
    assert pack.blocking_failures(checks) == []


def test_strict_promotes_advisories_to_blocking(tmp_path):
    root = _make_repo(tmp_path)

    failures = pack.blocking_failures(
        pack.run_preflight(root, strict=True)
    )

    assert any(f.name == "office_adapters" for f in failures)


def test_preflight_does_not_inspect_env_values(tmp_path):
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=dev-only-not-for-prod\n"
    )

    checks = pack.run_preflight(root)

    assert "secret_key" not in {check.name for check in checks}


def _set_build_times(root: Path, source: float, build: float) -> None:
    """Give front-dev-home/app one source file, then pin both sides' mtimes.

    Absolute epochs, minutes apart: build_fresh compares mtimes with >=, so
    writing the files in order and trusting the clock would ride on filesystem
    timestamp granularity.
    """
    source_file = root / "front-dev-home" / "app" / "pages" / "index.vue"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("<template />")
    os.utime(source_file, (source, source))

    spa_index = root / "front-dev-home" / ".output" / "public" / "index.html"
    os.utime(spa_index, (build, build))


def test_a_build_older_than_the_sources_is_advisory(tmp_path):
    """You ship yesterday's UI silently: the SPA is present and every blocking
    check passes, so only this advisory stands between a stale .output/ and
    production."""
    root = _make_repo(tmp_path)
    _set_build_times(root, source=2_000_000_000, build=1_999_999_000)

    checks = pack.run_preflight(root)

    fresh = next(c for c in checks if c.name == "build_fresh")
    assert not fresh.ok
    assert not fresh.blocking
    assert pack.blocking_failures(checks) == []


def test_a_build_newer_than_the_sources_passes(tmp_path):
    root = _make_repo(tmp_path)
    _set_build_times(root, source=2_000_000_000, build=2_000_000_060)

    checks = pack.run_preflight(root)

    assert next(c for c in checks if c.name == "build_fresh").ok


def test_no_app_directory_is_not_reported_as_a_stale_build(tmp_path):
    """Packing from an export that carries only .output/ must not warn about a
    freshness it cannot measure."""
    root = _make_repo(tmp_path)
    (root / "front-dev-home" / "app").rmdir()

    checks = pack.run_preflight(root)

    assert next(c for c in checks if c.name == "build_fresh").ok


def test_copy_preserves_the_depth_invariant(tmp_path):
    """env.py exactly 2 levels below root, or spa_dir() resolves wrong."""
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"

    pack.copy_bundle(repo, dest)

    env_py = dest / "back_dev_home" / "_runtime" / "env.py"
    assert env_py.is_file()
    assert env_py.resolve().parents[2] == dest.resolve()


def test_copy_omits_permanent_cloud_root_files(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"

    pack.copy_bundle(repo, dest)

    assert not (dest / "index.py").exists()
    assert not (dest / "wsgi.ini").exists()


def test_copy_places_the_spa_at_its_exact_path(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"

    pack.copy_bundle(repo, dest)

    assert (dest / "front-dev-home" / ".output" / "public" / "index.html").is_file()


def test_copy_prunes_pycache_and_tests(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "back_dev_home" / "__pycache__").mkdir()
    (repo / "back_dev_home" / "__pycache__" / "x.pyc").write_text("")
    (repo / "back_dev_home" / "sem_list" / "tests").mkdir(parents=True)
    (repo / "back_dev_home" / "sem_list" / "tests" / "test_x.py").write_text("")
    dest = tmp_path / "bundle"

    pack.copy_bundle(repo, dest)

    assert not list(dest.rglob("__pycache__"))
    assert not list(dest.rglob("test_x.py"))


def test_copy_keeps_gitignored_files_that_must_ship(tmp_path):
    repo = _make_repo(tmp_path)
    adapter = repo / "back_dev_home" / "sem_list" / "providers"
    adapter.mkdir(parents=True)
    (adapter / "office.py").write_text("# real adapter\n")
    dest = tmp_path / "bundle"

    pack.copy_bundle(repo, dest)

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

    pack.copy_bundle(repo, dest)

    out = dest / "front-dev-home" / ".output" / "public"
    assert (out / "tests" / "fixture.json").is_file()
    assert (out / "readme.md").is_file()


def test_verify_passes_on_a_well_formed_bundle(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"
    pack.copy_bundle(repo, dest)

    assert pack.verify_bundle(dest) == []


def test_verify_catches_a_mangled_bundle(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"
    pack.copy_bundle(repo, dest)
    (dest / "front-dev-home" / ".output" / "public" / "index.html").unlink()

    assert pack.verify_bundle(dest) != []


def test_manifest_records_the_adapter_roster(tmp_path):
    repo = _make_repo(tmp_path)
    adapter = repo / "back_dev_home" / "sem_list" / "providers"
    adapter.mkdir(parents=True)
    (adapter / "office.py").write_text("")
    dest = tmp_path / "bundle"
    pack.copy_bundle(repo, dest)

    path = pack.write_manifest(
        dest, repo, pack.run_preflight(repo), 10, "20260724-1530"
    )

    assert "sem_list" in path.read_text()


def test_manifest_records_advisory_warnings(tmp_path):
    repo = _make_repo(tmp_path)
    dest = tmp_path / "bundle"
    pack.copy_bundle(repo, dest)

    path = pack.write_manifest(
        dest, repo, pack.run_preflight(repo), 10, "20260724-1530"
    )

    assert "office_adapters" in path.read_text()


def test_runbook_names_preflight_before_uwsgi(tmp_path):
    dest = tmp_path / "bundle"
    dest.mkdir()

    text = pack.write_runbook(dest).read_text()

    assert text.index("preflight.py") < text.index("uwsgi --ini")


def test_main_exits_nonzero_when_a_blocking_check_fails(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "back_dev_home" / ".env").unlink()
    monkeypatch.chdir(repo)

    assert pack.main(["--out", str(tmp_path / "out")]) != 0


def test_main_writes_a_complete_bundle(tmp_path, monkeypatch):
    """Note there is no fake scripts/preflight_cloud.py in this tree: the
    checker ships from the packer's own package, not from the tree being
    packed, so a repo without one still gets a complete bundle."""
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    out = tmp_path / "out"

    assert pack.main(["--out", str(out)]) == 0

    bundle = next(out.iterdir())
    assert (bundle / "MANIFEST.txt").is_file()
    assert (bundle / "DEPLOY.md").is_file()

    shipped = bundle / "preflight.py"
    assert shipped.is_file()
    assert (
        shipped.read_text(encoding="utf-8")
        == (Path(pack.__file__).parent / "preflight_cloud.py").read_text(
            encoding="utf-8"
        )
    ), "the bundled checker must be the real one, byte for byte"


def test_main_locks_down_the_bundle_folder(tmp_path, monkeypatch):
    """The bundle carries back_dev_home/.env and minio_handler/minio_config.py.

    main() prints three lines telling the operator so, and DEPLOY.md tells them
    to re-apply mode 700 after the copy — both of which read as reassurance
    that the folder written here is already locked down. If the chmod were
    dropped, a bundle sitting on an office PC under the default umask would be
    world-readable with nothing announcing it.
    """
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    out = tmp_path / "out"

    assert pack.main(["--out", str(out)]) == 0

    bundle = next(out.iterdir())
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o700


def test_ignore_callback_is_not_poisoned_by_the_checkout_path():
    """copytree passes an ABSOLUTE source dir. If the prune decision consulted
    ancestors, a checkout living under any directory named `tests` (or
    __pycache__, .pytest_cache, .ruff_cache) would prune every file in the
    bundle. Regression: this emptied back_dev_home down to 3 files."""
    pruned = pack._ignore(
        "/Users/someone/tests/skewnono_v3_nuxt/back_dev_home/sem_list",
        ["routes.py", "data.py", "contracts.py", "__init__.py", "providers"],
    )

    assert pruned == set()


def test_ignore_callback_still_prunes_by_entry_name():
    pruned = pack._ignore(
        "/anywhere/back_dev_home",
        ["routes.py", "__pycache__", "tests", "MIGRATION.md", "conftest.py"],
    )

    assert pruned == {"__pycache__", "tests", "MIGRATION.md", "conftest.py"}


def test_copy_survives_a_checkout_under_a_directory_named_tests(tmp_path):
    """End-to-end guard for the same bug, at the path shape that triggers it."""
    nest = tmp_path / "tests"
    nest.mkdir()
    repo = _make_repo(nest)
    (repo / "back_dev_home" / "sem_list").mkdir(parents=True)
    (repo / "back_dev_home" / "sem_list" / "routes.py").write_text("# real code\n")
    dest = tmp_path / "bundle"

    pack.copy_bundle(repo, dest)

    assert (dest / "back_dev_home" / "sem_list" / "routes.py").is_file()
    assert pack.verify_bundle(dest) == []


def test_git_provenance_does_not_claim_a_clean_tree_when_git_fails(tmp_path):
    """sha=unknown next to uncommitted=no reads as a verified-clean build."""
    provenance = pack.git_provenance(tmp_path / "not-a-repo")

    assert provenance["dirty"] != "no"
