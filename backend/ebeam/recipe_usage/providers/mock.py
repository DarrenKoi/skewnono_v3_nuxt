"""Deterministic Phase 1 adapter for recipe_usage (VeritySEM / Provision).

Office counterpart -- schema of record:
`docs/datatables/veritysem/recipe_usage.txt`. The three loaders return rows in
the Redis keys' OWN column shape; `_shape.py` folds them into the contract for
both providers.

What this stands in for (user-confirmed 2026-11-12 unless marked):

    v3_df_verity_recipes / v3_df_provision_recipes            list keys
        one row per (eqp_id, recipe_id, fab_id) -- every recipe a tool ever
        started a job for. Real scale: 24,352 rows / 55 tools / 9,451 recipes
        (VeritySEM), 27,386 / 54 / 11,040 (Provision).
    v3_df_verity_recipe_usage / v3_df_provision_recipe_usage  usage keys
        one row per (dt, eqp_id, recipe_id). Real scale: 76,995 rows / 54
        tools / 2,220 recipes (VeritySEM), 27,358 / 53 / 1,708 (Provision).
    v3_verity_unique_rcp_list / v3_provision_unique_rcp_list  resident hashes
        field = eqp_id, value = JSON array of recipe full names found on the
        tool. Real VeritySEM overlap: 630 recipes only here, 8,421 only in the
        list key.

Properties copied from the office, each of which a tidier mock would hide:

* `(eqp_id, recipe_id)` is NOT unique in the list keys: some pairs appear
  under two `fab_id`s. `fab_id` is MES history and includes C2 / X1, which are
  no `fab_name`.
* VeritySEM `recipe_id` is `<TYPE>/<DEVICE>/<LAYER>/<JOB>` -- except for a
  handful that do not have exactly 3 slashes (10 rows at the office). Provision
  is `<ProductID>/<LayerID>/<RecipeName>` and ships those three as columns.
* The roster's `fac_id=R3, fab_name=R4` tools are kept as they are.
* The latest `dt` is YESTERDAY; today never exists. The loaded partitions span
  90 days but the rows start later and the first days hold 1-2 rows each.
* `fail_runs == runs` rows are common, and a run with no JobEnd contributes
  `meas_min` 0. No nulls; `meas_min` is the only float.
* Every usage `(eqp_id, recipe_id)` is also in the list key, the list key's
  `n_uses` is never below the runs in the usage key, and a recipe absent from
  the usage key was last used before the partitions start.
* One roster tool has no usage row at all: it must still appear, with zeros.

Where this deliberately differs or guesses:

* Scale is a few hundred recipes per family, not ~10k.
* OFFICE-VERIFY: the two Provision resident/tools_in_rcp key NAMES (see
  `FAMILY_KEYS`); only their existence and shape are confirmed.
* OFFICE-VERIFY: `first_used` / `last_used` / `first_start` / `last_start`
  are written `YYYY-MM-DD HH:MM:SS`. The office note says "HH:MMSS".
* OFFICE-VERIFY: a row's `fab_id` usually equals the tool's `fab_name`. Only
  "C2 and X1 exist and are not fab_names" is confirmed.
* OFFICE-VERIFY: VeritySEM tools whose roster `veridity` is not "On" are
  absent from the resident hash. The hash is parsed from
  `Veridity/Reports/*.KLA` and its refresh is not guaranteed; which tools it
  actually misses is unknown.
* The recipe vocabulary and every number are fabricated.

Like recipe_tat's ANCHOR_TIME, the anchor is the wall clock at module load, so
a dev server left running over midnight keeps yesterday's "yesterday".
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import NamedTuple

from backend.ebeam._tool_specs import model_to_tool_type
from backend.ebeam.recipe_usage.contracts import AmatToolType
from backend.ebeam.recipe_usage.providers._shape import (
    SPLIT_COLUMNS,
    ListRow,
    UsageRow,
)
from backend.sem_list.providers.mock import get_sem_list


__all__ = ["ANCHOR_DATE", "load_list_rows", "load_resident", "load_usage_rows"]

KST = timezone(timedelta(hours=9), "KST")
ANCHOR_DATE = datetime.now(KST).date() - timedelta(days=1)

N_RECIPES = 240
N_TOOL_ONLY = 16          # resident on a tool, never started via MES (real: ~7%)
N_BOTH = 28               # in the list key AND resident (real: ~11%)
PARTITION_DAYS = 90
FIRST_ROW_DAYS_AGO = 74   # rows start later than the partitions do
SPARSE_HEAD_DAYS = 15     # ... and the first days are nearly empty
STRAY_FAB_IDS = ("C2", "X1")

_PRODUCTS = ("4S8", "5T2", "7H1", "3D9", "6K4", "8V3")
_LAYERS = ("CBL", "POM", "WL", "BL", "SN", "GATE", "M0", "M1", "VIA", "ACT")
_STEPS = ("C0A", "D1B", "E2A", "F0C")
_OPTIONS = ("UPH_4P", "STD", "HR_2P", "FULL")
_PROVISION_NAMES = ("AVIS", "CDU", "OVL_CHK", "PROFILE", "INLINE", "MON")
_VERITY_TYPES = ("FI", "DI", "AEI", "ADI", "MON")
_VERITY_DEVICES = ("S2", "T5", "H7", "D9", "K4", "V3")
# The office has ids like these: fewer or more than 3 slashes. Anything that
# splits a VeritySEM id into four parts breaks on them.
_VERITY_ODD_IDS = ("MON/S2/DAILY", "MON/T5/WEEKLY", "FI/S2/POM/S2_POM/REWORK", "DI/H7/BL/H7_BL/V2/OLD")


class _Raw(NamedTuple):
    list_rows: tuple[ListRow, ...]
    usage_rows: tuple[UsageRow, ...]
    resident: dict[str, list[str]]


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _recipes(tool_type: AmatToolType, rng: random.Random) -> list[dict[str, str]]:
    """Recipe ids, with the Provision split columns the list key carries."""
    odd_ids = _VERITY_ODD_IDS if tool_type == "veritysem" else ()
    recipes: dict[str, dict[str, str]] = {}
    while len(recipes) < N_RECIPES - len(odd_ids):
        layer = rng.choice(_LAYERS)
        if tool_type == "provision":
            product = rng.choice(_PRODUCTS)
            layer_id = f"{product}_{layer}_{rng.choice(_STEPS)}_{rng.choice(_OPTIONS)}"
            name = rng.choice(_PROVISION_NAMES)
            recipes[f"{product}/{layer_id}/{name}"] = dict(
                zip(SPLIT_COLUMNS, (product, layer_id, name), strict=True)
            )
        else:
            device = rng.choice(_VERITY_DEVICES)
            job = f"{device}_{layer}" + rng.choice(("", "", "_V2", "_HR"))
            recipes[f"{rng.choice(_VERITY_TYPES)}/{device}/{layer}/{job}"] = {}
    # Last, so they land among the MES recipes: the odd ids are list-key rows.
    recipes.update({recipe_id: {} for recipe_id in odd_ids})
    return [{"recipe_id": recipe_id, **split} for recipe_id, split in recipes.items()]


def _usage_row(tool: dict, recipe_id: str, day: date, rng: random.Random) -> UsageRow:
    runs = rng.randint(1, 12)
    roll = rng.random()
    if roll < 0.18:
        fail_runs = runs
    elif roll < 0.30 and runs > 1:
        fail_runs = rng.randint(1, runs - 1)
    else:
        fail_runs = 0
    # Most failures are a missing JobEnd, which records 0 minutes; the rest
    # ended but were not adopted by MES and keep their time. A day where
    # nothing finished is usually one cause, hence a whole row at 0 minutes.
    if fail_runs == runs and rng.random() < 0.75:
        no_jobend = runs
    else:
        no_jobend = sum(1 for _ in range(fail_runs) if rng.random() < 0.8)
    meas_min = round(sum((rng.uniform(3, 45) for _ in range(runs - no_jobend)), 0.0), 2)
    midnight = datetime.combine(day, datetime.min.time())
    first, last = sorted(rng.randrange(86400) for _ in range(2))
    if runs == 1:
        last = first
    return UsageRow(
        dt=day.isoformat(),
        eqp_id=tool["eqp_id"],
        fac_id=tool["fac_id"],
        fab_name=tool["fab_name"],
        recipe_id=recipe_id,
        runs=runs,
        wafers=sum(rng.randint(1, 25) for _ in range(runs)),
        meas_min=meas_min,
        fail_runs=fail_runs,
        first_start=_stamp(midnight + timedelta(seconds=first)),
        last_start=_stamp(midnight + timedelta(seconds=last)),
    )


@lru_cache(maxsize=None)
def _generate(tool_type: AmatToolType) -> _Raw:
    rng = random.Random(f"recipe_usage:{tool_type}")
    # Same rule as the roster the responses are built from: this family only,
    # first row per eqp_id (the sem_list mock repeats a few ids).
    by_id: dict[str, dict] = {}
    for row in get_sem_list():
        if model_to_tool_type(row["eqp_model_cd"]) == tool_type:
            by_id.setdefault(row["eqp_id"], row)
    tools = [by_id[eqp_id] for eqp_id in sorted(by_id)]
    idle_tool = tools[-1]["eqp_id"]
    fab_names = sorted({tool["fab_name"] for tool in tools})

    recipes = _recipes(tool_type, rng)
    tool_only = recipes[:N_TOOL_ONLY]
    in_mes = recipes[N_TOOL_ONLY:]
    both = {recipe["recipe_id"] for recipe in in_mes[:N_BOTH]}

    # (tool, recipe) pairs the list key knows, and which of them ran recently.
    pairs: list[tuple[dict, dict, float]] = []
    for recipe in in_mes:
        active = rng.random() < 0.25
        for tool in rng.sample(tools, rng.choice((1, 1, 2, 2, 3, 4))):
            running = active and tool["eqp_id"] != idle_tool and rng.random() < 0.8
            pairs.append((tool, recipe, rng.uniform(0.15, 0.7) if running else 0.0))

    first_day = ANCHOR_DATE - timedelta(days=FIRST_ROW_DAYS_AGO)
    partition_start = datetime.combine(
        ANCHOR_DATE - timedelta(days=PARTITION_DAYS - 1), datetime.min.time()
    )
    running_pairs = [pair for pair in pairs if pair[2]]
    usage: dict[tuple[str, str, str], UsageRow] = {}
    for offset in range(FIRST_ROW_DAYS_AGO + 1):
        day = first_day + timedelta(days=offset)
        if offset < SPARSE_HEAD_DAYS:
            todays = rng.sample(running_pairs, rng.randint(1, 2))
        else:
            todays = [pair for pair in running_pairs if rng.random() < pair[2]]
        for tool, recipe, _rate in todays:
            row = _usage_row(tool, recipe["recipe_id"], day, rng)
            usage[(row["dt"], row["eqp_id"], row["recipe_id"])] = row
    usage_rows = tuple(usage[key] for key in sorted(usage))

    recent: dict[tuple[str, str], list[UsageRow]] = {}
    for row in usage_rows:
        recent.setdefault((row["eqp_id"], row["recipe_id"]), []).append(row)

    list_rows: list[ListRow] = []
    for tool, recipe, _rate in pairs:
        runs = recent.get((tool["eqp_id"], recipe["recipe_id"]), [])
        n_uses = sum(row["runs"] for row in runs) + rng.randint(0 if runs else 1, 400)
        first_used = partition_start - timedelta(seconds=rng.randrange(86400, 800 * 86400))
        last_used = (
            max(row["last_start"] for row in runs) if runs
            else _stamp(first_used + (partition_start - first_used) * rng.random())
        )
        base = {
            "eqp_id": tool["eqp_id"],
            "fac_id": tool["fac_id"],
            "fab_name": tool["fab_name"],
            **recipe,
        }
        other_fab_ids = [*STRAY_FAB_IDS, *(f for f in fab_names if f != tool["fab_name"])]
        roll = rng.random()
        if roll < 0.10 and n_uses > 1:
            # The same (tool, recipe) under two fab_ids: the earlier history
            # sits under the other one.
            earlier = rng.randint(1, n_uses - 1)
            handover = first_used + (partition_start - first_used) * rng.random()
            list_rows.append(ListRow(
                **base, fab_id=rng.choice(other_fab_ids), n_uses=earlier,
                first_used=_stamp(first_used), last_used=_stamp(handover),
            ))
            list_rows.append(ListRow(
                **base, fab_id=tool["fab_name"], n_uses=n_uses - earlier,
                first_used=_stamp(handover), last_used=max(last_used, _stamp(handover)),
            ))
        else:
            list_rows.append(ListRow(
                **base,
                fab_id=rng.choice(STRAY_FAB_IDS) if roll < 0.14 else tool["fab_name"],
                n_uses=n_uses, first_used=_stamp(first_used), last_used=last_used,
            ))

    resident: dict[str, set[str]] = {
        tool["eqp_id"]: set() for tool in tools
        if tool_type != "veritysem" or tool.get("veridity") == "On"
    }
    hosts = [tool for tool in tools if tool["eqp_id"] in resident]
    for tool, recipe, _rate in pairs:
        if recipe["recipe_id"] in both and tool["eqp_id"] in resident:
            resident[tool["eqp_id"]].add(recipe["recipe_id"])
    for recipe in tool_only:
        for tool in rng.sample(hosts, rng.randint(1, 3)):
            resident[tool["eqp_id"]].add(recipe["recipe_id"])

    return _Raw(
        tuple(list_rows),
        usage_rows,
        {eqp_id: sorted(recipe_ids) for eqp_id, recipe_ids in resident.items()},
    )


def load_list_rows(tool_type: AmatToolType) -> tuple[ListRow, ...]:
    return _generate(tool_type).list_rows


def load_usage_rows(tool_type: AmatToolType) -> tuple[UsageRow, ...]:
    return _generate(tool_type).usage_rows


def load_resident(tool_type: AmatToolType) -> dict[str, list[str]]:
    return _generate(tool_type).resident
