"""Stable response contracts for recipe_usage endpoints (VeritySEM / Provision).

Source of record: docs/datatables/veritysem/recipe_usage.txt. Two kinds of
Redis key feed this feature, and their grains differ:

* list keys   -- one row per (eqp_id, recipe_id, fab_id): every recipe a tool
  has ever started a job for, all-time.
* usage keys  -- one row per (dt, eqp_id, recipe_id): daily runs for the loaded
  partitions (about 90 days, never assumed -- count dt).

`recipe_id` is the family's own full name and is NEVER split here:
Provision `<Product>/<Layer>/<RecipeName>`, VeritySEM `<TYPE>/<DEVICE>/<LAYER>/<JOB>`.
Only Provision ships pre-split columns; VeritySEM answers "" for them.

Times are KST strings exactly as stored (no offset). Dates are KST `YYYY-MM-DD`.
`fab_name` is the roster's (sem_list) current fab; `fab_id` (MES history, with
values such as C2 / X1 that are no fab_name) never appears in a response.
"""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = [
    "AmatToolType",
    "RecipeSource",
    "CatalogRow",
    "CatalogResponse",
    "RecipeToolRow",
    "DailyPoint",
    "RecipeDetailResponse",
    "StatusSummary",
    "RecipeRankingRow",
    "EquipmentRow",
    "StatusResponse",
]


AmatToolType = Literal["veritysem", "provision"]

# "mes"  = seen in the MES list key only (a job started, file not on the tool now)
# "tool" = resident on a tool (unique_rcp_list hash) but never started via MES
# "both" = in both
RecipeSource = Literal["mes", "tool", "both"]


class CatalogRow(TypedDict):
    recipe_id: str
    fab_name: str
    # Provision only; "" for VeritySEM.
    product_id: str
    layer_id: str
    recipe_name: str
    eqp_ids: list[str]          # sorted asc, roster tools of this fab only
    n_uses: int                 # all-time JobStart count, summed over tools and fab_id
    first_used: str | None      # None when source == "tool"
    last_used: str | None
    source: RecipeSource


class CatalogResponse(TypedDict):
    tool_type: AmatToolType
    fab_names: list[str]        # echo of the request; [] = all fabs
    total: int
    rows: list[CatalogRow]


class RecipeToolRow(TypedDict):
    eqp_id: str
    fab_name: str
    n_uses: int
    first_used: str | None
    last_used: str | None
    on_tool: bool               # resident per the unique_rcp_list hash


class DailyPoint(TypedDict):
    date: str
    runs: int
    wafers: int
    meas_min: float
    fail_runs: int


class RecipeDetailResponse(TypedDict):
    tool_type: AmatToolType
    recipe_id: str
    fab_names: list[str]
    tools: list[RecipeToolRow]  # [] when the recipe is unknown -- not a 404
    daily: list[DailyPoint]     # every loaded dt for this recipe, asc; days with no run omitted


class StatusSummary(TypedDict):
    runs: int
    wafers: int
    meas_min: float
    fail_runs: int
    fail_rate: float            # fail_runs / runs, 0..1; 0.0 when runs == 0
    avg_meas_min: float         # meas_min / runs; reads LOW when fail_runs is high (no_jobend => 0 min)
    recipe_count: int
    active_tool_count: int      # tools with runs > 0 in the window
    tool_count: int             # roster tools in scope, including those with no run


class RecipeRankingRow(TypedDict):
    recipe_id: str
    runs: int
    wafers: int
    meas_min: float
    avg_meas_min: float
    fail_runs: int
    fail_rate: float
    eqp_ids: list[str]
    fab_names: list[str]
    last_start: str


class EquipmentRow(TypedDict):
    """One per ROSTER tool. A tool with no run in the window is present with zeros."""

    eqp_id: str
    fab_name: str
    eqp_model_cd: str
    runs: int
    wafers: int
    meas_min: float
    avg_meas_min: float
    fail_runs: int
    fail_rate: float
    recipe_count: int
    top_recipe: str | None      # by runs
    last_start: str | None


class StatusResponse(TypedDict):
    tool_type: AmatToolType
    fab_names: list[str]
    start_date: str
    end_date: str
    # Latest dt that has rows. It is YESTERDAY at best -- today's dt never exists.
    anchor_date: str | None
    # Earliest dt that has rows; the date picker's floor.
    data_start: str | None
    summary: StatusSummary
    daily: list[DailyPoint]     # every calendar day in [start_date, end_date], zero-filled
    recipes: list[RecipeRankingRow]   # sorted by meas_min desc; the client re-sorts per tab
    equipments: list[EquipmentRow]    # sorted by meas_min desc, then eqp_id
