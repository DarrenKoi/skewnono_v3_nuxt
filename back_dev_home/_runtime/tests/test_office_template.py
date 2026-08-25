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
    # env is built from scratch (not inherited), so these fixture calls keep
    # working even in the test that hides git from the PATH under test.
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(repo),
        },
    )


def _head_sha(repo):
    return _git(repo, "rev-parse", "--short", "HEAD").stdout.strip()


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


def test_the_history_window_ends_at_history_depth_and_then_says_edited(adapter, repo):
    """Past HISTORY_DEPTH commits the honest answer is EDITED, and that costs.

    The walk is bounded (`git log -HISTORY_DEPTH`) so boot stays cheap, which
    means "provably a copy of an old template" fades out at a fixed distance:
    beyond it, a pristine copy is indistinguishable from one carrying 사내
    edits and gets the safe label. Safe, not free — `sync_office_adapters`
    skips EDITED without --force, so the most neglected copies are exactly the
    ones it stops refreshing. Pinning the boundary keeps that trade visible if
    anyone tunes the constant.

    The commit that created the template is itself one of the HISTORY_DEPTH
    the walk sees, so HISTORY_DEPTH - 1 further commits leave it on the last
    line and one more pushes it off.
    """
    adapter.target.write_bytes(adapter.template.read_bytes())
    for version in range(2, office_template.HISTORY_DEPTH + 1):
        adapter.template.write_text(f"VERSION = {version}\n")
        _git(repo, "commit", "-qam", f"v{version}")

    assert _classify(adapter, repo)[0] == STALE  # last commit inside the window

    adapter.template.write_text("VERSION = one commit too many\n")
    _git(repo, "commit", "-qam", "the creating commit falls off the window")

    assert _classify(adapter, repo) == (EDITED, "")


def test_outside_a_git_checkout_nothing_is_reported_stale(adapter, repo, tmp_path):
    """A tarball deploy must not have every adapter shouted about."""
    adapter.target.write_bytes(adapter.template.read_bytes())
    adapter.template.write_text("VERSION = 2\n")
    _git(repo, "commit", "-qam", "moved ahead")

    not_a_checkout = tmp_path / "elsewhere"
    not_a_checkout.mkdir()
    assert _classify(adapter, not_a_checkout) == (EDITED, "")


def test_no_git_on_the_path_degrades_to_edited_instead_of_raising(
    adapter, repo, monkeypatch, tmp_path
):
    """Being unable to ask git must read as "cannot tell", not as a crash.

    This runs inside create_app() via boot's stale-adapter warning, and the
    PATH a uwsgi worker inherits is whatever the service definition gave it —
    frequently not the interactive one. A diagnostic that can stop Phase 3
    from booting is worse than no diagnostic, so the OSError from a missing
    git binary is swallowed here rather than relying on boot.py's blanket
    except, which is the second line of defence and only covers boot.
    """
    adapter.target.write_bytes(adapter.template.read_bytes())
    adapter.template.write_text("VERSION = 2\n")
    _git(repo, "commit", "-qam", "template moves ahead")
    assert _classify(adapter, repo)[0] == STALE  # git can be asked, for now

    monkeypatch.setenv("PATH", str(tmp_path / "there-is-no-git-here"))
    assert _classify(adapter, repo) == (EDITED, "")


def test_a_repo_root_the_template_does_not_live_under_is_not_asked_about(
    adapter, repo, tmp_path
):
    """A .git next door is not this adapter's history.

    The repo root is inferred from where the package sits, so a deploy that
    unpacks back_dev_home beside (or inside) an unrelated clone hands us a
    root the template is not under. The relative_to() guard bails out before
    git is consulted at all — which is what stops the neighbour's identically
    named file from being mistaken for our template's history, so the decoy
    below is committed to make that failure mode reachable if the guard ever
    softens into a best-effort path computation.
    """
    adapter.target.write_bytes(adapter.template.read_bytes())
    adapter.template.write_text("VERSION = 2\n")
    _git(repo, "commit", "-qam", "template moves ahead")
    assert _classify(adapter, repo)[0] == STALE  # asked against the right root

    unrelated = tmp_path / "unrelated-clone"
    decoy = unrelated / adapter.template.relative_to(repo)
    decoy.parent.mkdir(parents=True)
    decoy.write_text("VERSION = 1\n")  # exactly what our copy holds
    _git(unrelated, "init", "-q", "-b", "main")
    _git(unrelated, "add", "-A")
    _git(unrelated, "commit", "-qm", "another repo's office_example.py")

    assert _classify(adapter, unrelated) == (EDITED, "")


def test_a_template_deleted_and_re_added_still_resolves_to_the_right_commit(
    adapter, repo
):
    """`git log -- <path>` includes the commit that DELETED the template.

    Asking `cat-file --batch-check` for <that commit>:<path> prints
    "<input> missing" instead of a blob id. The lookup pairs output lines with
    input revisions by position, so treating that line as anything other than
    one non-matching line would shift every older commit onto the wrong sha —
    silently downgrading a STALE copy to EDITED, or crediting it to a commit
    it never came from. Features do get moved around under ebeam/, which
    deletes and re-adds a template, so this is an ordinary history, not a
    pathological one.
    """
    adapter.target.write_bytes(adapter.template.read_bytes())  # copy of VERSION = 1
    created_in = _head_sha(repo)

    relative = adapter.template.relative_to(repo).as_posix()
    _git(repo, "rm", "-q", "--", relative)
    _git(repo, "commit", "-qm", "template deleted")
    adapter.template.write_text("VERSION = 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "template re-added, moved ahead")

    status, note = _classify(adapter, repo)
    assert status == STALE
    assert note.startswith(f"copy of {created_in}")


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


def test_stale_survives_a_template_that_was_moved_to_another_folder(repo):
    """A renamed template must not turn every copy of it into EDITED.

    This is the ebeam flattening (2026-08-xx), where every
    `ebeam/hitachi/<feature>/` template moved up to `ebeam/<feature>/`. The
    copies were untouched and their exact bytes were still in git history —
    but under the OLD path, so a history walk pinned to the CURRENT path found
    nothing and four adapters were reported as locally EDITED.

    That misreport is expensive in both directions: `copy` refuses to refresh
    an EDITED copy without --force, so the honest user keeps running old
    adapter code against live office data, and the user who does force is told
    they may be destroying local work that never existed.
    """
    providers = repo / "back_dev_home" / "sem_list" / "providers"
    (providers / "office.py").write_text((providers / "office_example.py").read_text())
    before_move = _head_sha(repo)

    moved = repo / "back_dev_home" / "ebeam" / "sem_list" / "providers"
    (repo / "back_dev_home" / "ebeam").mkdir()
    _git(repo, "mv", "back_dev_home/sem_list", "back_dev_home/ebeam/sem_list")
    _git(repo, "commit", "-qm", "flatten: move the template one folder up")
    the_move = _head_sha(repo)
    # A separate commit, as the flattening was: the move carried the bytes
    # unchanged and the template moved ahead later. Renaming and rewriting in
    # ONE commit is a rename git cannot detect on a file this small, which
    # would test git's similarity heuristic rather than this module.
    (moved / "office_example.py").write_text("VERSION = 2\n")
    _git(repo, "commit", "-qam", "template moves ahead after the move")

    adapter = office_template.discover(repo / "back_dev_home")[0]
    # discover() finds the template at its NEW path; office.py rode along with
    # the `git mv` and is still the bytes committed at `origin`.
    status, note = _classify(adapter, repo)
    assert status == STALE
    # Either commit is a correct answer — the move carried the bytes unchanged,
    # so both hold a template identical to this copy, and the walk names the
    # newest match. What must not happen is naming neither.
    assert any(sha in note for sha in (before_move, the_move)), note
