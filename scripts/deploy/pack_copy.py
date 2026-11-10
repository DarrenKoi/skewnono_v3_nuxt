"""Sync the deployable files into a separate git checkout, for a git-push deploy.

pack.py's alternative. Same preflight, same file selection, same verification
- but instead of a fresh dist/ folder to drag onto the cloud, it refreshes the
deploy-owned paths inside a long-lived checkout (F:/skewnono-v3 at the office)
whose remote is the company git. Committing and pushing from there is the
deploy.

    .venv/bin/python -m scripts.deploy.pack_copy                  # -> F:/skewnono-v3
    .venv/bin/python scripts/deploy/pack_copy.py --target D:/x    # elsewhere

Only INCLUDED_ROOTS, preflight.py and MANIFEST.txt are touched. Each root is
deleted and re-copied, so a file removed here is removed there too (`git add
-A` turns it into a deletion). Anything else in the target - .git, its own
.gitignore, a committed index.py / wsgi.ini - is left alone.

**Git ignore rules are the new silent failure.** The bundle's most important
files are gitignored HERE by design (see pack.py's docstring), and the
backend/.gitignore that says so would travel along with backend/. In the
target that would make `git add -A` skip backend/.env, and the cloud would get
a tree without it. So nested .gitignore files are stripped from the copy, and
anything the target still ignores inside the deploy paths blocks.
"""

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Same bootstrap as pack.py - see the comment there.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import scripts  # noqa: E402,F401  (applies the stdout UTF-8 fix)

from scripts.deploy import pack  # noqa: E402

DEFAULT_TARGET = Path("F:/skewnono-v3")

# Paths in the target this script owns. Everything else there is the
# operator's.
OWNED_FILES = ("preflight.py", "MANIFEST.txt")


def sync_into(repo_root: Path, target: Path) -> int:
    """Replace every owned root in `target` with a fresh copy. Returns file count."""
    for rel in pack.INCLUDED_ROOTS:
        stale = target / rel
        if stale.is_dir():
            shutil.rmtree(stale)
        elif stale.exists():
            stale.unlink()

    pack.copy_bundle(repo_root, target)

    for rel in pack.INCLUDED_ROOTS:
        if rel not in pack.VERBATIM_ROOTS:
            for gi in (target / rel).rglob(".gitignore"):
                gi.unlink()

    return sum(
        1
        for rel in pack.INCLUDED_ROOTS
        for p in (target / rel).rglob("*")
        if p.is_file()
    )


def ignored_in_target(target: Path) -> list[str] | None:
    """Files under the owned paths that the target's git would NOT commit.

    None when git itself could not answer - never read that as "nothing
    ignored".
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(target), "ls-files", "--others", "--ignored",
             "--exclude-standard", "-z", "--", *pack.INCLUDED_ROOTS, *OWNED_FILES],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return [p for p in result.stdout.split("\0") if p]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync the deployable files into a git checkout for push-deploy."
    )
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--strict", action="store_true",
                        help="promote every advisory check to blocking")
    parser.add_argument("--repo-root", type=Path, default=None,
                        help="tree to copy from (default: the current directory)")
    args = parser.parse_args(argv)

    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")

    repo_root = (args.repo_root or Path.cwd()).resolve()
    target = args.target.resolve()

    if not (repo_root / "backend").is_dir():
        print(f"\nFAIL - {repo_root} is not a skewnono checkout.")
        print("  cd to the repo root, or name it with --repo-root.")
        return 1
    if not (target / ".git").exists():
        print(f"\nFAIL - {target} is not a git checkout.")
        print("  Clone or `git init` the company remote there first:")
        print(f"      git clone <company remote> {target}")
        return 1
    if target == repo_root or repo_root in target.parents or target in repo_root.parents:
        print(f"\nFAIL - {target} overlaps the source tree {repo_root}.")
        return 1

    checks = pack.run_preflight(repo_root, strict=args.strict)
    for check in checks:
        if not check.ok:
            label = "FAIL" if check.blocking else "WARN"
            print(f"  {label} {check.name}: {check.message}")
    failures = pack.blocking_failures(checks)
    if failures:
        print(f"\nFAIL - {len(failures)} blocking problem(s); nothing written.")
        return 1

    file_count = sync_into(repo_root, target)
    # From the packer's own package, not the tree - see pack.main().
    shutil.copy2(Path(pack.__file__).resolve().parent / "preflight_cloud.py",
                 target / "preflight.py")

    problems = pack.verify_bundle(target)
    ignored = ignored_in_target(target)
    if ignored is None:
        problems.append("git could not list ignored files in the target")
    elif ignored:
        problems.append(
            "the target's .gitignore would drop these from the commit, so the "
            "cloud would never get them: " + ", ".join(ignored)
        )
    if problems:
        print("\nFAIL - the synced tree is not deployable:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    pack.write_manifest(target, repo_root, checks, file_count, stamp)
    sha = pack.git_provenance(repo_root)["sha"][:8]

    warned = [c for c in checks if not c.ok]
    print(f"\nPASS - {file_count} files -> {target}")
    if warned:
        print(f"  {len(warned)} warning(s) recorded in MANIFEST.txt:")
        for check in warned:
            print(f"    - {check.name}")
    print("\n  This commit will contain credentials (backend/.env,")
    print("  minio_handler/minio_config.py). Push only to the internal remote.")
    print("\n  Next:")
    print(f"      cd {target}")
    print("      git add -A")
    print(f'      git commit -m "deploy {stamp} ({sha})"')
    print("      git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
