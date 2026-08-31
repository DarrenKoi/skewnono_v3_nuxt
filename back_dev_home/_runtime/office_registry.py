"""Which features have an office adapter — discovered from the filesystem.

``providers/office.py`` is gitignored and only ever appears because someone
deliberately ran ``cp office_example.py office.py`` while wiring a feature at
the office. Its existence IS the migration record, so nothing else has to
track readiness: no env var per feature, and no tracked set that the home side
would have to commit and push about a file it cannot see.

This mirrors what the app factory already does for blueprints
(``__init__.py`` globs ``routes.py``, then asserts each hit exports a
``Blueprint``): glob to discover, assert the hits are well-formed, fail at
boot rather than at request time.

Kept deliberately free of any ``os.environ`` access — everything env-related
lives in ``data_provider.py``, which imports this module. Splitting them that
way is what keeps the two free of a circular import.
"""

from functools import lru_cache
from pathlib import Path


# back_dev_home/. Monkeypatched by tests to point at a fake package tree.
_ROOT = Path(__file__).resolve().parent.parent


def _discover(filename: str) -> dict[str, Path]:
    """Map feature slug -> feature directory, for each providers/<filename>.

    ``**/providers/<filename>`` requires the file to sit DIRECTLY inside a
    directory literally named ``providers``, so per-tab adapters such as
    ``hardware/providers/fdc/office.py`` are excluded — ``fdc`` is not
    ``providers``. That exclusion is the boundary between feature-level
    resolution (here) and hardware's private per-tab fallback (``_tab()`` in
    ``hardware/providers/office_example.py``). It is load-bearing, and pinned
    by ``test_per_tab_adapters_never_enter_the_global_registry``.
    """
    found: dict[str, Path] = {}
    for path in sorted(_ROOT.glob(f"**/providers/{filename}")):
        feature_dir = path.parent.parent
        relative = feature_dir.relative_to(_ROOT)
        if any(part.startswith("_") for part in relative.parts):
            continue  # mirrors the blueprint scan in __init__.py
        if _nested_inside_a_feature(feature_dir):
            # A providers/ dir INSIDE another feature (chat/answer) is that
            # feature's private sub-seam with its own selector — registering
            # it here would claim its directory name as a global feature slug
            # ("answer") and print a presence-based resolution row that the
            # sub-seam's real selector can contradict.
            continue
        slug = feature_dir.name
        if slug in found:
            raise RuntimeError(
                f"Duplicate feature slug {slug!r}: "
                f"{repo_path(found[slug])} and {repo_path(feature_dir)}. "
                f"Feature directory names must be globally unique — "
                f"SKEWNONO_{slug.upper()}_PROVIDER can only name one of them."
            )
        found[slug] = feature_dir
    return found


def _nested_inside_a_feature(feature_dir: Path) -> bool:
    """True when a strict ancestor (below the package root) is itself a feature.

    Ancestry is decided by ``routes.py`` — the same marker the app factory
    uses to register a blueprint — not by ``providers/mock.py``. A feature is
    a thing the app serves; whether it happens to have a provider seam is a
    separate question, and chat is the case that separates them: it serves
    /api/chat/* with no seam of its own, while ``chat/answer`` beneath it has
    a seam and no route.
    """
    for ancestor in feature_dir.parents:
        if ancestor == _ROOT:
            return False
        if (ancestor / "routes.py").is_file():
            return True
    return False


@lru_cache(maxsize=1)
def _scan() -> tuple[dict[str, Path], dict[str, Path]]:
    """Scan once per process. Adding an office.py requires a restart.

    Flask's dev reloader restarts on its own; cloud deploys restart anyway.
    """
    all_features = _discover("mock.py")
    ready = _discover("office.py")

    orphans = sorted(set(ready) - set(all_features))
    if orphans:
        paths = ", ".join(repo_path(ready[slug]) for slug in orphans)
        raise RuntimeError(
            f"providers/office.py with no sibling providers/mock.py: {paths}. "
            f"Every feature needs a mock adapter — home development and the "
            f"contract tests both run against it."
        )
    return all_features, ready


def features() -> dict[str, Path]:
    """Every feature, by slug. A feature is a directory with providers/mock.py."""
    return _scan()[0]


def office_ready() -> dict[str, Path]:
    """Features whose providers/office.py exists on this machine."""
    return _scan()[1]


def backend_root() -> Path:
    """The back_dev_home package directory this process is scanning.

    Read through a function, not imported as a constant: tests monkeypatch
    ``_ROOT`` to a fake tree, and a second module holding its own copy would
    keep scanning the real one. ``office_template`` is that second module.
    """
    return _ROOT


def repo_path(feature_dir: Path) -> str:
    """Repo-relative POSIX path, for error messages a human can paste."""
    return feature_dir.relative_to(_ROOT.parent).as_posix()


def reset_cache() -> None:
    """Drop the memoized scan. Tests only."""
    _scan.cache_clear()
