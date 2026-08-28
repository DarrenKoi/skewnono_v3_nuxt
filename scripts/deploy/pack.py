"""Pack the working tree into a folder ready to copy to /project/workSpace.

Run at the office, after building the frontend. Both invocation forms work
(scripts/README.md section 1):

    npm --prefix front-dev-home run build
    .venv/bin/python -m scripts.deploy.pack        # module form
    .venv/bin/python scripts/deploy/pack.py        # path form

What gets packed is the CURRENT DIRECTORY, not this file's own checkout - the
point is to ship the tree the operator has in front of them, gitignored files
and all. `--repo-root` names it explicitly for anyone who ran the command from
somewhere else.

Two properties of this repository shape everything here.

**Depth is load-bearing.** _runtime/env.py defines is_cloud() as "does this
file resolve under /project/workSpace" and spa_dir() as parents[2]/
front-dev-home/.output/public. Cloud mode - auth blueprint, SPA mount, office
site detection - is a property of the filesystem path, not of configuration.
A re-nested bundle loses all three while still answering HTTP 200.

**The files that matter most are untracked.** providers/office.py,
minio_handler/minio_config.py and back_dev_home/.env are gitignored by design,
so this reads the working tree. A git-archive approach would produce a bundle
that boots cleanly and serves mock data in production - the worst available
failure mode, because nothing announces it.
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# The bootstrap from scripts/README.md section 1, one level deeper because this
# file sits in scripts/deploy/ rather than scripts/.
#
# `-m` puts the working directory on sys.path; running the file BY PATH puts
# scripts/deploy/ there instead, so without this the first repo import dies with
# ModuleNotFoundError. The by-path form is what a file manager, an IDE's run
# button and tab completion all produce.
#
# `import scripts` looks redundant next to the path insert and is not: it is
# what applies scripts/__init__.py's UTF-8 stdout fix. The `-m` form imports the
# package on its own, the path form never does, and this line is what makes the
# two behave the same on a Korean Windows console with output redirected.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import scripts  # noqa: E402,F401  (applies the stdout UTF-8 fix)

from scripts.deploy.preflight_cloud import env_file_values  # noqa: E402

# Repo-relative paths copied wholesale into the bundle. Order is display order.
# Only ops_store, minio_handler, ftp_handler and office_utils are actually
# imported by the app - office_utils via recipe_search's deferred import (the
# 사내 IDP parser behind recipe open; without it every recipe-open request
# fails after the FTP fetch). ops_index_mgmt (index-creation tooling) is
# deliberately absent.
INCLUDED_ROOTS = (
    "back_dev_home",
    "front-dev-home/.output/public",
    "ops_store",
    "minio_handler",
    "ftp_handler",
    "office_utils",
)

# Directory names removed anywhere in the copied tree.
# `.git` is here for the chat RAG checkout at back_dev_home/chat/_rag/, which
# is a nested repository the bundle must carry (the office adapter imports it
# in-process) - its history and objects are not runtime files.
PRUNE_DIRS = frozenset({"__pycache__", "tests", ".pytest_cache", ".ruff_cache", ".git"})

# File suffixes removed anywhere. .md covers 22 MIGRATION.md files plus
# READMEs - office-migration notes with no runtime role. .db is the chat
# thread store (back_dev_home/chat/chat.db, gitignored but present in every
# working tree that ran chat): overlaying the bundle onto /project/workSpace/
# would replace the cloud's threads with the office PC's.
PRUNE_SUFFIXES = (".pyc", ".pyo", ".md", ".log", ".db")

# Exact file names removed anywhere.
PRUNE_NAMES = frozenset({"conftest.py", ".DS_Store", "Thumbs.db"})


def prunes_by_name(name: str) -> bool:
    """Prune decision for a single directory entry, from its name alone.

    Deliberately name-only. The walk is top-down, so pruning a directory by
    name is enough - nothing below it is ever visited. Anything that consults
    ancestors would inherit whatever the bundle happens to be checked out
    under, which is not ours to interpret.
    """
    return (
        name in PRUNE_NAMES
        or name in PRUNE_DIRS
        or Path(name).suffix in PRUNE_SUFFIXES
    )


def should_prune(path: Path) -> bool:
    """True when this REPO-RELATIVE path must not appear in the bundle.

    Takes a relative path: the ancestor check below reads every component, so
    an absolute path would test the directories the checkout happens to live
    in. Use prunes_by_name() when all you have is one entry's name.
    """
    return prunes_by_name(path.name) or any(part in PRUNE_DIRS for part in path.parts)


@dataclass(frozen=True)
class Check:
    """One preflight result.

    `blocking` is the whole point: this deploy is a feasibility check, so an
    incomplete mock→office transition must warn rather than refuse. Only a
    guaranteed-dead deploy blocks.
    """

    name: str
    ok: bool
    message: str
    blocking: bool


def _newest_mtime(root: Path) -> float:
    return max(
        (p.stat().st_mtime for p in root.rglob("*") if p.is_file()), default=0.0
    )


def office_adapters(repo_root: Path) -> list[str]:
    """Feature slugs that have a providers/office.py, i.e. serve real data."""
    backend = repo_root / "back_dev_home"
    if not backend.is_dir():
        return []
    return sorted(
        str(p.relative_to(backend).parent.parent)
        for p in backend.rglob("providers/office.py")
    )


def run_preflight(repo_root: Path, strict: bool = False) -> list[Check]:
    checks = []

    def add(name, ok, message, blocking):
        checks.append(Check(name, ok, message, blocking or strict))

    spa_index = repo_root / "front-dev-home" / ".output" / "public" / "index.html"
    add(
        "spa_built",
        spa_index.is_file(),
        f"{spa_index} missing - run: npm --prefix front-dev-home run build",
        True,
    )

    env_path = repo_root / "back_dev_home" / ".env"
    add(
        "env_present",
        env_path.is_file(),
        f"{env_path} missing - create_app() load_dotenv()s this path",
        True,
    )

    # The one .env value pack has standing to judge. Everything else in that
    # file is content this script has no opinion on (see
    # test_preflight_does_not_inspect_env_values) - but SKEWNONO_LOG_ENV is
    # not content, it is a property of the MACHINE, and back_dev_home is
    # copied wholesale, so packing here sends this office PC's value to the
    # cloud. That is how a cloud deploy came to run with `local` on
    # 2026-08-03, writing every activity document to the office alias. The
    # bundle's own preflight.py fails on it too, but only after the transfer.
    log_env = (env_file_values(env_path) or {}).get("SKEWNONO_LOG_ENV", "")
    add(
        "logging_target",
        log_env in ("production", ""),
        f"{env_path} sets SKEWNONO_LOG_ENV={log_env} - that is this machine's "
        "own logging target and the bundle is for the cloud. Activity would go "
        "to the `skewnono_logging_local` alias, production `skewnono_logging` "
        "would stay empty, and /admin-logs would read the same wrong alias "
        "back, so nothing up there reports it. Set SKEWNONO_LOG_ENV=production "
        "in the bundle's copy before transfer.",
        False,
    )

    reqs = repo_root / "back_dev_home" / "requirements.txt"
    add(
        "requirements_present",
        reqs.is_file(),
        f"{reqs} missing - nothing to pip install on the cloud",
        True,
    )

    missing_roots = [r for r in INCLUDED_ROOTS if not (repo_root / r).exists()]
    add(
        "roots_present",
        not missing_roots,
        f"missing from the working tree: {', '.join(missing_roots)}",
        True,
    )

    app_dir = repo_root / "front-dev-home" / "app"
    build_fresh = True
    if spa_index.is_file() and app_dir.is_dir():
        build_fresh = spa_index.stat().st_mtime >= _newest_mtime(app_dir)
    add(
        "build_fresh",
        build_fresh,
        "the built SPA is older than front-dev-home/app/ - rebuild, or you "
        "will ship yesterday's UI",
        False,
    )

    adapters = office_adapters(repo_root)
    add(
        "office_adapters",
        bool(adapters),
        "no providers/office.py found - every feature will serve mock data",
        False,
    )

    return checks


def blocking_failures(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.ok and c.blocking]


def _ignore(directory: str, names: list[str]) -> set[str]:
    """shutil.copytree callback - drop pruned entries during the walk.

    Matches on the entry NAME only. copytree passes `directory` as an absolute
    source path, so joining it and testing every component would prune the
    whole tree whenever the checkout lives under a directory called `tests`,
    `__pycache__`, or similar - a real office-PC path, not a hypothetical.
    """
    del directory  # the walk is top-down; ancestors are already decided
    return {name for name in names if prunes_by_name(name)}


# The Nuxt build output is already exactly what should ship, and it is opaque
# to our naming rules: a content file could legitimately be called tests/ or
# end in .md, and pruning it would break the SPA silently - the page would
# 404 an asset at runtime with nothing failing at pack time. So it is copied
# verbatim. Everything else goes through should_prune().
VERBATIM_ROOTS = frozenset({"front-dev-home/.output/public"})


def copy_bundle(repo_root: Path, dest: Path) -> int:
    """Copy every included root into `dest`, preserving relative depth."""
    dest.mkdir(parents=True, exist_ok=True)

    for rel in INCLUDED_ROOTS:
        source = repo_root / rel
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            ignore = None if rel in VERBATIM_ROOTS else _ignore
            shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)
        elif source.is_file():
            shutil.copy2(source, target)

    return sum(1 for p in dest.rglob("*") if p.is_file())


def verify_bundle(dest: Path) -> list[str]:
    """Check the bundle we just wrote, rather than trusting the copy logic.

    Catching a layout mistake here costs seconds; catching it on the cloud
    costs a full transfer round-trip.
    """
    failures = []

    env_py = dest / "back_dev_home" / "_runtime" / "env.py"
    if not env_py.is_file():
        failures.append(f"missing {env_py}")
    elif env_py.resolve().parents[2] != dest.resolve():
        failures.append(
            f"{env_py} is not 2 levels below the bundle root; spa_dir() will miss"
        )

    index_html = dest / "front-dev-home" / ".output" / "public" / "index.html"
    if not index_html.is_file():
        failures.append(f"missing {index_html}")

    # office_utils is gitignored (like providers/office.py), so a checkout that
    # never had it packs a bundle where recipe open 500s on the parse step -
    # with copy_bundle silently skipping the absent root. Catch it here.
    idp_parser = dest / "office_utils" / "read_idp_info.py"
    if not idp_parser.is_file():
        failures.append(
            f"missing {idp_parser} - recipe open needs the 사내 IDP parser; "
            "office_utils/ was absent (or empty) in the working tree"
        )

    if list(dest.rglob("__pycache__")):
        failures.append("__pycache__ survived the prune")

    return failures


RUNBOOK = """# Deploy this bundle

1. Copy this bundle's contents over the existing `/project/workSpace/` on the
   cloud host. Do not delete or replace `/project/workSpace`: its permanent
   `index.py` and `wsgi.ini` are intentionally not included in this bundle.

   The path matters: `is_cloud()` tests whether `back_dev_home/_runtime/env.py`
   resolves under `/project/workSpace`. Anywhere else and the app starts with
   no SSO auth, no SPA mount, and mock data - while still answering HTTP 200.

   This folder carries credentials (`back_dev_home/.env`,
   `minio_handler/minio_config.py`). It is mode 700 here, but `scp -r` without
   `-p`, SFTP clients and tar-extract all recreate directories under the
   destination umask, so re-apply it after the copy:

       chmod 700 /project/workSpace
       chmod 600 /project/workSpace/back_dev_home/.env
       chmod 600 /project/workSpace/minio_handler/minio_config.py

2. Check the transfer landed correctly, before installing anything:

       cd /project/workSpace && python preflight.py

3. Install dependencies:

       pip install -r back_dev_home/requirements.txt

4. Run preflight again. Every runtime import comes from requirements.txt -
   identity is the LASTUSER cookie, so nothing here needs the cloud image:

       python preflight.py

5. Start the app:

       uwsgi --ini wsgi.ini        # or: python index.py

6. Verify which data providers actually engaged:

       curl -b "LASTUSER=<admin empno>" localhost:5000/api/health/providers

   This endpoint deliberately bypasses the provider swap mechanism, so it is
   the honest answer to whether office mode is on. It is admin-only - it
   discloses the site, mode and every feature's provider - so an uncookied
   call gets a 403 rather than the table.

`MANIFEST.txt` records what this bundle contains and any warnings raised
when it was packed.
"""


def git_provenance(repo_root: Path) -> dict[str, str]:
    """Best-effort. A bundle packed from a non-git export still packs."""

    def run(*args):
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return "unknown"
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    status = run("status", "--porcelain")
    if status == "unknown":
        # Never report a clean tree because git failed -- this is a provenance
        # record, and "no" next to sha=unknown reads as a verified-clean build.
        dirty = "unknown"
    else:
        dirty = "yes" if status else "no"
    return {
        "sha": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": dirty,
    }


def write_manifest(dest, repo_root, checks, file_count, stamp) -> Path:
    """Provenance record. The adapter roster is the point.

    Presence detection leaves no configuration line to read afterwards, so
    without this file there is no way to answer "what is actually running up
    there?" without shell access to the cloud host.
    """
    git = git_provenance(repo_root)
    adapters = office_adapters(repo_root)
    total_bytes = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    warnings = [c for c in checks if not c.ok]

    lines = [
        "SKEWNONO deployment bundle",
        f"packed:      {stamp}",
        f"host:        {socket.gethostname()}",
        f"git sha:     {git['sha']}",
        f"git branch:  {git['branch']}",
        f"uncommitted: {git['dirty']}",
        f"files:       {file_count}",
        f"size:        {total_bytes / 1_048_576:.1f} MiB",
        "",
        f"office adapters ({len(adapters)}) - these features serve real data:",
    ]
    lines += [f"  {name}" for name in adapters] or ["  (none - all mock)"]

    lines += ["", f"warnings at pack time ({len(warnings)}):"]
    lines += [f"  {c.name}: {c.message}" for c in warnings] or ["  (none)"]

    path = dest / "MANIFEST.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_runbook(dest: Path) -> Path:
    path = dest / "DEPLOY.md"
    path.write_text(RUNBOOK, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pack the working tree into a cloud deployment folder."
    )
    parser.add_argument("--out", type=Path, default=Path("dist"))
    parser.add_argument(
        "--build",
        action="store_true",
        help="run `npm run build` in front-dev-home/ first",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="promote every advisory check to blocking",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="tree to pack (default: the current directory)",
    )
    args = parser.parse_args(argv)

    # Rule 4: prove the process is alive, and name the encoding, before any of
    # the slow work. When the same command behaves differently in two windows,
    # this line is what tells them apart.
    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")

    repo_root = (args.repo_root or Path.cwd()).resolve()

    # Rule 6: say what is wrong and what to do about it. Without this, running
    # from the wrong directory printed four separate blocking failures, each
    # naming a path under that wrong directory - which reads as a broken repo
    # rather than a mislaid `cd`.
    if not (repo_root / "back_dev_home").is_dir():
        print(f"\nFAIL - {repo_root} is not a skewnono checkout.")
        print("  Pack runs against the CURRENT DIRECTORY. Either cd to the")
        print("  repo root, or name it:")
        print(f"      python -m scripts.deploy.pack --repo-root {_REPO_ROOT}")
        return 1

    if args.build:
        print("building the frontend...")
        result = subprocess.run(
            ["npm", "--prefix", str(repo_root / "front-dev-home"), "run", "build"]
        )
        if result.returncode != 0:
            print("FAIL frontend build failed")
            return 1

    checks = run_preflight(repo_root, strict=args.strict)
    for check in checks:
        if not check.ok:
            label = "FAIL" if check.blocking else "WARN"
            print(f"  {label} {check.name}: {check.message}")

    failures = blocking_failures(checks)
    if failures:
        print(f"\nFAIL - {len(failures)} blocking problem(s); nothing written.")
        return 1

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    dest = args.out / f"skewnono-{stamp}"
    if dest.exists():
        shutil.rmtree(dest)

    file_count = copy_bundle(repo_root, dest)

    # A sibling module, deliberately not a working-tree path: the checker that
    # ships must be the one this packer was written against. Reading it out of
    # the tree being packed would let a stale checkout ship a checker that
    # disagrees with the bundle it is meant to validate -- and no exception
    # here means a bundle that silently arrives with no preflight.py at all.
    shutil.copy2(
        Path(__file__).resolve().parent / "preflight_cloud.py",
        dest / "preflight.py",
    )

    problems = verify_bundle(dest)
    if problems:
        print("\nFAIL - the bundle written is not well formed:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    write_manifest(dest, repo_root, checks, file_count, stamp)
    write_runbook(dest)

    os.chmod(dest, 0o700)

    warned = [c for c in checks if not c.ok]
    print(f"\nPASS - {file_count} files -> {dest}")
    if warned:
        print(f"  {len(warned)} warning(s) recorded in MANIFEST.txt:")
        for check in warned:
            print(f"    - {check.name}")
    print("\n  This bundle contains credentials:")
    print("    back_dev_home/.env")
    print("    minio_handler/minio_config.py")
    print("  The folder is chmod 700. Do not place it on shared storage.")
    print(
        f"\n  Next: overlay the contents of {dest}/ onto the existing "
        "/project/workSpace/ then read DEPLOY.md"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
