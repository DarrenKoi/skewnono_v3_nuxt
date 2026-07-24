"""Copy `providers/office_example.py` templates to their runnable `office.py`.

`office_example.py` is the tracked template; `office.py` is the gitignored
adapter that actually runs, and creating it is what switches a feature to
office data (see `_runtime/office_registry.py`). With 30 templates spread
across nested folders it is hard to tell which ones have been copied, so the
default action here is a **status report**, not a copy.

Run FROM THE REPO ROOT:

    # 1. See where every adapter stands (safe, changes nothing)
    .venv/bin/python -m scripts.sync_office_adapters

    # 2. Copy the ones you want
    .venv/bin/python -m scripts.sync_office_adapters --all
    .venv/bin/python -m scripts.sync_office_adapters storage sem_list
    .venv/bin/python -m scripts.sync_office_adapters hardware/fdc
    .venv/bin/python -m scripts.sync_office_adapters -i      # pick from a menu

    # 3. Inspect / rehearse
    .venv/bin/python -m scripts.sync_office_adapters --all --dry-run
    .venv/bin/python -m scripts.sync_office_adapters --diff storage

Statuses:

    MISSING  no office.py yet -> feature still serves mock data
    SYNCED   office.py is byte-identical to the template
    STALE    office.py matches an OLDER committed template -- the template
             moved ahead (a git pull) and this copy was never refreshed
    EDITED   office.py differs from the template and matches no committed
             version, so it holds local changes -- never overwritten
             without --force

STALE vs EDITED is the distinction that matters, and only git can tell them
apart. Both merely "differ from the template", but:

  * STALE  is provably just an out-of-date copy -- its exact bytes exist in
           git history, so refreshing it loses nothing. Treated as safe to
           overwrite. This is the state after `git pull` updates a template,
           and a stale office.py silently runs OLD adapter code against live
           office data (it once produced a phantom recipe_tat bug report).
  * EDITED matches no committed template version, so someone changed it here.
           office.py is gitignored, meaning those changes exist NOWHERE else
           -- clobbering them is unrecoverable. Requires --force, which takes
           a .bak first.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "back_dev_home"

MISSING = "MISSING"
SYNCED = "SYNCED"
STALE = "STALE"
EDITED = "EDITED"

# Statuses a copy may overwrite freely: either there is nothing there, or
# what is there is provably recoverable from git history.
SAFE_TO_WRITE = (MISSING, STALE)

# How far back to look for a matching historical template. Deep enough to
# cover a long-neglected copy, shallow enough to stay fast.
_HISTORY_DEPTH = 40


@dataclass(frozen=True)
class Adapter:
    """One office_example.py template and the office.py it copies to."""

    template: Path
    target: Path
    slug: str  # e.g. "ebeam/hitachi/storage" or "ebeam/hitachi/hardware/fdc"

    @property
    def name(self) -> str:
        """Short label: last path segment (e.g. "storage", "fdc")."""
        return self.slug.rsplit("/", 1)[-1]

    @property
    def status(self) -> str:
        return classify(self)[0]

    @property
    def note(self) -> str:
        """Human detail for the status (e.g. which commit a STALE copy is from)."""
        return classify(self)[1]


_classify_cache: dict[Path, tuple[str, str]] = {}


def classify(adapter: Adapter) -> tuple[str, str]:
    """Return (status, note), consulting git only when a copy differs.

    Cached per target: a status run asks for every adapter, and the git
    history walk below is the only expensive part.
    """
    cached = _classify_cache.get(adapter.target)
    if cached is None:
        cached = _classify(adapter)
        _classify_cache[adapter.target] = cached
    return cached


def _classify(adapter: Adapter) -> tuple[str, str]:
    if not adapter.target.exists():
        return MISSING, ""
    # shallow=False: compare contents, not just size+mtime. A copied file
    # keeps its own mtime, so a shallow compare would report false drift.
    if filecmp.cmp(adapter.template, adapter.target, shallow=False):
        return SYNCED, ""
    # It differs -- but "differs" alone can't tell an out-of-date copy from a
    # deliberate local edit, and the two want opposite handling. If these
    # exact bytes were ever a committed template, it is just an old copy.
    origin = _committed_template_origin(adapter)
    if origin:
        return STALE, f"copy of {origin}"
    return EDITED, ""


def _committed_template_origin(adapter: Adapter) -> str | None:
    """Find the commit whose office_example.py matches this office.py.

    Returns "<short-sha> (<date>)" when office.py is byte-identical to some
    historical version of its template, else None.
    """
    try:
        current = adapter.target.read_bytes()
    except OSError:
        return None

    relative = adapter.template.relative_to(REPO_ROOT).as_posix()
    log = subprocess.run(
        ["git", "log", f"-{_HISTORY_DEPTH}", "--format=%h %ad", "--date=short",
         "--", relative],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if log.returncode != 0:
        return None

    for line in log.stdout.splitlines():
        sha, _, date = line.partition(" ")
        if not sha:
            continue
        blob = subprocess.run(
            ["git", "show", f"{sha}:{relative}"], cwd=REPO_ROOT, capture_output=True,
        )
        if blob.returncode == 0 and blob.stdout == current:
            return f"{sha} ({date.strip()})"
    return None


def discover() -> list[Adapter]:
    """Every office_example.py under back_dev_home, sorted by slug."""
    adapters: list[Adapter] = []
    for template in BACKEND_ROOT.rglob("office_example.py"):
        relative = template.relative_to(BACKEND_ROOT).parent
        # Drop the "providers" segment so slugs read as feature paths:
        # ebeam/hitachi/hardware/providers/fdc -> ebeam/hitachi/hardware/fdc
        parts = [part for part in relative.parts if part != "providers"]
        adapters.append(Adapter(
            template=template,
            target=template.with_name("office.py"),
            slug="/".join(parts),
        ))
    return sorted(adapters, key=lambda adapter: adapter.slug)


def resolve(adapters: list[Adapter], query: str) -> list[Adapter]:
    """Match a user-typed name against slugs, allowing any unique suffix.

    So "storage", "hitachi/storage" and the full slug all select the same
    adapter, while an ambiguous stem raises instead of guessing.
    """
    needle = query.strip().strip("/").lower()
    if not needle:
        return []

    exact = [a for a in adapters if a.slug.lower() == needle]
    if exact:
        return exact

    # Suffix match on whole path segments, so "fdc" matches ".../hardware/fdc"
    # but "c" matches nothing.
    matches = [
        a for a in adapters
        if a.slug.lower() == needle or a.slug.lower().endswith("/" + needle)
    ]
    if not matches:
        raise SystemExit(
            f"error: no adapter matches {query!r}.\n"
            "       Run without arguments to list every adapter."
        )
    if len(matches) > 1:
        listed = "\n".join(f"         {a.slug}" for a in matches)
        raise SystemExit(
            f"error: {query!r} is ambiguous; it matches:\n{listed}\n"
            "       Use a longer path to disambiguate."
        )
    return matches


def git_ignores(path: Path) -> bool:
    """True when git ignores `path` (office.py must never be tracked)."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def print_status(adapters: list[Adapter]) -> None:
    width = max(len(a.slug) for a in adapters)
    counts = {MISSING: 0, SYNCED: 0, STALE: 0, EDITED: 0}

    print(f"{'ADAPTER'.ljust(width)}  STATUS")
    print(f"{'-' * width}  {'-' * 7}")
    for adapter in adapters:
        status, note = classify(adapter)
        counts[status] += 1
        suffix = f"   {note}" if note else ""
        print(f"{adapter.slug.ljust(width)}  {status}{suffix}")

    total = len(adapters)
    copied = counts[SYNCED] + counts[STALE] + counts[EDITED]
    print(
        f"\n{total} adapters: {copied} copied "
        f"({counts[SYNCED]} synced, {counts[STALE]} stale, {counts[EDITED]} edited), "
        f"{counts[MISSING]} missing."
    )
    if counts[STALE]:
        print(
            f"\n{counts[STALE]} STALE: the template moved ahead and these copies still run\n"
            "OLD code against live office data. Refresh with --all (safe -- their\n"
            "exact contents are in git history), then restart Flask."
        )
    if counts[MISSING]:
        print("Copy the missing ones with: --all, or by name (e.g. storage).")
    if counts[EDITED]:
        print("EDITED copies have local changes that exist nowhere else; "
              "inspect with --diff before using --force.")


def show_diff(adapters: list[Adapter]) -> int:
    """Show how each copied office.py drifted from its template."""
    shown = 0
    for adapter in adapters:
        status, note = classify(adapter)
        if status not in (STALE, EDITED):
            continue
        shown += 1
        # flush: our stdout is block-buffered when piped, but the git
        # subprocess writes straight to the fd -- without this the header
        # lands after the diff it labels.
        header = f"{adapter.slug} [{status}]" + (f" {note}" if note else "")
        print(f"\n=== {header} ===", flush=True)
        subprocess.run(
            [
                "git", "diff", "--no-index", "--",
                str(adapter.template.relative_to(REPO_ROOT)),
                str(adapter.target.relative_to(REPO_ROOT)),
            ],
            cwd=REPO_ROOT,
        )
    if not shown:
        print("Nothing to diff -- every copied office.py matches its template.")
    return 0


def choose_interactively(adapters: list[Adapter]) -> list[Adapter]:
    """Numbered menu; blank input selects every MISSING adapter."""
    print("Select adapters to copy (comma-separated numbers, or blank for all MISSING):\n")
    for index, adapter in enumerate(adapters, start=1):
        print(f"  {index:>2}. [{adapter.status:^7}] {adapter.slug}")

    try:
        raw = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return []

    if not raw:
        return [a for a in adapters if a.status == MISSING]

    chosen: list[Adapter] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit() or not 1 <= int(token) <= len(adapters):
            raise SystemExit(f"error: {token!r} is not a number between 1 and {len(adapters)}.")
        chosen.append(adapters[int(token) - 1])
    return chosen


def copy(adapters: list[Adapter], *, force: bool, dry_run: bool) -> int:
    copied = skipped = 0

    for adapter in adapters:
        status, note = classify(adapter)
        target = adapter.target.relative_to(REPO_ROOT)

        if status == SYNCED and not force:
            print(f"  skip   {adapter.slug} (already synced)")
            skipped += 1
            continue

        if status == EDITED and not force:
            print(
                f"  SKIP   {adapter.slug} -- office.py has local changes and "
                f"matches no committed template.\n"
                f"         They exist nowhere else (office.py is gitignored). "
                f"Review with\n"
                f"         --diff {adapter.slug}, then re-run with --force to overwrite."
            )
            skipped += 1
            continue

        if dry_run:
            action = "create" if status == MISSING else "refresh" if status == STALE else "overwrite"
            detail = f" ({note})" if note else ""
            print(f"  [dry-run] would {action} {target}{detail}")
            copied += 1
            continue

        # Back up before any overwrite -- office.py can hold in-house details
        # that exist nowhere else, so losing it is unrecoverable.
        if status != MISSING:
            backup = adapter.target.with_suffix(".py.bak")
            shutil.copy2(adapter.target, backup)
            print(f"  backup {backup.relative_to(REPO_ROOT)}")

        shutil.copy2(adapter.template, adapter.target)
        copied += 1

        if git_ignores(adapter.target):
            print(f"  copy   {target}")
        else:
            # Loud, because a tracked office.py risks committing company schema.
            print(
                f"  copy   {target}\n"
                f"  WARNING: git does NOT ignore this file. Check .gitignore "
                f"before committing -- office.py must stay untracked."
            )

    verb = "would copy" if dry_run else "copied"
    print(f"\n{verb} {copied}, skipped {skipped}.")
    if not dry_run and copied:
        print("Restart Flask so the new adapters are picked up, then verify with:")
        print("  curl -s localhost:5000/api/health/providers")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sync_office_adapters",
        description="Copy providers/office_example.py templates to office.py.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  %(prog)s                        show status of all adapters\n"
            "  %(prog)s --all                  copy every MISSING adapter\n"
            "  %(prog)s storage sem_list       copy adapters by name\n"
            "  %(prog)s -i                     pick from a numbered menu\n"
            "  %(prog)s --diff                 show drift in edited office.py files\n"
        ),
    )
    parser.add_argument(
        "names", nargs="*",
        help="adapter names to copy (e.g. storage, hardware/fdc). Any unique path suffix works.",
    )
    parser.add_argument("--all", action="store_true", help="copy every MISSING adapter")
    parser.add_argument(
        "-i", "--interactive", action="store_true",
        help="choose adapters from a numbered menu",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="overwrite an existing office.py (backs it up to office.py.bak first)",
    )
    parser.add_argument("--dry-run", action="store_true", help="show what would happen, copy nothing")
    parser.add_argument(
        "--diff", action="store_true",
        help="show how edited office.py files differ from their templates",
    )
    args = parser.parse_args()

    adapters = discover()
    if not adapters:
        raise SystemExit(f"error: no office_example.py found under {BACKEND_ROOT}.")

    selected = adapters
    if args.names:
        selected = [a for name in args.names for a in resolve(adapters, name)]

    if args.diff:
        return show_diff(selected)

    if args.interactive:
        selected = choose_interactively(adapters)
        if not selected:
            print("Nothing selected.")
            return 0
    elif args.all:
        # --all means "bring this machine up to date": adapters with nothing
        # there yet, plus stale copies whose bytes are recoverable from git.
        # EDITED is excluded -- only --force may clobber unrecoverable edits.
        selected = [a for a in adapters if a.status in SAFE_TO_WRITE or args.force]
        if not selected:
            print("Every adapter is already up to date. "
                  "Use --force to also overwrite EDITED copies.")
            return 0
    elif not args.names:
        print_status(adapters)
        return 0

    return copy(selected, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
