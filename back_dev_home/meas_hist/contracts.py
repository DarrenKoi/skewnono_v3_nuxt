"""Stable response contracts for meas_hist endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict

from back_dev_home.ebeam.hitachi._tool_specs import ToolType


__all__ = [
    "MeasHistRow",
    "MeasHistResponse",
    "MeasHistRecipeName",
    "MeasHistSearchResponse",
    "MeasHistFacetValue",
    "MeasHistFacetsResponse",
]


class MeasHistRow(TypedDict):
    id: str
    fac_id: str
    fab_name: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    eqp_id: str
    eqp_ip: str
    eqp_model_cd: str
    tool_type: ToolType
    lot_cd: str
    lot_id: str
    class_name: str
    recipe_name: str
    full_name: str
    timestamp: str
    start_time: str
    end_time: str
    meastime: int
    msr: str
    msr_check: Literal["Yes", "No"]
    align_fail: Literal["Pass", "Fail", "NA"]
    total_images: int
    fail_images: int
    fail_ratio: float  # PERCENT, 0..100 — 4.57 means 4.57%. Never a fraction.
    idp_name: str
    idw_name: str


class MeasHistResponse(TypedDict):
    tool_type: ToolType | None
    fab_name: str | None
    recipe_name: str | None
    total: int
    rows: list[MeasHistRow]


class MeasHistRecipeName(TypedDict):
    """One distinct (recipe, fab) the current recipe filter matched.

    The pair grain exists for multi-fab recipe-search: the fallback probe
    tags every discovered name with the fab it was measured in, so the UI
    can badge and owner-route it exactly like a catalog row. ``fab_name``
    may be ``""`` when the source documents carry no fab (dirty office
    data) — "name known, owner unknown", never a reason to hide the name.
    """

    full_name: str
    fab_name: str


class MeasHistSearchResponse(TypedDict):
    total: int
    capped: bool
    recipe_names: list[MeasHistRecipeName]
    recipe_names_complete: bool
    offset: int
    limit: int
    range: dict[str, str]
    out_of_retention: bool
    rows: list[MeasHistRow]


class MeasHistFacetValue(TypedDict):
    value: str
    count: int


class MeasHistFacetsResponse(TypedDict):
    tool_type: ToolType | None
    anchor: str
    retention_days: int
    fab: list[MeasHistFacetValue]
    model: list[MeasHistFacetValue]
    eq: list[MeasHistFacetValue]
