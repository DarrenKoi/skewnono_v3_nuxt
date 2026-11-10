import subprocess
from pathlib import Path

from scripts.deploy import pack_copy
from tests.test_pack_deploy import _make_repo


def _git_target(tmp_path: Path) -> Path:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    return target


def test_sync_ships_env_despite_the_source_gitignore(tmp_path):
    """backend/.gitignore lists .env; copied along, it would hide the file
    from the target's commit. The synced tree must commit it."""
    repo = _make_repo(tmp_path)
    (repo / "backend" / ".gitignore").write_text(".env\n")
    target = _git_target(tmp_path)
    (target / "backend").mkdir()
    (target / "backend" / "removed_upstream.py").write_text("")
    (target / "index.py").write_text("permanent")

    assert pack_copy.main(["--repo-root", str(repo), "--target", str(target)]) == 0

    assert (target / "backend" / ".env").is_file()
    assert not (target / "backend" / ".gitignore").exists()
    assert not (target / "backend" / "removed_upstream.py").exists()
    assert (target / "index.py").read_text() == "permanent"
    assert (target / "preflight.py").is_file()
    assert (target / "MANIFEST.txt").is_file()
    assert (target / ".git").is_dir()


def test_target_gitignore_hiding_a_deploy_file_blocks(tmp_path):
    repo = _make_repo(tmp_path)
    target = _git_target(tmp_path)
    (target / ".gitignore").write_text(".env\n")

    assert pack_copy.main(["--repo-root", str(repo), "--target", str(target)]) != 0


def test_a_target_that_is_not_a_git_checkout_is_refused(tmp_path):
    repo = _make_repo(tmp_path)
    target = tmp_path / "plain"
    target.mkdir()

    assert pack_copy.main(["--repo-root", str(repo), "--target", str(target)]) != 0
    assert not (target / "backend").exists()
