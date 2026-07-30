"""Inspect an office Redis value — as a DataFrame when it is one, as itself otherwise.

Schema-discovery tool. Every office adapter reads a key it *believes* holds a
parquet-serialized DataFrame with a known set of columns, and the only way to
learn what a key really contains is to look at it from the office: the store is
unreachable from home. This script is that look.

Run FROM THE REPO ROOT at the office (the shared client self-loads
``back_dev_home/.env``; ``-m`` is what puts the root on ``sys.path``):

    # which keys exist?
    .venv/bin/python -m scripts.inspect_redis_key
    .venv/bin/python -m scripts.inspect_redis_key --pattern "v3_df_sem*"

    # what is inside one (or several) of them?
    .venv/bin/python -m scripts.inspect_redis_key v3_df_sem_list
    .venv/bin/python -m scripts.inspect_redis_key v3_df_sem_list v3_df_sem_avail

    # what values does a column actually take?
    .venv/bin/python -m scripts.inspect_redis_key v3_df_sem_list --unique fab_name,eqp_model_cd

Whatever this prints belongs in TWO places (CLAUDE.md): the schema of record in
``docs/datatables/<source>.txt`` AND the feature's ``providers/mock.py``
docstring. Mark what a run proved with ``office 확인 YYYY-MM-DD`` — a fact whose
provenance is missing gets re-litigated by the next session.

Read-only: this script only ever issues SCAN / TYPE / GET / size / sample
commands. It never writes, expires, or deletes a key.
"""

from __future__ import annotations

import argparse
import sys

from back_dev_home._runtime.office_redis import (
    STORE_ERRORS,
    read_dataframe,
    redis_client,
    redis_text,
)


DEFAULT_PATTERN = "v3_*"

# SCAN batch size. Larger than redis-py's default 10 so listing a few hundred
# keys is a couple of round trips instead of dozens; still small enough not to
# block the server on a big keyspace.
_SCAN_COUNT = 500

# Per-type "how big is this" command. A DataFrame key is a plain string, so
# strlen is its serialized byte length; the collection types report cardinality.
_SIZE_COMMAND = {
    "string": ("bytes", "strlen"),
    "hash": ("fields", "hlen"),
    "list": ("items", "llen"),
    "set": ("members", "scard"),
    "zset": ("members", "zcard"),
}


def _rule(title: str = "") -> None:
    print(f"\n{'─' * 78}")
    if title:
        print(title)
        print("─" * 78)


def _human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:,.0f} {unit}" if unit == "B" else f"{value:,.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _key_kind(client, key: bytes) -> str:
    return redis_text(client.type(key))


def _key_size(client, key: bytes, kind: str) -> str:
    """Cardinality (or byte length) of a key, without fetching its value."""
    label_command = _SIZE_COMMAND.get(kind)
    if label_command is None:
        return "?"
    label, command = label_command
    try:
        count = getattr(client, command)(key)
    except STORE_ERRORS:
        return "?"
    return f"{_human_bytes(count)}" if label == "bytes" else f"{count:,} {label}"


def list_keys(client, pattern: str, limit: int) -> int:
    """Print every key matching ``pattern`` with its type and size.

    SCAN, never KEYS: the office Redis is shared, and KEYS blocks the whole
    server while it walks the keyspace.
    """
    _rule(f"KEYS matching {pattern!r}")
    found = sorted(client.scan_iter(match=pattern, count=_SCAN_COUNT))
    if not found:
        print("(none — try a wider --pattern, e.g. --pattern '*')")
        return 0

    shown = found[:limit]
    for key in shown:
        kind = _key_kind(client, key)
        print(f"  {redis_text(key):44s} {kind:8s} {_key_size(client, key, kind)}")

    print(f"\n  {len(found):,} key(s) matched", end="")
    print(f", showing first {len(shown)} (raise --limit for more)" if len(found) > len(shown) else "")
    return len(found)


def _first_sample(series) -> str:
    """One representative value, preferring a non-null one."""
    import pandas as pd

    present = series.dropna()
    if present.empty:
        return "(all null)"
    value = present.iloc[0]
    text = str(value)
    if isinstance(value, pd.Timestamp):
        text = value.isoformat()
    return text if len(text) <= 34 else text[:31] + "..."


def describe_dataframe(df, key: str, rows: int, unique_cols: list[str]) -> None:
    """Print the column inventory — the part that gets copied into the docs."""
    import pandas as pd

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_colwidth", 30)

    print(f"  shape:   {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"  index:   {type(df.index).__name__}")
    print(f"  memory:  {_human_bytes(int(df.memory_usage(deep=True).sum()))}")

    # dtype gets 20 chars: "datetime64[us, UTC]" is 19 and overflowed a
    # narrower column, which shifted every count to its right out of alignment.
    print(f"\n  {'column':<24} {'dtype':<20} {'non-null':>9} {'nunique':>9}  sample")
    print(f"  {'-' * 24} {'-' * 20} {'-' * 9} {'-' * 9}  {'-' * 34}")
    for name in df.columns:
        series = df[name]
        try:
            distinct = f"{series.nunique(dropna=True):,}"
        except TypeError:  # unhashable cells (list/dict columns)
            distinct = "n/a"
        print(
            f"  {str(name):<24} {str(series.dtype):<20} "
            f"{series.notna().sum():>9,} {distinct:>9}  {_first_sample(series)}"
        )

    if rows > 0:
        print(f"\n  first {min(rows, len(df))} row(s):")
        print(df.head(rows).to_string(max_rows=rows))

    for name in unique_cols:
        if name not in df.columns:
            print(f"\n  --unique {name!r}: no such column (have {sorted(map(str, df.columns))})")
            continue
        counts = df[name].value_counts(dropna=False)
        print(f"\n  --unique {name}: {len(counts):,} distinct value(s)")
        for value, count in counts.items():
            print(f"      {str(value):<36} {count:>7,}")


def _describe_collection(client, key: bytes, kind: str, rows: int) -> None:
    """Sample a hash / set / list / zset without pulling the whole thing."""
    if kind == "hash":
        # HSCAN so a 100k-field hash does not land in memory just to show 5.
        _, fields = client.hscan(key, count=max(rows, 1))
        print(f"  first {min(rows, len(fields))} field(s):")
        for field, value in list(fields.items())[:rows]:
            shown = redis_text(value)
            print(f"      {redis_text(field):<40} {shown if len(shown) <= 60 else shown[:57] + '...'}")
    elif kind == "set":
        _, members = client.sscan(key, count=max(rows, 1))
        print(f"  first {min(rows, len(members))} member(s):")
        for member in members[:rows]:
            print(f"      {redis_text(member)}")
    elif kind == "list":
        print(f"  first {rows} item(s):")
        for item in client.lrange(key, 0, rows - 1):
            print(f"      {redis_text(item)}")
    elif kind == "zset":
        print(f"  top {rows} member(s) by score:")
        for member, score in client.zrevrange(key, 0, rows - 1, withscores=True):
            print(f"      {redis_text(member):<40} {score}")
    else:
        print(f"  (no sampler for Redis type {kind!r})")


def _describe_string(client, key: bytes, name: str, rows: int, unique_cols: list[str]) -> None:
    """A string value: a serialized DataFrame if it deserializes as one, else text."""
    raw = client.get(key)
    print(f"  {len(raw):,} bytes, leading bytes: {raw[:8].hex(' ')}")

    try:
        df = read_dataframe(raw, name)
    except LookupError as err:
        # Not a DataFrame. Plain text is the common alternative (a timestamp, a
        # JSON blob, a counter), so show that rather than only the diagnostic.
        print(f"\n  not a DataFrame — {err}")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            print(f"\n  raw head: {raw[:64].hex(' ')}")
        else:
            print(f"\n  as text: {text if len(text) <= 400 else text[:400] + ' ...(truncated)'}")
        return

    describe_dataframe(df, name, rows, unique_cols)


def inspect_key(client, name: str, rows: int, unique_cols: list[str]) -> bool:
    """Print everything worth knowing about one key. False if it is missing."""
    key = name.encode()
    kind = _key_kind(client, key)

    _rule(f"KEY {name!r}  (redis type: {kind})")
    if kind == "none":
        print("  MISSING — no such key. List what does exist with:")
        print("      .venv/bin/python -m scripts.inspect_redis_key --pattern '*'")
        return False

    if kind == "string":
        _describe_string(client, key, name, rows, unique_cols)
    else:
        print(f"  size: {_key_size(client, key, kind)}")
        _describe_collection(client, key, kind, rows)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.inspect_redis_key",
        description="Inspect office Redis keys — DataFrame columns, or a sample of a collection.",
    )
    parser.add_argument(
        "keys",
        nargs="*",
        help="Key name(s) to inspect. With none, lists keys matching --pattern.",
    )
    parser.add_argument(
        "--pattern",
        default=DEFAULT_PATTERN,
        help=f"Glob for the key listing (default: {DEFAULT_PATTERN!r}). Use '*' for everything.",
    )
    parser.add_argument(
        "--limit", type=int, default=100, help="Max keys to print when listing (default: 100)."
    )
    parser.add_argument(
        "--rows", type=int, default=5, help="Sample rows / fields to print per key (default: 5)."
    )
    parser.add_argument(
        "--unique",
        default="",
        help="Comma-separated columns to print full value counts for (e.g. fab_name,eqp_model_cd).",
    )
    args = parser.parse_args(argv)

    unique_cols = [name.strip() for name in args.unique.split(",") if name.strip()]

    try:
        client = redis_client()
    except RuntimeError as err:
        print(f"Redis is not configured: {err}", file=sys.stderr)
        return 2

    try:
        if not args.keys:
            list_keys(client, args.pattern, args.limit)
            print("\nPass one or more key names to inspect their contents.")
            return 0

        missing = [name for name in args.keys if not inspect_key(client, name, args.rows, unique_cols)]
        print()
        return 1 if missing else 0
    except STORE_ERRORS as err:
        print(f"\nRedis is unreachable: {type(err).__name__}: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
