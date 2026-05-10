"""횡전개(lateral) — recipe ↔ tools mapping mock.

Production sources (deferred):
  - Redis hash `v3_tools_in_recipe_<fab>` keyed by recipe_name → list[eqp_id]
  - OpenSearch table providing recipe_version per (eqp_id, recipe_name)

Phase 1 mock derives both from `sem_list` so the table is always self-consistent
with the rest of the app (장비 리스트 shows the same eqp_ids).
"""

import hashlib
import random
from functools import lru_cache
from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi._tool_specs import ToolType, model_to_tool_type
from back_dev_home.sem_list.data import SemListRow, get_sem_list


__all__ = ["LateralRecipeRow", "LateralRecipeResponse", "ToolType", "get_lateral_recipe"]


class LateralRecipeRow(TypedDict):
    eqp_id: str
    eqp_model_cd: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    available: Literal["On", "Off"]
    recipe_ready: bool
    recipe_version: int | None


class LateralRecipeResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    recipe_name: str
    total_tools_in_fab: int
    ready_count: int
    not_ready_count: int
    rows: list[LateralRecipeRow]


READY_RATIO = 0.65
RECIPE_VERSION_RANGE = (1, 7)


def _seed(*values: str | None) -> int:
    digest = hashlib.sha256(":".join(value or "" for value in values).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


@lru_cache(maxsize=1)
def _all_rows() -> tuple[SemListRow, ...]:
    return tuple(get_sem_list())


def _filter_rows(tool_type: ToolType, fab_name: str | None) -> list[SemListRow]:
    rows: list[SemListRow] = []
    fab_normalized = (fab_name or "").upper() or None

    for row in _all_rows():
        if model_to_tool_type(row["eqp_model_cd"]) != tool_type:
            continue
        if fab_normalized and row["fab_name"].upper() != fab_normalized:
            continue
        rows.append(row)

    rows.sort(key=lambda r: r["eqp_id"])
    return rows


def get_lateral_recipe(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_name: str
) -> LateralRecipeResponse:
    fab_rows = _filter_rows(tool_type, fab_name)
    rng = random.Random(_seed(tool_type, fab_name, recipe_name))

    rows: list[LateralRecipeRow] = []
    ready_count = 0

    for sem in fab_rows:
        is_ready = rng.random() < READY_RATIO
        version = rng.randint(*RECIPE_VERSION_RANGE) if is_ready else None
        if is_ready:
            ready_count += 1

        rows.append(LateralRecipeRow(
            eqp_id=sem["eqp_id"],
            eqp_model_cd=sem["eqp_model_cd"],
            vendor_nm=sem["vendor_nm"],
            available=sem["available"],
            recipe_ready=is_ready,
            recipe_version=version
        ))

    total = len(rows)

    return LateralRecipeResponse(
        tool_type=tool_type,
        fab_name=fab_name,
        recipe_name=recipe_name,
        total_tools_in_fab=total,
        ready_count=ready_count,
        not_ready_count=total - ready_count,
        rows=rows
    )
