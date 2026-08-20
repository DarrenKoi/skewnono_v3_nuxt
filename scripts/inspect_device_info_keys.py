"""Check the office Redis device catalogs ``device_desc`` and ``r3_device_grp``.

Purpose: verify the two catalog-shaped inputs behind the **cdsem
device_statistics** office adapter (`providers/office_example.py`) - the same two
keys `_office_meas_hist.py` feeds recipe_tat / fail_issue from. This script
answers, from the office, what each key actually contains and which contract it
can feed.

The split is **user-confirmed (2026-07-31)**: ``device_desc`` carries the M-fab
(양산) catalog, ``r3_device_grp`` carries R3 (연구개발). These are the
*initial-setup* catalogs - device-statistics extracts device codes out of them
per request, rather than reading a per-request table.

Each key is still scored against BOTH contracts anyway, and fab coverage is
checked against the confirmed expectation, so a surprise (an R3 row inside
``device_desc``, a renamed column) shows up as a flagged mismatch instead of
being silently absorbed into the shape the key name promised.

Run FROM THE REPO ROOT at the office (the shared client self-loads
``back_dev_home/.env``; ``-m`` is what puts the root on ``sys.path``):

    .venv/bin/python -m scripts.inspect_device_info_keys

    # full value counts for the columns that decide fab coverage
    .venv/bin/python -m scripts.inspect_device_info_keys --unique fac_id,tech_nm

    # more sample rows, and check other key names instead
    .venv/bin/python -m scripts.inspect_device_info_keys --rows 10
    .venv/bin/python -m scripts.inspect_device_info_keys --keys device_desc,r3_device_grp

What it reports per key: existence and byte size, the full column inventory
(dtype / non-null / distinct / sample), fit against `DeviceDescRow` and
`R3DeviceGrpRow` including the ``ctn_desc`` / ``stn_desc`` spelling the docs
have recorded both ways, placeholder contamination (the literal string
``"None"`` the datatable docs warn about, which an adapter must normalize to
``""``), and fab coverage. Then across keys: ``lot_cd`` overlap (the join key
`recipe-params`/`recipe-statistics` depend on) and the four fields
`recipe_tat`'s external `lot_metadata()` importer reads.

Whatever this prints belongs in TWO places (CLAUDE.md): the schema of record in
``docs/datatables/<source>.txt`` AND the feature's ``providers/mock.py``
docstring. Mark what this run proved with ``office 확인 YYYY-MM-DD``.

Read-only: only EXISTS / TYPE / STRLEN / GET are issued. Nothing is written,
expired, or deleted.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

from pathlib import Path
# Make `back_dev_home` importable however this file was started. `-m` puts the
# working directory on sys.path and works from the repo root; running the file
# by path puts scripts/ there instead and fails on the first import below. Both
# forms get typed -- a file manager, an IDE "run this file" button and tab
# completion all produce the by-path one -- so support both.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
# Importing the package applies its stdout UTF-8 fix. `-m` gets it for free
# because -m imports the package first; running this file by path does not,
# and would then die on the ANSI code page. One line covers both.
import scripts  # noqa: E402,F401

from back_dev_home._runtime.office_redis import (  # noqa: E402
    STORE_ERRORS,
    read_dataframe,
    redis_client,
    redis_text,
)
from back_dev_home.ebeam.device_statistics.contracts import (  # noqa: E402
    DeviceDescRow,
    R3DeviceGrpRow,
)

# Reused rather than re-implemented: the sibling generic inspector already owns
# the column-inventory printer and the byte formatter, and a second copy would
# drift from it. `scripts` is a namespace package, so `-m` from the repo root
# makes this import work (same pattern as check_contract -> capture_fixtures).
from scripts.inspect_redis_key import _human_bytes, describe_dataframe  # noqa: E402


DEFAULT_KEYS = ("device_desc", "r3_device_grp")

# User-confirmed 2026-07-31: which fabs each key is supposed to carry. Checked
# rather than assumed - the script's job is to catch the case where the key name
# and the contents disagree, which is precisely what a silent assumption hides.
# Matched on the fac_id's leading character (M11/M12/... vs R3/R4).
EXPECTED_FABS = {
    "device_desc": ("M", "M-fab 양산 (M11/M12/M14/M15/M16)"),
    "r3_device_grp": ("R", "R3 연구개발"),
}

# Fields the contracts declare but the office does NOT store - `id` is a
# row identifier the mock synthesizes (e.g. "M11-TP"), so counting it as a
# missing office column would understate every fit score.
SYNTHESIZED = frozenset({"id"})

# Cells that are present-but-empty. The datatable docs are explicit that real
# None/NaN AND the literal four-character string "None" both occur, and that an
# adapter must normalize both to "" (see recipe_tat's office `_text`). Counted
# per column because "which columns are dirty" is what an adapter author needs.
PLACEHOLDER_TEXT = ("None", "none", "NONE", "nan", "NaN", "NULL", "null", "")

# Fields `back_dev_home/ebeam/_analytics.py`'s `lot_metadata()` reads
# off device_statistics.data - Recipe TAT's device quick-filter chips break if
# the office source cannot supply them (device_statistics/MIGRATION.md).
EXTERNAL_IMPORTER_FIELDS = ("lot_cd", "fac_id", "prod_catg_cd", "tech_nm")


@dataclass
class ContractSpec:
    """One target row shape, plus the office column names that satisfy it."""

    name: str
    annotations: dict
    # contract field -> extra office spellings that count as present.
    #
    # `stn_desc` is kept ONLY as a defensive alias: the real column is
    # `ctn_desc`, same as the contract, but the docs recorded it as `stn_desc`
    # once. The alias costs nothing and means an unexpected `stn_desc` reads as
    # an alias hit rather than a missing field.
    #
    # r3_device_grp's office spellings drop the `e` from `_type` (the datatable
    # doc calls plan_catg_typ / den_typ 정식).
    aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def required(self) -> list[str]:
        return [n for n in self.annotations if n not in SYNTHESIZED]

    def accepted(self, name: str) -> tuple[str, ...]:
        return (name, *self.aliases.get(name, ()))


CONTRACTS = (
    ContractSpec(
        name="DeviceDescRow",
        annotations=DeviceDescRow.__annotations__,
        aliases={"ctn_desc": ("stn_desc",)},
    ),
    ContractSpec(
        name="R3DeviceGrpRow",
        annotations=R3DeviceGrpRow.__annotations__,
        aliases={
            "ctn_desc": ("stn_desc",),
            "plan_catg_type": ("plan_catg_typ",),
            "den_type": ("den_typ",),
            "prod_grp_typ": ("prod_grp_type",),
            "gen_typ": ("gen_type",),
            # Deliberately NOT aliasing tech_cd <-> tech_nm. They are similar
            # enough to be tempting, but device_desc stores tech_nm and
            # r3_device_grp stores tech_cd as separate columns of separate
            # tables, and MIGRATION.md's external importer reads tech_nm by
            # name. Treating them as interchangeable inflates the wrong
            # contract's score and blurs the 양산/연구개발 distinction this
            # script exists to draw.
        },
    ),
)


def _rule(title: str = "") -> None:
    print(f"\n{'─' * 78}")
    if title:
        print(title)
        print("─" * 78)


def _fit(df, spec: ContractSpec) -> tuple[list[str], list[tuple[str, str]], list[str]]:
    """Split a contract's required fields into exact / aliased / missing."""
    columns = {str(c) for c in df.columns}
    exact, aliased, missing = [], [], []
    for name in spec.required:
        if name in columns:
            exact.append(name)
            continue
        match = next((alt for alt in spec.accepted(name)[1:] if alt in columns), None)
        if match:
            aliased.append((name, match))
        else:
            missing.append(name)
    return exact, aliased, missing


def report_contract_fit(df, key: str) -> None:
    """Score the key against both contracts - this is what names the mapping."""
    print("\n  contract fit (office column -> device_statistics contract):")
    scores = []
    for spec in CONTRACTS:
        exact, aliased, missing = _fit(df, spec)
        satisfied = len(exact) + len(aliased)
        total = len(spec.required)
        scores.append((satisfied / total if total else 0.0, spec.name))
        print(f"\n    {spec.name}: {satisfied}/{total} field(s) satisfiable")
        if aliased:
            for name, match in aliased:
                print(f"      alias   {match!r} satisfies contract field {name!r}")
        if missing:
            print(f"      MISSING {', '.join(missing)}")
        else:
            print("      every required field is present")

    best_score, best_name = max(scores)
    if best_score >= 0.8:
        print(f"\n    -> {key!r} looks like {best_name} ({best_score:.0%} of fields present)")
    else:
        print(
            f"\n    -> {key!r} matches NEITHER contract cleanly "
            f"(best: {best_name} at {best_score:.0%}). Record its real columns "
            "in docs/datatables/ before writing the adapter."
        )

    extra = {str(c) for c in df.columns} - {
        alt for spec in CONTRACTS for n in spec.required for alt in spec.accepted(n)
    }
    if extra:
        print(f"\n    columns no contract asks for: {', '.join(sorted(extra))}")


def report_placeholders(df) -> None:
    """Count the empty-but-present cells an adapter has to normalize to ""."""
    rows = []
    for name in df.columns:
        series = df[name]
        nulls = int(series.isna().sum())
        # No dtype guard: pandas 3 gives text columns dtype `str`, not `object`
        # (and a parquet round-trip - what the office actually serves - keeps
        # `str`), so an `is object` check silently scored every text column as
        # clean and defeated this entire report. `isin` on a numeric or datetime
        # column simply matches nothing, which is the correct answer there.
        literal = int(series.isin(PLACEHOLDER_TEXT).sum())
        if nulls or literal:
            rows.append((str(name), nulls, literal))

    print('\n  placeholder cells (adapter must normalize both kinds to ""):')
    if not rows:
        print("    (none - no NaN and no literal 'None'/'' in any column)")
        return
    print(f"    {'column':<24} {'NaN/None':>9} {'literal str':>12}")
    print(f"    {'-' * 24} {'-' * 9} {'-' * 12}")
    for name, nulls, literal in rows:
        print(f"    {name:<24} {nulls:>9,} {literal:>12,}")
    if any(literal for _, _, literal in rows):
        print("    NOTE: literal placeholders confirm the datatable docs' warning.")


def report_fab_coverage(df, key: str) -> None:
    """Which fabs this key carries - the actual test of the hvm/rnd split."""
    column = next((c for c in ("fac_id", "fab_name", "fab_id") if c in df.columns), None)
    print("\n  fab coverage:")
    if column is None:
        print("    (no fac_id / fab_name / fab_id column - cannot tell)")
        return
    counts = df[column].value_counts(dropna=False)
    print(f"    by {column}: {len(counts):,} distinct value(s)")
    for value, count in counts.items():
        print(f"      {str(value):<20} {count:>8,}")
    if column != "fac_id":
        print(
            f"    NOTE: filter key is {column!r}, not fac_id. fab_name is the "
            "canonical granular key elsewhere in this repo - record which one "
            "device_statistics should filter on."
        )

    expectation = EXPECTED_FABS.get(key)
    if expectation is None:
        print(f"    -> {key!r} carries: {', '.join(str(v) for v in counts.index[:12])}")
        return

    prefix, described = expectation
    offenders = {
        str(value): int(count)
        for value, count in counts.items()
        if not str(value).upper().startswith(prefix)
    }
    if offenders:
        print(f"    MISMATCH: expected only {described}, but also found:")
        for value, count in sorted(offenders.items(), key=lambda kv: -kv[1]):
            print(f"      {value:<20} {count:>8,}")
        print(
            "      -> the key name and its contents disagree. Do NOT wire the "
            "adapter on the key name alone; confirm the intended split first."
        )
    else:
        print(f"    -> matches the confirmed expectation: {described}")


def inspect_key(client, name: str, rows: int, unique_cols: list[str]):
    """Print everything worth knowing about one key. Returns the DataFrame."""
    key = name.encode()
    kind = redis_text(client.type(key))

    _rule(f"KEY {name!r}  (redis type: {kind})")
    if kind == "none":
        print("  MISSING - no such key. List what does exist with:")
        print("      .venv/bin/python -c \"from back_dev_home._runtime.office_redis"
              " import redis_client; print(sorted(k.decode() for k in"
              " redis_client().scan_iter('*device*')))\"")
        return None

    if kind != "string":
        print(f"  size: {kind} (not a string - a serialized DataFrame is a string key)")
        # inspect_redis_key takes no arguments: its key is the KEY_NAME
        # constant in its own source, and it refuses a supplied one.
        print(f"  Inspect it by setting KEY_NAME = {name!r} in"
              " scripts/inspect_redis_key.py, then running that script bare.")
        return None

    raw = client.get(key)
    print(f"  {_human_bytes(len(raw))} ({len(raw):,} bytes), leading bytes: {raw[:8].hex(' ')}")

    try:
        df = read_dataframe(raw, name)
    except LookupError as err:
        print(f"\n  not a DataFrame - {err}")
        return None

    describe_dataframe(df, name, rows, unique_cols)
    report_contract_fit(df, name)
    report_placeholders(df)
    report_fab_coverage(df, name)
    return df


def report_cross_key(frames: dict) -> None:
    """lot_cd joinability and the external importer's four fields."""
    _rule("ACROSS KEYS")

    named = {k: df for k, df in frames.items() if df is not None and "lot_cd" in df.columns}
    if len(named) >= 2:
        (left, left_df), (right, right_df) = list(named.items())[:2]
        lhs = set(left_df["lot_cd"].dropna().astype(str))
        rhs = set(right_df["lot_cd"].dropna().astype(str))
        shared = lhs & rhs
        print("  lot_cd overlap (the join key recipe-params / recipe-statistics use):")
        print(f"    {left:<20} {len(lhs):>8,} distinct lot_cd")
        print(f"    {right:<20} {len(rhs):>8,} distinct lot_cd")
        print(f"    shared              {len(shared):>8,}")
        if shared:
            print(f"    e.g. {', '.join(sorted(shared)[:8])}")
        else:
            print(
                "    -> disjoint vocabularies. That is EXPECTED if one key is "
                "양산 and the other 연구개발; it means the adapter must read BOTH "
                "and union them, never treat one as a superset."
            )
    else:
        print("  lot_cd overlap: needs two readable keys with a lot_cd column - skipped.")

    print("\n  fields recipe_tat's lot_metadata() reads (MIGRATION.md external importer):")
    for wanted in EXTERNAL_IMPORTER_FIELDS:
        holders = [k for k, df in frames.items() if df is not None and wanted in df.columns]
        status = ", ".join(holders) if holders else "NOWHERE - lot_metadata() would lose this field"
        print(f"    {wanted:<16} {status}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.inspect_device_info_keys",
        description=(
            "Check the office Redis keys device_desc / r3_device_grp and "
            "score them against the cdsem device_statistics contracts."
        ),
    )
    parser.add_argument(
        "--keys",
        default=",".join(DEFAULT_KEYS),
        help=f"Comma-separated key names to check (default: {','.join(DEFAULT_KEYS)}).",
    )
    parser.add_argument(
        "--rows", type=int, default=5, help="Sample rows to print per key (default: 5)."
    )
    parser.add_argument(
        "--unique",
        default="",
        help="Comma-separated columns to print full value counts for (e.g. fac_id,tech_nm).",
    )
    args = parser.parse_args(argv)

    keys = [name.strip() for name in args.keys.split(",") if name.strip()]
    unique_cols = [name.strip() for name in args.unique.split(",") if name.strip()]

    try:
        client = redis_client()
    except RuntimeError as err:
        print(f"Redis is not configured: {err}", file=sys.stderr)
        return 2

    try:
        frames = {name: inspect_key(client, name, args.rows, unique_cols) for name in keys}
        report_cross_key(frames)

        _rule("NEXT")
        print(
            "  Record what this run proved in BOTH places (CLAUDE.md):\n"
            "    1. docs/datatables/device_desc.txt / r3_device_grp.txt\n"
            "    2. back_dev_home/ebeam/device_statistics/providers/mock.py "
            "docstring\n"
            "  Mark each fact 'office 확인 YYYY-MM-DD'. Then implement\n"
            "  device_statistics/providers/office.py per its MIGRATION.md.\n"
        )
        return 0 if all(df is not None for df in frames.values()) else 1
    except STORE_ERRORS as err:
        print(f"\nRedis is unreachable: {type(err).__name__}: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
