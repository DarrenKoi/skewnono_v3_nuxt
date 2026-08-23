"""횡전개(lateral) — recipe ↔ tools mapping mock.

Office counterpart — schema of record: `docs/datatables/hitachi/idp_ver.txt`. CONNECTED
(2026-07-27); the Redis `v3_tools_in_recipe_<fab>` hash this docstring used to
name as the deferred production source was never the source and is not used.
What the office adapter actually reads:

    cdsem_idp_ver / hvsem_idp_ver   OpenSearch, ONE DOC PER (recipe, version)

so searching a `full_name` returns that recipe's whole version history and the
highest `version` (a long) is current. Fields used: full_name, fab_name (stored
uppercase), version, modified (date), eqp_id (multi-valued — the tools that
explicitly hold that version).

Two office rules this mock already mirrors structurally, which is why it is
built the way it is:

* the equipment roster does NOT come from the version index. It comes from
  `sem_list`, the same source behind 장비 리스트 — so this page can never show a
  different tool count for a fab than the inventory view does.
* recent measurement history is a HARD FLOOR on readiness: a tool that executed
  the recipe in the last 30 days cannot be displayed as 미보유, even when the
  IDP index omits it (such a tool is assigned the newest discovered version).
  Explicit IDP assignments always win. `_measured_eqp_ids` is the home stand-in
  for that 30-day `meas_hist_*` window.

The office adapter deliberately does NOT read the index's `not_found_eqp_id`
(미보유) list: readiness is the union of explicit membership and execution
evidence, and a negative list must not override proof that a tool ran the
recipe.

Timestamps: the office index stores KST wall clock with no offset, so
`recipe_generated_at` is emitted with an explicit +09:00. Tagging it `Z` would
render 12:00 KST as 21:00 in a KST browser.
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from back_dev_home.ebeam._tool_specs import ToolType, model_to_tool_type
from back_dev_home.ebeam.lateral_recipe.contracts import (
    LateralRecipeResponse,
    LateralRecipeRow,
    LateralRecipeVersion,
)
from back_dev_home.meas_hist.providers.mock import get_meas_hist
from back_dev_home.sem_list.contracts import SemListRow
from back_dev_home.sem_list.providers.mock import get_sem_list


__all__ = [
    "LateralRecipeRow",
    "LateralRecipeResponse",
    "LateralRecipeVersion",
    "ToolType",
    "get_lateral_recipe",
]


# Applies ONLY to tools with no 측정 이력 for the recipe — a tool that measured
# it is ready unconditionally (see `_measured_eqp_ids`). Lower than the flat 0.65
# this used to be because that floor now carries most of the readiness on its own:
# at 0.65 nearly half the fab/recipe pairs came out 100% 보유 and left the 미보유
# tab empty, which is a view worth keeping populated in the Phase 1 fixture.
UNMEASURED_READY_RATIO = 0.35
RECIPE_VERSION_RANGE = (1, 7)

# The office index stores KST wall clock with no offset, so the office adapter
# emits an explicit +09:00 — see this module's header, which warns that tagging
# the same instant `Z` renders 12:00 KST as 21:00 in a KST browser. The helper
# below used to do exactly that, contradicting the header a few lines above it.
KST = timezone(timedelta(hours=9))
RECIPE_GENERATED_AT_BASE = datetime(2026, 5, 20, 9, 0, tzinfo=KST)


def _seed(*values: str | None) -> int:
    digest = hashlib.sha256(":".join(value or "" for value in values).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _iso_kst(dt: datetime) -> str:
    return dt.astimezone(KST).isoformat()


def _version_generated_at(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_name: str,
    version: int
) -> str:
    version_age_days = RECIPE_VERSION_RANGE[1] - version
    jitter_minutes = _seed(tool_type, fab_name, recipe_name, str(version)) % (12 * 60)
    generated_at = RECIPE_GENERATED_AT_BASE - timedelta(days=version_age_days * 5, minutes=jitter_minutes)
    return _iso_kst(generated_at)


@lru_cache(maxsize=1)
def _all_rows() -> tuple[SemListRow, ...]:
    return tuple(get_sem_list())


def _measured_eqp_ids(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_name: str
) -> frozenset[str]:
    """Tools that actually ran this recipe inside the 측정 이력 window.

    측정했으면 보유 — a tool cannot have measurement history for a recipe it
    does not hold. Without this, readiness was an independent coin flip over
    the same fleet and 횡전개 happily listed a tool as 미보유 while 측정 이력
    showed its runs; the two views disagreed on half of all recipe/fab pairs.

    Same arguments the 측정 이력 view passes, so the two screens read the same
    rows (including the synthesized ones an unknown recipe gets).
    """
    return frozenset(row["eqp_id"] for row in get_meas_hist(tool_type, fab_name, recipe_name)["rows"])


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
    measured = _measured_eqp_ids(tool_type, fab_name, recipe_name)
    rng = random.Random(_seed(tool_type, fab_name, recipe_name))

    rows: list[LateralRecipeRow] = []
    ready_count = 0
    version_counts: dict[int, int] = {}
    version_generated_at: dict[int, str] = {}

    for sem in fab_rows:
        # Both draws happen for every tool, measured or not, so the measurement
        # set decides only WHO is ready — it never shifts the rng stream and
        # reshuffles the versions of the tools around it.
        ready_draw = rng.random()
        version_draw = rng.randint(*RECIPE_VERSION_RANGE)

        is_ready = sem["eqp_id"] in measured or ready_draw < UNMEASURED_READY_RATIO
        version = version_draw if is_ready else None
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
