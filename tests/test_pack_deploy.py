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
