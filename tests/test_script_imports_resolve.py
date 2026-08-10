"""Every internal import in `scripts/` must name a module that exists.

Scripts are the one tree with no tests of its own: they are office-only, they
talk to real tools and real OpenSearch, and nothing at home ever executes them.
So when a refactor moves a module, a script's import rots and nobody finds out
until someone stands at the office trying to run it.

That is not hypothetical. The e-beam flattening (`b87af52f`) moved
`ebeam/hitachi/_office_meas_hist.py` up one level, and
`scripts/measure_msr_image_ftp.py` kept importing the old path for a day. The
symptom at the office was the worst kind: the traceback went to stderr while
the progress lines sat in a block-buffered stdout, so the screen scrolled and
appeared to show nothing at all.

This checks resolvability, not importability -- `find_spec` locates the module
without executing it, so no script's side effects run and no office-only
dependency (OpenSearch, a tool FTP) has to be reachable.

Limits worth knowing:

  * A lazy import inside a function is still found, because the scan is over
    the AST rather than over what executed. That is exactly the case that bit
    us -- `_discover()`'s import only runs when no locator is passed.
  * A module that exists but whose BODY is broken still passes. `find_spec`
    does not run it. This guards paths, not correctness.
  * `providers.office` modules are gitignored and absent at home by design, so
    they are excluded rather than reported.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

# Top-level packages that live in this repo. A missing one of these is a
# refactor that left a caller behind; a missing third-party package is an
# environment question and not this test's business.
INTERNAL_ROOTS = {
    "back_dev_home",
    "ftp_handler",
    "minio_handler",
    "ops_index_mgmt",
    "ops_store",
}


def _is_office_only(module: str) -> bool:
    """`providers/office.py` is gitignored and absent at home on purpose."""
    return module.endswith(".office") or ".providers.office" in module


def _imported_modules() -> dict[str, list[str]]:
    """module name -> the script files that import it, lazy imports included."""
    found: dict[str, list[str]] = {}
    for path in sorted(SCRIPTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                if name.split(".")[0] in INTERNAL_ROOTS and not _is_office_only(name):
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    found.setdefault(name, []).append(f"{rel}:{node.lineno}")
    return found


def test_every_internal_import_in_scripts_resolves():
    modules = _imported_modules()
    assert modules, "scanned no imports — the scripts/ scan is broken, not clean"

    unresolved = []
    for module, sites in sorted(modules.items()):
        try:
            missing = importlib.util.find_spec(module) is None
        except (ImportError, ValueError) as exc:
            missing, detail = True, f"{type(exc).__name__}: {exc}"
        else:
            detail = "not found"
        if missing:
            unresolved.append(f"  {module} ({detail})\n    imported at: {', '.join(sites)}")

    assert not unresolved, (
        "scripts/ import modules that do not exist — a refactor moved them and "
        "left the caller behind:\n" + "\n".join(unresolved)
    )
