"""Stable response contracts for lateral_recipe endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict

from backend.ebeam._tool_specs import ToolType


__all__ = [
    "LateralRecipeResponse",
    "LateralRecipeRow",
    "LateralRecipeVersion",
]


class LateralRecipeRow(TypedDict):
    eqp_id: str
    eqp_model_cd: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    available: Literal["On", "Off"]
    recipe_ready: bool
    recipe_version: int | None
    recipe_generated_at: str | None
    # The last IDP check could not reach this tool (FTP / parse failure), so
    # "not ready" here means "not verified", not "verified absent". Only ever
    # True on a row with recipe_ready False — evidence that a tool holds the
    # recipe outranks a failed check.
    recipe_unverified: bool


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
