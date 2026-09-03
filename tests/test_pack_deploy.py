"""Packing rules for the office → cloud bundle."""

import os
import stat
from pathlib import Path

from scripts.deploy import pack


def test_includes_the_vendored_packages_the_app_imports():
    """office_utils rides along for recipe open's deferred 사내 parser import."""
    for name in ("ops_store", "minio_handler", "ftp_handler", "office_utils"):
        assert name in pack.INCLUDED_ROOTS


def test_excludes_packages_the_app_never_imports():
    """afm_data_platform is 1.8MB of spec; ops_index_mgmt is index tooling."""
    for name in ("afm_data_platform", "ops_index_mgmt", "docs"):
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
    for name in ("ops_store", "minio_handler", "ftp_handler", "office_utils"):
        (root / name).mkdir()
        (root / name / "__init__.py").write_text("")
    (root / "office_utils" / "read_idp_info.py").write_text("")
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


def test_preflight_flags_an_office_logging_target_before_it_travels(tmp_path):
    """The one exception to "pack does not inspect .env values".

    SKEWNONO_LOG_ENV is not content, it is a property of the machine, and
    back_dev_home is copied wholesale — so packing at the office is the moment
    an office-only value starts travelling to the cloud. The cloud's own
    preflight fails on it as well, but only after the transfer, which on a
    host with a slow iteration loop is the difference worth having.
    """
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=k\nSKEWNONO_LOG_ENV=local\n"
    )

    checks = pack.run_preflight(root)

    target = next(c for c in checks if c.name == "logging_target")
    assert not target.ok
    assert "production" in target.message


def test_preflight_accepts_a_bundle_that_names_the_production_target(tmp_path):
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").write_text(
        "SKEWNONO_SECRET_KEY=k\nSKEWNONO_LOG_ENV=production\n"
    )

    checks = pack.run_preflight(root)

    assert next(c for c in checks if c.name == "logging_target").ok


def test_preflight_leaves_an_unset_logging_target_to_the_cloud(tmp_path):
    """Unset is not an office value travelling anywhere — it is a decision not
    yet made, which the cloud's preflight reports against the .env that ends up
    there. Failing here would block a deploy whose operator sets it after
    transfer."""
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").write_text("SKEWNONO_SECRET_KEY=k\n")

    checks = pack.run_preflight(root)

    assert next(c for c in checks if c.name == "logging_target").ok


def test_office_logging_target_is_advisory_not_blocking(tmp_path):
    """Advisory because the operator may intend to edit the bundle's .env after
    the copy; --strict promotes it for a real production pack."""
    root = _make_repo(tmp_path)
    (root / "back_dev_home" / ".env").write_text("SKEWNONO_LOG_ENV=local\n")

    assert not any(
        f.name == "logging_target" for f in pack.blocking_failures(pack.run_preflight(root))
    )
    assert any(
        f.name == "logging_target"
        for f in pack.blocking_failures(pack.run_preflight(root, strict=True))
    )


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


def test_copy_keeps_rag_database_but_prunes_chat_threads(tmp_path):
    repo = _make_repo(tmp_path)
    rag_index = repo / "back_dev_home" / "chat" / "_rag" / "skewnono_rag" / "index"
    rag_index.mkdir(parents=True)
    (rag_index / "store.db").write_text("rag index")
    (repo / "back_dev_home" / "chat" / "chat.db").write_text("local threads")
    dest = tmp_path / "bundle"

    pack.copy_bundle(repo, dest)

    assert (dest / rag_index.relative_to(repo) / "store.db").is_file()
    assert not (dest / "back_dev_home" / "chat" / "chat.db").exists()


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


def test_verify_catches_a_missing_idp_parser(tmp_path):
    """copy_bundle skips an absent root silently; recipe open then 500s on
    the cloud with nothing failing at pack time. verify must name it."""
    repo = _make_repo(tmp_path)
    (repo / "office_utils" / "read_idp_info.py").unlink()
    dest = tmp_path / "bundle"
    pack.copy_bundle(repo, dest)

    assert any("read_idp_info" in f for f in pack.verify_bundle(dest))


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


def test_main_packs_the_named_root_from_a_foreign_cwd(tmp_path, monkeypatch):
    """`--repo-root` is what makes the by-path invocation usable.

    Double-clicking the file, or running it via an absolute path from a home
    directory, leaves cwd somewhere unrelated. Before this flag the only
    remedy was to know that cwd - never mentioned in the output - was the
    thing being packed.
    """
    repo = _make_repo(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    out = tmp_path / "out"

    assert pack.main(["--out", str(out), "--repo-root", str(repo)]) == 0

    bundle = next(out.iterdir())
    assert (bundle / "back_dev_home" / "_runtime" / "env.py").is_file()


def test_main_rejects_a_cwd_that_is_not_a_checkout(tmp_path, monkeypatch, capsys):
    """One line naming the cause, not four naming its symptoms.

    Running from the wrong directory used to emit a blocking failure per
    missing root, each quoting a path under that wrong directory - which reads
    as a broken repo rather than a mislaid `cd`.
    """
    monkeypatch.chdir(tmp_path)

    assert pack.main(["--out", str(tmp_path / "out")]) == 1

    out = capsys.readouterr().out
    assert "not a skewnono checkout" in out
    assert "--repo-root" in out
    assert "spa_built" not in out, "symptom-level checks must not run at all"


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


def _adapter(root: Path, slug: str, template: str, copy: str | None) -> None:
    providers = root / "back_dev_home" / slug / "providers"
    providers.mkdir(parents=True, exist_ok=True)
    (providers / "office_example.py").write_text(template)
    if copy is not None:
        (providers / "office.py").write_text(copy)


def test_an_office_copy_matching_its_template_raises_nothing(tmp_path):
    root = _make_repo(tmp_path)
    _adapter(root, "sem_list", "X = 1\n", "X = 1\n")
    stale, edited = pack.adapter_drift(root)
    assert (stale, edited) == ([], [])


def test_a_differing_office_copy_is_named_before_the_bundle_leaves(tmp_path):
    """The whole reason this check runs at pack time.

    `.git` is in PRUNE_DIRS, and office_template needs a clone to tell STALE
    from EDITED — so on the cloud every differing copy answers EDITED and the
    boot-time STALE warning can never fire. This tmp tree has no `.git`
    either, which is exactly why it reproduces the cloud's blind spot: the
    copy below is out of date, and without git the best anyone can say is
    "it differs". Saying that at the office is still worth more than saying
    nothing on a host no one can inspect.
    """
    root = _make_repo(tmp_path)
    _adapter(root, "msr_image", "TRANSPORT = 'direct'\n", "TRANSPORT = 'proxy'\n")
    stale, edited = pack.adapter_drift(root)
    assert "msr_image" in edited
    assert stale == []


def test_a_missing_office_copy_is_not_drift(tmp_path):
    """No office.py means the feature serves mock — office_adapters already
    reports that, and it is not a copy that drifted."""
    root = _make_repo(tmp_path)
    _adapter(root, "afm", "X = 1\n", None)
    assert pack.adapter_drift(root) == ([], [])


def test_adapter_drift_is_advisory_not_blocking(tmp_path):
    """An EDITED copy is usually the legitimate 사내 case, so it must not
    refuse a deploy — it only has to be said out loud while it still can be."""
    root = _make_repo(tmp_path)
    _adapter(root, "msr_image", "A = 1\n", "A = 2\n")
    checks = pack.run_preflight(root)
    named = {c.name: c for c in checks}
    assert named["adapters_reviewed"].ok is False
    assert named["adapters_reviewed"].blocking is False
    assert not pack.blocking_failures(checks)


def test_drift_warnings_reach_the_manifest_the_cloud_reads(tmp_path):
    """MANIFEST.txt is the only provenance that survives the transfer, so a
    warning that stops here helps nobody."""
    root = _make_repo(tmp_path)
    _adapter(root, "msr_image", "A = 1\n", "A = 2\n")
    dest = tmp_path / "bundle"
    dest.mkdir()
    manifest = pack.write_manifest(dest, root, pack.run_preflight(root), 1, "now")
    assert "adapters_reviewed" in manifest.read_text(encoding="utf-8")
