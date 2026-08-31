"""Find and delete feature directories that git left behind after a move.

`providers/office.py` is gitignored, so `git pull` can never delete it. When a
commit MOVES a feature directory (the e-beam flattening `b87af52f` moved
`ebeam/cdsem/device_statistics/` -> `ebeam/device_statistics/`), git removes
every tracked file from the old path but cannot remove the directory itself --
the ignored `office.py` and `__pycache__` keep it alive. The old path then
still matches `_runtime/office_registry.py`'s `**/providers/office.py` glob,
and the app refuses to boot:

    RuntimeError: Duplicate feature slug 'device_statistics': ...

That failure only ever happens at the office, because home has no `office.py`
at all. This script is the cleanup, and it runs from anywhere:

    .venv/bin/python -m scripts.adapters.prune_orphan_features            # report only
    .venv/bin/python -m scripts.adapters.prune_orphan_features --delete   # actually remove
    .venv/bin/python -m scripts.adapters.prune_orphan_features --delete --yes

Windows (office local PC):

    .venv\\Scripts\\python -m scripts.adapters.prune_orphan_features --delete

## What counts as an orphan

A feature directory (one holding `providers/office.py` or `providers/mock.py`)
is an orphan when git knows nothing about anything inside it:

  * no TRACKED files            -> the move/delete really did land
  * no untracked-but-UNIGNORED  -> nobody is scaffolding a new feature here

Both halves matter. The second is the safety catch: a feature you just
scaffolded and have not committed yet is also "untracked", but its `mock.py`
and `routes.py` are *not ignored*, so it never looks like an orphan. Only a
directory whose entire remaining content is ignored (`office.py`, `*.bak`,
`__pycache__`) is safe to delete -- and every one of those bytes is either
reproducible from `office_example.py` or pure build output.

Empty parent directories are pruned afterwards, so removing
`ebeam/cdsem/device_statistics/` also takes `ebeam/cdsem/` with it.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "back_dev_home"

# Mirrors _runtime/office_registry.py: a feature is a directory with a
# providers/ child holding one of these. Both are globbed because a moved
# feature may have left EITHER behind -- office.py when the office copied an
# adapter there, mock.py in the rarer case where git could not clean up.
_FEATURE_MARKERS = ("office.py", "mock.py")


def _git(*args: str) -> list[str]:
    """Run a git command from REPO_ROOT, return its non-empty output lines."""
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"error: git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return [line for line in result.stdout.splitlines() if line.strip()]


def _feature_dirs() -> dict[Path, list[str]]:
    """Every feature directory under BACKEND_ROOT -> the markers found in it.

    Underscore-prefixed paths are skipped for the same reason the app factory
    and the registry skip them: `_runtime/`, `_auth/` and friends are shared
    plumbing, not features.
    """
    found: dict[Path, list[str]] = {}
    for marker in _FEATURE_MARKERS:
        for path in sorted(BACKEND_ROOT.glob(f"**/providers/{marker}")):
            feature_dir = path.parent.parent
            relative = feature_dir.relative_to(BACKEND_ROOT)
            if any(part.startswith("_") for part in relative.parts):
                continue
            found.setdefault(feature_dir, []).append(marker)
    return found


def _is_orphan(feature_dir: Path) -> bool:
    """True when git knows nothing about anything under this directory.

    Two questions, both of which must answer "nothing":

      ls-files                        -> tracked files
      ls-files --others --exclude-standard -> untracked files that are NOT ignored

    A live feature fails the first check. A brand-new uncommitted feature fails
    the second. Only a post-move husk -- ignored files and build output alone --
    passes both.
    """
    relative = feature_dir.relative_to(REPO_ROOT).as_posix()
    if _git("ls-files", "--", relative):
        return False
    if _git("ls-files", "--others", "--exclude-standard", "--", relative):
        return False
    return True


def _duplicate_slugs(feature_dirs: list[Path]) -> dict[str, list[Path]]:
    """Slugs claimed by more than one directory -- the boot error, reproduced."""
    by_slug: dict[str, list[Path]] = {}
    for feature_dir in feature_dirs:
        by_slug.setdefault(feature_dir.name, []).append(feature_dir)
    return {slug: dirs for slug, dirs in sorted(by_slug.items()) if len(dirs) > 1}


def _contents(feature_dir: Path) -> list[Path]:
    """Files remaining under an orphan, for the report. Ignored ones, by definition."""
    return sorted(path for path in feature_dir.rglob("*") if path.is_file())


def _prune_empty_parents(start: Path) -> list[Path]:
    """Walk up from a deleted directory, removing parents left empty.

    Stops at BACKEND_ROOT so the backend package itself is never a candidate,
    and stops at the first parent that still holds something.
    """
    removed: list[Path] = []
    parent = start.parent
    while parent != BACKEND_ROOT and BACKEND_ROOT in parent.parents:
        if any(parent.iterdir()):
            break
        parent.rmdir()
        removed.append(parent)
        parent = parent.parent
    return removed


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="prune_orphan_features",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Default action is a report. Pass --delete to remove anything.",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="remove the orphan directories (default: report only)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="skip the confirmation prompt (for --delete in a script)",
    )
    args = parser.parse_args(argv)

    if not BACKEND_ROOT.is_dir():
        raise SystemExit(f"error: {_rel(BACKEND_ROOT)} not found -- run this from the skewnono repo.")
    # A shallow/partial checkout would report every directory as untracked and
    # this script would happily delete the whole backend. Refuse instead.
    if not _git("ls-files", "--", "back_dev_home"):
        raise SystemExit("error: git tracks no files under back_dev_home/ -- refusing to guess.")

    feature_dirs = _feature_dirs()
    orphans = [feature_dir for feature_dir in sorted(feature_dirs) if _is_orphan(feature_dir)]

    duplicates = _duplicate_slugs(list(feature_dirs))
    if duplicates:
        print("Duplicate feature slugs (this is what blocks boot):")
        for slug, dirs in duplicates.items():
            print(f"  {slug}")
            for feature_dir in dirs:
                mark = "ORPHAN" if feature_dir in orphans else "live"
                print(f"    [{mark:6}] {_rel(feature_dir)}")
        print()

    if not orphans:
        print(f"No orphan feature directories under {_rel(BACKEND_ROOT)}/.")
        if duplicates:
            print("The duplicate slugs above are all live directories -- this is a")
            print("real naming collision, not leftover files. Rename one feature.")
            return 1
        return 0

    print(f"Orphan feature directories ({len(orphans)}):")
    for feature_dir in orphans:
        files = _contents(feature_dir)
        markers = ", ".join(sorted(feature_dirs[feature_dir]))
        print(f"  {_rel(feature_dir)}  ({markers}; {len(files)} file(s) remaining)")
        for path in files:
            print(f"      {path.relative_to(feature_dir).as_posix()}")
    print()

    if not args.delete:
        print("Nothing was changed. Re-run with --delete to remove them.")
        return 0

    if not args.yes:
        answer = input(f"Delete these {len(orphans)} directories? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Aborted.")
            return 1

    for feature_dir in orphans:
        shutil.rmtree(feature_dir)
        print(f"removed {_rel(feature_dir)}")
        for parent in _prune_empty_parents(feature_dir):
            print(f"removed {_rel(parent)}  (empty parent)")

    print()
    print("Done. Restart Flask -- office_registry scans once per process.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
