"""Pack the working tree into a folder ready to copy to /project/workSpace.

Run FROM THE REPO ROOT, at the office, after building the frontend:

    npm --prefix front-dev-home run build
    .venv/bin/python -m scripts.pack_deploy

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

from dataclasses import dataclass
from pathlib import Path

# Repo-relative paths copied wholesale into the bundle. Order is display order.
# Only ops_store, minio_handler and ftp_handler are actually imported by the
# app; ops_index_mgmt (index-creation tooling) and afm_data_platform (1.8MB,
# referenced only in a mock docstring) are deliberately absent.
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


def should_prune(path: Path) -> bool:
    """True when this path must not appear in the bundle."""
    if path.name in PRUNE_NAMES:
        return True
    if path.name in PRUNE_DIRS:
        return True
    if any(part in PRUNE_DIRS for part in path.parts):
        return True
    return path.suffix in PRUNE_SUFFIXES


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
        bool(secret) and secret != DEFAULT_SECRET_KEY,
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
