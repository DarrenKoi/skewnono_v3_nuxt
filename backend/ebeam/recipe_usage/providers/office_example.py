# TEMPLATE — copy to office.py at the office, then run. office.py is
# gitignored (backend/**/providers/office.py); this office_example.py
# is the tracked skeleton and the source of truth — edit it at home.
"""Phase 2/3 adapter for the AMAT recipe keys (Redis). NEVER RUN AT THE OFFICE YET.

Written at home from `docs/datatables/veritysem/recipe_usage.txt`
(user-confirmed 2026-11-12); nothing here has touched the real keys.

This adapter only READS and NORMALIZES. It returns each key in its own column
shape and `data.py` + `providers/_shape.py` do every aggregation, the roster
join (`sem_list`) and the fab scoping -- so do not filter or sum here.

Sources per family (names in `_shape.FAMILY_KEYS`):

* list key   -- DataFrame, one row per (eqp_id, recipe_id, fab_id).
* usage key  -- DataFrame, one row per (dt, eqp_id, recipe_id).
* resident   -- hash, field = eqp_id, value = JSON array of recipe full names.
  Its refresh is not guaranteed, so a missing or empty hash is an empty
  mapping (the catalog then shows MES recipes only), not an error.
* `tools_in_rcp_{fab}` is documented and deliberately not read: it is the
  resident hash inverted.

OFFICE-VERIFY, in the order worth checking on the first run (`python -m
backend.ebeam.recipe_usage.providers.office` prints all of it):

1. The two DataFrame keys are parquet like `v3_df_sem_list`
   (`read_dataframe` also accepts JSON / pickle, so this fails soft).
2. The Provision hash is named `v3_provision_unique_rcp_list`. If the smoke
   run prints 0 tools for it, fix the name in `_shape.FAMILY_KEYS`.
3. The time columns are text. A datetime column is handled too and comes out
   as `YYYY-MM-DD HH:MM:SS`, the format the mock uses.

Null handling: the office note says the usage keys are null-free. This adapter
does not rely on it -- NaN/None become ""/0 and a row without an eqp_id or a
recipe_id is dropped, because neither can be keyed.

Connection settings come from ``REDIS_HOST`` / ``REDIS_PORT`` /
``REDIS_PASSWORD`` in ``backend/.env``. `sem_list` must resolve to office
too (`_OFFICE_DEPENDENCIES`): the roster is the join for every row here.
"""

from __future__ import annotations

import json
from typing import Callable

import pandas as pd

from backend._runtime.office_redis import (
    read_dataframe,
    redis_client,
    redis_text,
)
from backend.ebeam.recipe_usage.contracts import AmatToolType
from backend.ebeam.recipe_usage.providers._shape import (
    FAMILY_KEYS,
    USAGE_COLUMNS,
    ListRow,
    UsageRow,
)


def _is_missing(value) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _text(value) -> str:
    return "" if _is_missing(value) else str(value).strip()


def _int(value) -> int:
    return 0 if _is_missing(value) else int(float(value))


def _float(value) -> float:
    return 0.0 if _is_missing(value) else float(value)


def _stamp(value) -> str:
    if hasattr(value, "strftime") and not _is_missing(value):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return _text(value)


def _day(value) -> str:
    return _stamp(value)[:10]


# Anything not named here is text.
_COERCE: dict[str, Callable] = {
    "n_uses": _int,
    "runs": _int,
    "wafers": _int,
    "fail_runs": _int,
    "meas_min": _float,
    "dt": _day,
    "first_used": _stamp,
    "last_used": _stamp,
    "first_start": _stamp,
    "last_start": _stamp,
}


def _normalize(df: pd.DataFrame, key: str, columns: tuple[str, ...]) -> list[dict]:
    """DataFrame -> rows with exactly `columns`, typed, unkeyable rows dropped."""
    missing = set(columns) - set(df.columns)
    if missing:
        # Bare LookupError: the app factory answers a JSON 502 for it.
        raise LookupError(
            f"Redis key {key!r} DataFrame is missing columns: {sorted(missing)} "
            f"(got {sorted(df.columns)})"
        )
    rows = []
    for record in df[list(columns)].to_dict(orient="records"):
        row = {
            column: _COERCE.get(column, _text)(value)
            for column, value in record.items()
        }
        if row["eqp_id"] and row["recipe_id"]:
            rows.append(row)
    return rows


# ponytail: every request re-reads and re-parses the whole key (the largest is
# ~77k rows). Add `_office_search.ttl_cache` here if the status page feels slow;
# the keys change once a day.
def _load(key: str, columns: tuple[str, ...]) -> list[dict]:
    raw = redis_client().get(key)
    if raw is None:
        raise LookupError(
            f"Redis key {key!r} not found — check REDIS_HOST/REDIS_PORT/"
            "REDIS_PASSWORD in backend/.env and that the daily recipe job "
            "has populated the key."
        )
    return _normalize(read_dataframe(raw, key), key, columns)


def load_list_rows(tool_type: AmatToolType) -> list[ListRow]:
    keys = FAMILY_KEYS[tool_type]
    return _load(keys.list_key, keys.list_columns)


def load_usage_rows(tool_type: AmatToolType) -> list[UsageRow]:
    return _load(FAMILY_KEYS[tool_type].usage_key, USAGE_COLUMNS)


def _parse_resident(raw: dict) -> dict[str, list[str]]:
    """`hgetall` result -> {eqp_id: [recipe_id, ...]}; unparseable fields skipped."""
    resident: dict[str, list[str]] = {}
    for field, value in raw.items():
        try:
            recipe_ids = json.loads(redis_text(value))
        except ValueError:
            continue
        if isinstance(recipe_ids, list):
            resident[redis_text(field).strip()] = [
                str(recipe_id).strip() for recipe_id in recipe_ids
                if str(recipe_id).strip()
            ]
    return resident


def load_resident(tool_type: AmatToolType) -> dict[str, list[str]]:
    return _parse_resident(redis_client().hgetall(FAMILY_KEYS[tool_type].resident_hash))


if __name__ == "__main__":
    from collections import Counter

    for family, family_keys in FAMILY_KEYS.items():
        listed = load_list_rows(family)
        used = load_usage_rows(family)
        on_tool = load_resident(family)
        days = sorted({row["dt"] for row in used})
        print(f"== {family}")
        print(f"  {family_keys.list_key}: {len(listed)} rows, "
              f"{len({r['eqp_id'] for r in listed})} tools, "
              f"{len({r['recipe_id'] for r in listed})} recipes")
        print(f"    slashes per recipe_id: {dict(Counter(r['recipe_id'].count('/') for r in listed))}")
        print(f"    sample: {listed[:1]}")
        print(f"  {family_keys.usage_key}: {len(used)} rows, dt {days[:1]} .. {days[-1:]}")
        print(f"    sample: {used[:1]}")
        print(f"  {family_keys.resident_hash}: {len(on_tool)} tools, "
              f"{len({r for ids in on_tool.values() for r in ids})} recipes")
