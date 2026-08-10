"""`scripts/` must stay runnable at the office. See `scripts/README.md`.

These scripts have no other coverage: they are office-only, they talk to real
tools, and nothing at home executes them. Every rule checked here corresponds
to a failure that actually cost office time on 2026-08-10, when a single
measurement run took most of an afternoon to start — encoding, then an
unguarded stream call, then the invocation form.

Checks are static (AST and source text), never execution: importing these
modules would open FTP sessions and read OpenSearch.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# Packages that live in this repo. Importing one is what makes the sys.path
# bootstrap necessary; a script importing only stdlib does not need it.
REPO_PACKAGES = {
    "back_dev_home",
    "ftp_handler",
    "minio_handler",
    "ops_index_mgmt",
    "ops_store",
}

# Characters that a Korean Windows console (cp949) cannot encode. Printing one
# raises UnicodeEncodeError, and `--help` alone used to die on it. Hangul is
# NOT here: cp949 covers it, so Korean prose in output is fine.
FORBIDDEN_OUTPUT_CHARS = "—–═►◄▲▼✓✗…"


def _script_paths() -> list[Path]:
    return sorted(p for p in SCRIPTS.rglob("*.py") if p.name != "__init__.py")


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _ids(paths: list[Path]) -> list[str]:
    return [_rel(p) for p in paths]


SCRIPT_PATHS = _script_paths()


def test_there_are_scripts_to_check():
    """A scan that silently finds nothing would make every test below vacuous."""
    assert SCRIPT_PATHS, f"no scripts found under {_rel(SCRIPTS)}"


@pytest.mark.parametrize("path", SCRIPT_PATHS, ids=_ids(SCRIPT_PATHS))
def test_script_bootstraps_sys_path_before_importing_repo_packages(path: Path):
    """Rule 1: both `-m scripts.x` and `python scripts/x.py` must work.

    `-m` puts the working directory on sys.path; running the file by path puts
    scripts/ there instead, so the first repo import raises ModuleNotFoundError.
    The by-path form is what a file manager, an IDE's run button and tab
    completion all produce, so it has to work rather than be explained.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    first_repo_import = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        if any(name.split(".")[0] in REPO_PACKAGES for name in names):
            line = node.lineno
            first_repo_import = line if first_repo_import is None else min(first_repo_import, line)

    if first_repo_import is None:
        pytest.skip("imports no repo package, so no bootstrap is needed")

    match = re.search(r"^\s*sys\.path\.insert\(", source, re.MULTILINE)
    assert match, (
        f"{_rel(path)} imports a repo package but never puts the repo root on "
        f"sys.path, so `python {_rel(path)}` fails with ModuleNotFoundError. "
        f"Add the bootstrap from scripts/README.md §1."
    )
    bootstrap_line = source[: match.start()].count("\n") + 1
    assert bootstrap_line < first_repo_import, (
        f"{_rel(path)} bootstraps sys.path at line {bootstrap_line}, AFTER its "
        f"first repo import at line {first_repo_import}. The import runs first "
        f"and still fails."
    )


@pytest.mark.parametrize("path", SCRIPT_PATHS, ids=_ids(SCRIPT_PATHS))
def test_script_source_is_cp949_encodable(path: Path):
    """Rule 2: output must survive the office console's ANSI code page.

    Checking the whole source rather than only string literals is deliberate:
    argparse prints module docstrings as `description=`, and comments migrate
    into messages. Hangul passes — cp949 covers it — so this only bans the
    typographic characters that look harmless and are not.
    """
    source = path.read_text(encoding="utf-8")
    found = {c for c in source if c in FORBIDDEN_OUTPUT_CHARS}
    assert not found, (
        f"{_rel(path)} contains {sorted(found)!r}, which cp949 cannot encode — "
        f"a Windows terminal raises UnicodeEncodeError, sometimes on --help "
        f"alone. Use ASCII (scripts/README.md §2)."
    )
    try:
        source.encode("cp949")
    except UnicodeEncodeError as exc:
        bad = source[exc.start:exc.end]
        pytest.fail(f"{_rel(path)} contains {bad!r}, which cp949 cannot encode.")


@pytest.mark.parametrize("path", SCRIPT_PATHS, ids=_ids(SCRIPT_PATHS))
def test_stream_reconfigure_is_guarded(path: Path):
    """Rule 3: a convenience must never be why the script produced nothing.

    `reconfigure` is missing on some stdout objects and raises on a detached
    stream. Called bare at the top of main(), it aborts before the first
    character is printed — which reads as "the command does nothing".
    """
    source = path.read_text(encoding="utf-8")
    if "reconfigure(" not in source:
        return
    tree = ast.parse(source, filename=str(path))

    guarded_by_try = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    guarded_by_try.add(id(child))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "reconfigure"):
            continue
        assert id(node) in guarded_by_try, (
            f"{_rel(path)}:{node.lineno} calls reconfigure() outside a try. "
            f"Guard it (scripts/README.md §3)."
        )
