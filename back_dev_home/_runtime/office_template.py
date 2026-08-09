"""Is each providers/office.py still a faithful copy of its template?

``office_registry.py`` answers *whether* an adapter exists; this module
answers *which version* of the template it was copied from. The two are
separate questions and only the second one rots over time: office.py is
gitignored, so a ``git pull`` moves ``office_example.py`` forward while the
copy that actually runs stays exactly where it was.

That gap is not theoretical. ``768f16b`` moved the meas_hist fail_ratio
derivation out of the tracked dispatcher and into a call inside the adapter;
the pull delivered the helper but not the call, so every office instance whose
copy predated it silently went back to reading the index's raw ``fail_ratio``
(a percentage) and rendered failure rates above 100%. Nothing announced it.

So boot announces it now. The classification is the same one
``scripts/sync_office_adapters.py`` reports, and lives here rather than there
because the app must be able to warn about itself without dev tooling present.

STALE vs EDITED is the whole point, and only git can tell them apart:

  * STALE  — these exact bytes were a committed template once, so the copy is
             provably just out of date. Refreshing it loses nothing. This is
             the state worth shouting about.
  * EDITED — matches no committed version, so it holds local changes. At the
             office that is the NORMAL state (office.py may carry 사내 schema
             details that stay out of git), which is why a plain "differs from
             the template" check is useless as a warning: it would fire on
             every healthy adapter and be tuned out within a day.

Everything here is best-effort and must never break boot. No git available, a
deploy unpacked from a tarball rather than cloned, a permission error — all
degrade to "cannot tell", not to an exception.
"""

from __future__ import annotations

import filecmp
import subprocess
from dataclasses import dataclass
from pathlib import Path

from back_dev_home._runtime.office_registry import backend_root


__all__ = [
    "MISSING",
    "SYNCED",
    "STALE",
    "EDITED",
    "HISTORY_DEPTH",
    "Adapter",
    "classify",
    "discover",
    "stale_adapters",
]


MISSING = "MISSING"
SYNCED = "SYNCED"
STALE = "STALE"
EDITED = "EDITED"

# How far back to look for a matching historical template. Deep enough to
# cover a long-neglected copy, shallow enough to stay fast.
HISTORY_DEPTH = 40


@dataclass(frozen=True)
class Adapter:
    """One office_example.py template and the office.py it copies to."""

    template: Path
    target: Path
    slug: str  # e.g. "ebeam/storage" or "ebeam/hardware/fdc"

    @property
    def name(self) -> str:
        """Short label: last path segment (e.g. "storage", "fdc")."""
        return self.slug.rsplit("/", 1)[-1]


def discover(root: Path | None = None) -> list[Adapter]:
    """Every office_example.py under the backend package, sorted by slug."""
    backend = root or backend_root()
    adapters: list[Adapter] = []
    for template in backend.rglob("office_example.py"):
        relative = template.relative_to(backend).parent
        # Drop the "providers" segment so slugs read as feature paths:
        # ebeam/hardware/providers/fdc -> ebeam/hardware/fdc
        parts = [part for part in relative.parts if part != "providers"]
        adapters.append(Adapter(
            template=template,
            target=template.with_name("office.py"),
            slug="/".join(parts),
        ))
    return sorted(adapters, key=lambda adapter: adapter.slug)


def classify(adapter: Adapter, repo_root: Path | None = None) -> tuple[str, str]:
    """Return (status, note). Consults git only when a copy differs."""
    if not adapter.target.exists():
        return MISSING, ""
    # shallow=False: compare contents, not just size+mtime. A copied file
    # keeps its own mtime, so a shallow compare would report false drift.
    try:
        identical = filecmp.cmp(adapter.template, adapter.target, shallow=False)
    except OSError:
        return EDITED, ""
    if identical:
        return SYNCED, ""

    origin = committed_template_origin(adapter, repo_root)
    if origin:
        return STALE, f"copy of {origin}"
    return EDITED, ""


def stale_adapters(
    root: Path | None = None, repo_root: Path | None = None
) -> list[tuple[Adapter, str]]:
    """Every adapter whose office.py is a provably out-of-date copy.

    Returns (adapter, note) pairs. SYNCED and EDITED copies are omitted —
    the first is fine and the second is a deliberate local change this module
    has no standing to second-guess.
    """
    found: list[tuple[Adapter, str]] = []
    for adapter in discover(root):
        status, note = classify(adapter, repo_root)
        if status == STALE:
            found.append((adapter, note))
    return found


# --------------------------------------------------------------------------
# git plumbing
#
# Three subprocesses per differing adapter, independent of HISTORY_DEPTH:
# hash the copy once, list the template's commits once, then resolve all of
# their blob ids in a single `cat-file --batch-check`. The obvious loop —
# `git show <sha>:<path>` per commit — costs HISTORY_DEPTH processes each,
# which is affordable in a CLI run but not on every worker's boot.
# --------------------------------------------------------------------------


def _repo_root(explicit: Path | None) -> Path:
    return explicit if explicit is not None else backend_root().parent


def _git(repo_root: Path, *args: str, stdin: str | None = None) -> str | None:
    """Run git, returning stdout, or None for any failure at all."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            input=stdin,
        )
    except OSError:
        return None  # no git on PATH, or cwd is gone
    return result.stdout if result.returncode == 0 else None


def committed_template_origin(
    adapter: Adapter, repo_root: Path | None = None
) -> str | None:
    """Find the commit whose office_example.py matches this office.py.

    Returns "<short-sha> (<date>)" when office.py is byte-identical to some
    historical version of its template, else None (including "we could not
    check" — an unknowable origin and a genuine local edit are reported the
    same way, deliberately: both mean "do not tell the user this is stale").
    """
    root = _repo_root(repo_root)
    if not (root / ".git").exists():
        return None  # deployed from a tarball, not a clone

    try:
        relative = adapter.template.relative_to(root).as_posix()
    except ValueError:
        return None

    blob = _git(root, "hash-object", "--", str(adapter.target))
    if not blob:
        return None
    want = blob.strip()

    log = _git(
        root, "log", f"-{HISTORY_DEPTH}", "--format=%H|%h|%ad", "--date=short",
        "--", relative,
    )
    if not log:
        return None

    commits = [
        line.split("|", 2) for line in log.splitlines() if line.count("|") == 2
    ]
    if not commits:
        return None

    revisions = "".join(f"{full}:{relative}\n" for full, _, _ in commits)
    names = _git(
        root, "cat-file", "--batch-check=%(objectname)", stdin=revisions
    )
    if names is None:
        return None

    # One output line per input revision, in order. A revision that does not
    # resolve prints "<input> missing", which can never equal a blob id.
    for (_, short, date), line in zip(commits, names.splitlines(), strict=True):
        if line.strip() == want:
            return f"{short} ({date.strip()})"
    return None
