"""Pack the working tree into a folder ready to copy to /project/workSpace.

Run FROM THE REPO ROOT, at the office, after building the frontend:

    npm --prefix front-dev-home run build
    .venv/bin/python -m scripts.deploy

Two properties of this repository shape everything here.

**Depth is load-bearing.** _runtime/env.py defines is_cloud() as "does this
file resolve under /project/workSpace" and spa_dir() as parents[2]/
front-dev-home/.output/public. Cloud mode — auth blueprint, SPA mount, office
site detection — is a property of the filesystem path, not of configuration.
A re-nested bundle loses all three while still answering HTTP 200.

**The files that matter most are untracked.** providers/office.py,
minio_handler/minio_config.py and back_dev_home/.env are gitignored by design,
so this reads the working tree. A git-archive approach would produce a bundle
that boots cleanly and serves mock data in production — the worst available
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

# Repo-relative paths copied wholesale into the bundle. Order is display order.
# Only ops_store, minio_handler and ftp_handler are actually imported by the
# app; ops_index_mgmt (index-creation tooling) is deliberately absent.
INCLUDED_ROOTS = (
    "index.py",
    "wsgi.ini",
    "back_dev_home",
    "front-dev-home/.output/public",
    "ops_store",
    "minio_handler",
    "ftp_handler",
)

# Directory names removed anywhere in the copied tree.
PRUNE_DIRS = frozenset({"__pycache__", "tests", ".pytest_cache", ".ruff_cache"})

# File suffixes removed anywhere. .md covers 22 MIGRATION.md files plus
# READMEs — office-migration notes with no runtime role.
PRUNE_SUFFIXES = (".pyc", ".pyo", ".md", ".log")

# Exact file names removed anywhere.
PRUNE_NAMES = frozenset({"conftest.py", ".DS_Store", "Thumbs.db"})


def prunes_by_name(name: str) -> bool:
    """Prune decision for a single directory entry, from its name alone.

    Deliberately name-only. The walk is top-down, so pruning a directory by
    name is enough — nothing below it is ever visited. Anything that consults
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


# Keep in sync with the fallback in back_dev_home/__init__.py's
# app.secret_key = os.environ.get("SKEWNONO_SECRET_KEY", ...). Not imported:
# packing must work without importing the app.
DEFAULT_SECRET_KEY = "dev-only-not-for-prod"


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


def _read_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _as_the_app_reads_it(value: str) -> str:
    """What create_app() will actually see for a `.env` value this reader got.

    `_read_env` is deliberately three lines — packing must work without
    importing the app — so it does not strip quotes. `create_app()` reads the
    same file with `load_dotenv()`, which does. That gap made
    `SKEWNONO_SECRET_KEY="dev-only-not-for-prod"` compare unequal to the
    default here and pass the advisory silently, while the running app signed
    real sessions with the key published in this repo.

    Only the unambiguous case is handled: one matching pair of surrounding
    quotes. Escapes, `${}` interpolation and multi-line values are left alone
    rather than half-guessed — `back_dev_home/.env.example` documents the
    format as "no quotes, no `export`, no spaces around `=`", so anything
    fancier is already outside it. This narrows the blind spot to shapes the
    packer cannot be sure about instead of leaving the common one open.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


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
        f"{spa_index} missing — run: npm --prefix front-dev-home run build",
        True,
    )

    env_path = repo_root / "back_dev_home" / ".env"
    add(
        "env_present",
        env_path.is_file(),
        f"{env_path} missing — create_app() load_dotenv()s this path",
        True,
    )

    reqs = repo_root / "back_dev_home" / "requirements.txt"
    add(
        "requirements_present",
        reqs.is_file(),
        f"{reqs} missing — nothing to pip install on the cloud",
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
        "the built SPA is older than front-dev-home/app/ — rebuild, or you "
        "will ship yesterday's UI",
        False,
    )

    secret = _read_env(env_path).get("SKEWNONO_SECRET_KEY", "")
    add(
        "secret_key",
        bool(secret) and _as_the_app_reads_it(secret) != DEFAULT_SECRET_KEY,
        "SKEWNONO_SECRET_KEY is unset or still the default; sessions are "
        "signed with a known key. Fine for a feasibility deploy, not for "
        "skewnono.skhynix.com",
        False,
    )

    adapters = office_adapters(repo_root)
    add(
        "office_adapters",
        bool(adapters),
        "no providers/office.py found — every feature will serve mock data",
        False,
    )

    return checks


def blocking_failures(checks: list[Check]) -> list[Check]:
    return [c for c in checks if not c.ok and c.blocking]


def _ignore(directory: str, names: list[str]) -> set[str]:
    """shutil.copytree callback — drop pruned entries during the walk.

    Matches on the entry NAME only. copytree passes `directory` as an absolute
    source path, so joining it and testing every component would prune the
    whole tree whenever the checkout lives under a directory called `tests`,
    `__pycache__`, or similar — a real office-PC path, not a hypothetical.
    """
    del directory  # the walk is top-down; ancestors are already decided
    return {name for name in names if prunes_by_name(name)}


# The Nuxt build output is already exactly what should ship, and it is opaque
# to our naming rules: a content file could legitimately be called tests/ or
# end in .md, and pruning it would break the SPA silently — the page would
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

    for name in ("index.py", "wsgi.ini"):
        if not (dest / name).is_file():
            failures.append(f"missing {dest / name}")

    if list(dest.rglob("__pycache__")):
        failures.append("__pycache__ survived the prune")

    return failures


RUNBOOK = """# Deploy this bundle

1. Copy this whole folder to `/project/workSpace/` on the cloud host.
   The path matters: `is_cloud()` tests whether `back_dev_home/_runtime/env.py`
   resolves under `/project/workSpace`. Anywhere else and the app starts with
   no SSO auth, no SPA mount, and mock data — while still answering HTTP 200.

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

4. Run preflight again. Imports should now resolve, and it reports which
   `hcputil` module spelling this image provides:

       python preflight.py

5. Start the app:

       uwsgi --ini wsgi.ini        # or: python index.py

6. Verify which data providers actually engaged:

       curl localhost:5000/api/health/providers

   This endpoint deliberately bypasses the provider swap mechanism, so it is
   the honest answer to whether office mode is on.

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
        f"office adapters ({len(adapters)}) — these features serve real data:",
    ]
    lines += [f"  {name}" for name in adapters] or ["  (none — all mock)"]

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
    args = parser.parse_args(argv)

    repo_root = Path.cwd()

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
        print(f"\nFAIL — {len(failures)} blocking problem(s); nothing written.")
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
        print("\nFAIL — the bundle written is not well formed:")
        for problem in problems:
            print(f"  {problem}")
        return 1

    write_manifest(dest, repo_root, checks, file_count, stamp)
    write_runbook(dest)

    os.chmod(dest, 0o700)

    warned = [c for c in checks if not c.ok]
    print(f"\nPASS — {file_count} files -> {dest}")
    if warned:
        print(f"  {len(warned)} warning(s) recorded in MANIFEST.txt:")
        for check in warned:
            print(f"    - {check.name}")
    print("\n  This bundle contains credentials:")
    print("    back_dev_home/.env")
    print("    minio_handler/minio_config.py")
    print("  The folder is chmod 700. Do not place it on shared storage.")
    print(f"\n  Next: copy {dest}/ to /project/workSpace/ then read DEPLOY.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
