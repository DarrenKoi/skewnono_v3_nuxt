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
