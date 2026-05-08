"""Recipe Search mock catalog.

The real office source is expected to return a large recipe-name catalog for
the selected e-beam tool/fab. Keep this mock intentionally large so the
frontend exercises the same client-side search and rendering constraints.
"""

import hashlib
import random
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal, TypedDict


__all__ = ["RecipeSearchRow", "RecipeSearchResponse", "ToolType", "get_recipe_catalog"]


ToolType = Literal["cd-sem", "hv-sem"]


class RecipeSearchRow(TypedDict):
    recipe_id: str
    recipe_name: str
    class_name: str
    fac_id: str
    fab_name: str
    tool_type: ToolType
    eqp_model_cd: str
    updated_at: str


class RecipeSearchResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    total: int
    rows: list[RecipeSearchRow]


RECIPE_COUNT = 50_000
BASE_UPDATED_AT = datetime(2026, 5, 8, 9, 0, 0, tzinfo=timezone.utc)

TOOL_MODELS: dict[ToolType, tuple[str, ...]] = {
    "cd-sem": ("CG6300", "CG6320", "CG6380", "GT2000", "GT2000S"),
    "hv-sem": ("TP3000", "TP3500", "TP4000", "VERITYSEM_5", "PROVISION_3")
}

NAME_PATTERNS: tuple[tuple[str, str], ...] = (
    ("RACE", "DEAE"),
    ("EA", "ERJERI_TEA"),
    ("RA", "DFEF1_1AA"),
    ("ABC", "123_MAIN"),
    ("ADI", "CD_BIAS"),
    ("AEI", "OVERLAY"),
    ("QC", "DAILY_MATCH"),
    ("CNT", "CONTACT_CHECK"),
    ("GATE", "PITCH_MON"),
    ("EDGE", "PROFILE_SCAN")
)


def _seed_for(tool_type: ToolType, fab_name: str | None) -> int:
    digest = hashlib.sha256(f"{tool_type}:{fab_name or 'ALL'}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _fac_id_from_fab(fab_name: str | None) -> str:
    if not fab_name:
        return "R3"
    if fab_name.startswith("R"):
        return "R3"
    return fab_name[:3]


def _format_iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _build_recipe_name(index: int, rng: random.Random) -> tuple[str, str]:
    class_name, base_name = NAME_PATTERNS[index % len(NAME_PATTERNS)]
    variant = rng.choice(("STD", "MON", "ENG", "QUAL", "PROD"))
    suffix = f"{index + 1:05d}"

    # Every mock name includes ABC123 so "ABC" and "123" remain useful
    # smoke-searches while preserving the slash-heavy recipe-name shape.
    return class_name, f"{class_name}/{base_name}_ABC123_{variant}_{suffix}"


@lru_cache(maxsize=16)
def _generate_recipe_rows(tool_type: ToolType, fab_name: str | None) -> tuple[RecipeSearchRow, ...]:
    rng = random.Random(_seed_for(tool_type, fab_name))
    models = TOOL_MODELS[tool_type]
    tool_slug = tool_type.replace("-", "").upper()
    fab_label = fab_name or "ALL"
    fac_id = _fac_id_from_fab(fab_name)
    rows: list[RecipeSearchRow] = []

    for index in range(RECIPE_COUNT):
        class_name, recipe_name = _build_recipe_name(index, rng)
        updated_at = BASE_UPDATED_AT - timedelta(minutes=rng.randint(0, 60 * 24 * 90))

        rows.append({
            "recipe_id": f"{tool_slug}-{fab_label}-RCP-{index + 1:05d}",
            "recipe_name": recipe_name,
            "class_name": class_name,
            "fac_id": fac_id,
            "fab_name": fab_label,
            "tool_type": tool_type,
            "eqp_model_cd": rng.choice(models),
            "updated_at": _format_iso(updated_at)
        })

    return tuple(rows)


def get_recipe_catalog(tool_type: ToolType, fab_name: str | None = None) -> RecipeSearchResponse:
    rows = list(_generate_recipe_rows(tool_type, fab_name))
    return {
        "tool_type": tool_type,
        "fab_name": fab_name,
        "total": len(rows),
        "rows": rows
    }
