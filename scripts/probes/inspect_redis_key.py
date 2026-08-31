"""Inspect one office Redis value in PyCharm's interactive Python console.

This is a schema-discovery worksheet, not an argument-driven CLI. **The key
comes from ``KEY_NAME`` in this file and there is no way to pass one on the
command line** - edit ``KEY_NAME``, ``ROWS`` and ``UNIQUE_COLUMNS`` below, then
run. Supplying a key as an argument is refused rather than ignored, because
``-m scripts.probes.inspect_redis_key v3_df_sem_avail`` printing ``v3_df_sem_list``'s
schema is a wrong datatables entry, not a wasted run. At the office, set the
PyCharm working directory to the repository root, then use **Run File in
Python Console**.

After execution, inspect the module variables directly in PyCharm:

    df
    df.columns
    df.dtypes
    df.head()
    raw
    kind
    client

Whatever this prints belongs in TWO places (CLAUDE.md): the schema of record in
``docs/datatables/<source>.txt`` AND the feature's ``providers/mock.py``
docstring. Mark what a run proved with ``office 확인 YYYY-MM-DD`` - a fact whose
provenance is missing gets re-litigated by the next session.

Read-only: this script only ever issues SCAN / TYPE / GET / size / sample
commands. It never writes, expires, or deletes a key.
"""

from __future__ import annotations

import sys
from pathlib import Path
# Make `back_dev_home` importable however this file was started. `-m` puts the
# working directory on sys.path and works from the repo root; running the file
# by path puts scripts/ there instead and fails on the first import below. Both
# forms get typed -- a file manager, an IDE "run this file" button and tab
# completion all produce the by-path one -- so support both.
_REPO_ROOT = Path(__file__).resolve().parents[2]
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


# THE KEY LIVES HERE. Edit these values before choosing "Run File in Python
# Console" in PyCharm; nothing on the command line can override them.
KEY_NAME = "v3_df_sem_list"
ROWS = 5
UNIQUE_COLUMNS: list[str] = []

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
    """Print the column inventory - the part that gets copied into the docs."""
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


if __name__ == "__main__":
    # Refuse a command-line key BEFORE connecting: the office Redis handshake is
    # the slow part of a run, and this one is already doomed. Silently ignoring
    # the argument was worse than either -- the operator read the schema of
    # whatever KEY_NAME happened to say and wrote it into docs/datatables under
    # the name they had typed.
    if len(sys.argv) > 1:
        raise SystemExit(
            "inspect_redis_key 는 인자를 받지 않습니다. 조사할 key 는 이 파일 안의\n"
            "KEY_NAME 이며, 편집한 뒤 다시 실행합니다.\n"
            f"  현재 KEY_NAME = {KEY_NAME!r}\n"
            f"  무시된 인자   = {sys.argv[1:]}"
        )

    # These assignments intentionally stay at module scope. PyCharm keeps them
    # in its Variables pane after "Run File in Python Console" finishes.
    client = redis_client()
    key = KEY_NAME.encode()
    kind = _key_kind(client, key)
    raw = None
    df = None

    _rule(f"KEY {KEY_NAME!r}  (redis type: {kind})")
    if kind == "none":
        raise KeyError(f"Redis key {KEY_NAME!r} does not exist")

    if kind == "string":
        raw = client.get(key)
        if raw is None:
            raise KeyError(f"Redis key {KEY_NAME!r} disappeared before GET")
        print(f"  {len(raw):,} bytes, leading bytes: {raw[:8].hex(' ')}")

        try:
            df = read_dataframe(raw, KEY_NAME)
        except LookupError as err:
            # Not a DataFrame. Plain text is the common alternative (a timestamp,
            # a JSON blob, a counter), so leave raw visible and show a preview.
            print(f"\n  not a DataFrame - {err}")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                print(f"\n  raw head: {raw[:64].hex(' ')}")
            else:
                shown = text if len(text) <= 400 else text[:400] + " ...(truncated)"
                print(f"\n  as text: {shown}")
        else:
            describe_dataframe(df, KEY_NAME, ROWS, UNIQUE_COLUMNS)
    else:
        print(f"  size: {_key_size(client, key, kind)}")
        _describe_collection(client, key, kind, ROWS)
