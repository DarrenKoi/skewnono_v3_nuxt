"""Stable response contracts for lateral_recipe endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict

from back_dev_home.ebeam._tool_specs import ToolType


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
