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
