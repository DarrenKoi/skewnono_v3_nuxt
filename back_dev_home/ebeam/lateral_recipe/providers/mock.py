"""횡전개(lateral) — recipe ↔ tools mapping mock.

Production sources (deferred):
  - Redis hash `v3_tools_in_recipe_<fab>` keyed by recipe_name → list[eqp_id]
  - OpenSearch table providing recipe_version per (eqp_id, recipe_name)

Phase 1 mock derives both from `sem_list` so the table is always self-consistent
with the rest of the app (장비 리스트 shows the same eqp_ids).
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi._tool_specs import ToolType, model_to_tool_type
from back_dev_home.sem_list.data import SemListRow, get_sem_list


__all__ = [
    "LateralRecipeRow",
    "LateralRecipeResponse",
    "LateralRecipeVersion",
    "ToolType",
    "get_lateral_recipe",
]


class LateralRecipeRow(TypedDict):
    eqp_id: str
    eqp_model_cd: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    available: Literal["On", "Off"]
    recipe_ready: bool
    recipe_version: int | None
    recipe_generated_at: str | None


class LateralRecipeVersion(TypedDict):
    recipe_version: int
    generated_at: str
    ready_count: int


class LateralRecipeResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    recipe_name: str
    total_tools_in_fab: int
    ready_count: int
    not_ready_count: int
    latest_recipe_version: int | None
    latest_generated_at: str | None
    versions: list[LateralRecipeVersion]
    rows: list[LateralRecipeRow]


READY_RATIO = 0.65
RECIPE_VERSION_RANGE = (1, 7)
RECIPE_GENERATED_AT_BASE = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)


def _seed(*values: str | None) -> int:
    digest = hashlib.sha256(":".join(value or "" for value in values).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _version_generated_at(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_name: str,
    version: int
) -> str:
    version_age_days = RECIPE_VERSION_RANGE[1] - version
    jitter_minutes = _seed(tool_type, fab_name, recipe_name, str(version)) % (12 * 60)
    generated_at = RECIPE_GENERATED_AT_BASE - timedelta(days=version_age_days * 5, minutes=jitter_minutes)
    return _iso_z(generated_at)


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
    version_counts: dict[int, int] = {}
    version_generated_at: dict[int, str] = {}

    for sem in fab_rows:
        is_ready = rng.random() < READY_RATIO
        version = rng.randint(*RECIPE_VERSION_RANGE) if is_ready else None
        generated_at = (
            _version_generated_at(tool_type, fab_name, recipe_name, version)
            if version is not None
            else None
        )
        if is_ready:
            ready_count += 1
        if version is not None:
            version_counts[version] = version_counts.get(version, 0) + 1
            version_generated_at[version] = generated_at or ""

        rows.append(LateralRecipeRow(
            eqp_id=sem["eqp_id"],
            eqp_model_cd=sem["eqp_model_cd"],
            vendor_nm=sem["vendor_nm"],
            available=sem["available"],
            recipe_ready=is_ready,
            recipe_version=version,
            recipe_generated_at=generated_at
        ))

    total = len(rows)
    versions = [
        LateralRecipeVersion(
            recipe_version=version,
            generated_at=version_generated_at[version],
            ready_count=count
        )
        for version, count in sorted(version_counts.items(), reverse=True)
    ]
    latest = versions[0] if versions else None

    return LateralRecipeResponse(
        tool_type=tool_type,
        fab_name=fab_name,
        recipe_name=recipe_name,
        total_tools_in_fab=total,
        ready_count=ready_count,
        not_ready_count=total - ready_count,
        latest_recipe_version=latest["recipe_version"] if latest else None,
        latest_generated_at=latest["generated_at"] if latest else None,
        versions=versions,
        rows=rows
    )
