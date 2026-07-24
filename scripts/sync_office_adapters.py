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
    EDITED   office.py differs from the template (in-house schema details
             live only there) -- never overwritten without --force

EDITED is the state worth protecting: `office.py` may carry company schema
details that are deliberately kept out of git, so a copy that clobbered it
would destroy the only copy. Overwriting therefore always requires --force,
and --force takes a .bak first.
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
EDITED = "EDITED"


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
        if not self.target.exists():
            return MISSING
        # shallow=False: compare contents, not just size+mtime. A copied file
        # keeps its own mtime, so a shallow compare would report false drift.
        return SYNCED if filecmp.cmp(self.template, self.target, shallow=False) else EDITED


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
    counts = {MISSING: 0, SYNCED: 0, EDITED: 0}

    print(f"{'ADAPTER'.ljust(width)}  STATUS")
    print(f"{'-' * width}  {'-' * 7}")
    for adapter in adapters:
        status = adapter.status
        counts[status] += 1
        print(f"{adapter.slug.ljust(width)}  {status}")

    total = len(adapters)
    live = counts[SYNCED] + counts[EDITED]
    print(
        f"\n{total} adapters: {live} copied "
        f"({counts[SYNCED]} synced, {counts[EDITED]} edited), "
        f"{counts[MISSING]} missing."
    )
    if counts[MISSING]:
        print("Copy the missing ones with: --all, or by name (e.g. storage).")


def show_diff(adapters: list[Adapter]) -> int:
    """Show how each copied office.py drifted from its template."""
    shown = 0
    for adapter in adapters:
        if adapter.status != EDITED:
            continue
        shown += 1
        # flush: our stdout is block-buffered when piped, but the git
        # subprocess writes straight to the fd -- without this the header
        # lands after the diff it labels.
        print(f"\n=== {adapter.slug} ===", flush=True)
        subprocess.run(
            [
                "git", "diff", "--no-index", "--",
                str(adapter.template.relative_to(REPO_ROOT)),
                str(adapter.target.relative_to(REPO_ROOT)),
            ],
            cwd=REPO_ROOT,
        )
    if not shown:
        print("No EDITED adapters -- every copied office.py matches its template.")
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
        status = adapter.status
        target = adapter.target.relative_to(REPO_ROOT)

        if status == SYNCED and not force:
            print(f"  skip   {adapter.slug} (already synced)")
            skipped += 1
            continue

        if status == EDITED and not force:
            print(
                f"  SKIP   {adapter.slug} -- office.py was edited locally.\n"
                f"         Its changes are not in git. Review with "
                f"--diff {adapter.slug}, then re-run with --force to overwrite."
            )
            skipped += 1
            continue

        if dry_run:
            action = "overwrite" if status != MISSING else "create"
            print(f"  [dry-run] would {action} {target}")
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
        # --all means "finish the job": every adapter not yet copied. With
        # --force it also refreshes the ones already there.
        selected = [a for a in adapters if a.status == MISSING or args.force]
        if not selected:
            print("Every adapter already has an office.py. Use --force to refresh them.")
            return 0
    elif not args.names:
        print_status(adapters)
        return 0

    return copy(selected, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
