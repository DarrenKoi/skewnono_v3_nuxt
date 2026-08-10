"""One-shot office setup: create every runnable `office.py` on this machine.

Run it after a fresh clone at the office, and again after any `git pull`
that touched a template. No arguments needed:

    .venv/bin/python -m scripts.setup_office_adapters

It creates `providers/office.py` for adapters that have none, and refreshes
copies that have fallen behind their template. Then restart Flask
(`office_registry` scans for office.py once per process).

Two kinds of adapter are deliberately left alone:

  * STUBS -- a template whose functions just raise NotImplementedError,
    because that feature has not been wired to an office source yet.
    Copying one is actively harmful: `office.py` existing IS the switch
    (see `_runtime/office_registry.py`), so it would flip that feature to
    office mode and turn a working mock page into a 500. Pass
    --include-stubs only if you are about to implement one.
  * EDITED -- a copy holding local changes that match no committed
    template. office.py is gitignored, so those changes exist nowhere
    else. Use `sync_office_adapters.py --diff` to inspect and --force to
    overwrite.

For status, per-adapter selection, diffs and forced overwrites, use the
fuller tool: `.venv/bin/python -m scripts.sync_office_adapters`.
"""

from __future__ import annotations

import argparse
import shutil
import sys

from scripts.sync_office_adapters import (
    EDITED,
    MISSING,
    REPO_ROOT,
    SAFE_TO_WRITE,
    STALE,
    classify,
    discover,
    git_ignores,
    is_stub,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="setup_office_adapters",
        description="Create/refresh every runnable providers/office.py. No arguments needed.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show what would happen, copy nothing"
    )
    parser.add_argument(
        "--include-stubs", action="store_true",
        help="also copy not-yet-implemented templates (flips those features to a 500)",
    )
    args = parser.parse_args(argv)

    created = refreshed = 0
    skipped_stub: list[str] = []
    skipped_edited: list[str] = []
    warnings: list[str] = []

    for adapter in discover():
        status, note = classify(adapter)
        if status not in SAFE_TO_WRITE:
            if status == EDITED:
                skipped_edited.append(adapter.slug)
            continue
        if is_stub(adapter.template) and not args.include_stubs:
            skipped_stub.append(adapter.slug)
            continue

        target = adapter.target.relative_to(REPO_ROOT)
        if args.dry_run:
            verb = "create" if status == MISSING else "refresh"
            print(f"  [dry-run] would {verb} {target}")
        else:
            if status == STALE:
                shutil.copy2(adapter.target, adapter.target.with_suffix(".py.bak"))
            shutil.copy2(adapter.template, adapter.target)
            print(f"  {'create ' if status == MISSING else 'refresh'} {target}"
                  + (f"  (was {note})" if note else ""))
            if not git_ignores(adapter.target):
                warnings.append(str(target))

        created += status == MISSING
        refreshed += status == STALE

    verb = "Would create" if args.dry_run else "Created"
    tail = "would refresh" if args.dry_run else "refreshed"
    print(f"\n{verb} {created}, {tail} {refreshed}.")

    if skipped_stub:
        print(
            f"\nSkipped {len(skipped_stub)} not-yet-implemented template(s) - copying\n"
            f"these would switch a working mock page to a 500:\n  "
            + "\n  ".join(skipped_stub)
            + "\n(Use --include-stubs when you start wiring one.)"
        )
    if skipped_edited:
        print(
            f"\nSkipped {len(skipped_edited)} locally-edited copy/copies (changes exist\n"
            f"nowhere else):\n  " + "\n  ".join(skipped_edited)
            + "\nInspect: python -m scripts.sync_office_adapters --diff <name>"
        )
    if warnings:
        print("\nWARNING: git does NOT ignore these - office.py must stay untracked:")
        for path in warnings:
            print(f"  {path}")
    if (created or refreshed) and not args.dry_run:
        # 5000 at the office, 5050 at home (5000 is macOS AirPlay).
        print("\nRestart Flask, then verify: "
              "curl -s localhost:${PORT:-5000}/api/health/providers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
