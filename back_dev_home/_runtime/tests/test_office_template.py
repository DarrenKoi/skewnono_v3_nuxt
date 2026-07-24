"""STALE vs EDITED classification of providers/office.py copies.

These tests build a real throwaway git repo rather than mocking subprocess:
the whole value of the module is that it asks git a question a filesystem
compare cannot answer, so a fake git would test nothing.
"""

import subprocess

import pytest

from back_dev_home._runtime import office_template
from back_dev_home._runtime.office_template import (
    EDITED,
    MISSING,
    STALE,
    SYNCED,
)


def _git(repo, *args):
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo),
        },
    )


@pytest.fixture
def repo(tmp_path):
    """A repo with back_dev_home/sem_list/providers/office_example.py committed."""
    _git(tmp_path, "init", "-q", "-b", "main")
    providers = tmp_path / "back_dev_home" / "sem_list" / "providers"
    providers.mkdir(parents=True)
    (providers / "office_example.py").write_text("VERSION = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "first template")
    return tmp_path


@pytest.fixture
def adapter(repo):
    backend = repo / "back_dev_home"
    found = office_template.discover(backend)
    assert len(found) == 1
    return found[0]


def _classify(adapter, repo):
    return office_template.classify(adapter, repo_root=repo)


def test_no_copy_yet_is_missing(adapter, repo):
    assert _classify(adapter, repo) == (MISSING, "")


def test_byte_identical_copy_is_synced(adapter, repo):
    adapter.target.write_bytes(adapter.template.read_bytes())
    assert _classify(adapter, repo) == (SYNCED, "")


def test_copy_of_an_older_committed_template_is_stale(adapter, repo):
    # The copy is made, THEN the template moves ahead — the git pull scenario.
    adapter.target.write_bytes(adapter.template.read_bytes())
    adapter.template.write_text("VERSION = 2\n")
    _git(repo, "commit", "-qam", "template moves ahead")

    status, note = _classify(adapter, repo)
    assert status == STALE
    assert note.startswith("copy of ")


def test_locally_changed_copy_is_edited_not_stale(adapter, repo):
    """The distinction that makes the boot warning usable.

    At the office a copy carrying 사내 schema details differs from the
    template permanently. Reporting that as STALE would fire on every healthy
    adapter and train the reader to ignore the warning.
    """
    adapter.target.write_text("VERSION = 1  # plus local schema details\n")
    assert _classify(adapter, repo) == (EDITED, "")


def test_stale_survives_more_history_than_one_commit(adapter, repo):
    adapter.target.write_bytes(adapter.template.read_bytes())
    for version in range(2, 6):
        adapter.template.write_text(f"VERSION = {version}\n")
        _git(repo, "commit", "-qam", f"v{version}")

    assert _classify(adapter, repo)[0] == STALE


def test_outside_a_git_checkout_nothing_is_reported_stale(adapter, repo, tmp_path):
    """A tarball deploy must not have every adapter shouted about."""
    adapter.target.write_bytes(adapter.template.read_bytes())
    adapter.template.write_text("VERSION = 2\n")
    _git(repo, "commit", "-qam", "moved ahead")

    not_a_checkout = tmp_path / "elsewhere"
    not_a_checkout.mkdir()
    assert _classify(adapter, not_a_checkout) == (EDITED, "")


def test_stale_adapters_lists_only_the_stale_ones(repo):
    backend = repo / "back_dev_home"
    synced = backend / "storage" / "providers"
    synced.mkdir(parents=True)
    (synced / "office_example.py").write_text("OK = 1\n")
    (synced / "office.py").write_text("OK = 1\n")

    stale = backend / "sem_list" / "providers"
    (stale / "office.py").write_text("VERSION = 1\n")
    (stale / "office_example.py").write_text("VERSION = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "template moves ahead")

    found = office_template.stale_adapters(root=backend, repo_root=repo)
    assert [adapter.slug for adapter, _ in found] == ["sem_list"]


def test_discover_drops_the_providers_segment_from_the_slug(repo):
    backend = repo / "back_dev_home"
    tab = backend / "hardware" / "providers" / "fdc"
    tab.mkdir(parents=True)
    (tab / "office_example.py").write_text("")

    slugs = [adapter.slug for adapter in office_template.discover(backend)]
    assert slugs == ["hardware/fdc", "sem_list"]
