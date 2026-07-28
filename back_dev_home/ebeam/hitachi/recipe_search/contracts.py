"""Stable response contracts for recipe_search endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = [
    "AlignImageRow",
    "AmpRow",
    "CompareParameter",
    "CompareRecipe",
    "IdpImageInfoRow",
    "RecipeCompareResponse",
    "RecipeDetailResponse",
    "RecipeSearchResponse",
    "RecipeSearchRow",
    "ToolType",
    "WaferAlignInfoRow",
    "WaferMpInfoRow",
]


ToolType = Literal["cd-sem", "hv-sem"]
RecipeSearchRow = str

WaferMpInfoRow = TypedDict("WaferMpInfoRow", {
    "ChipNo_X": int,
    "ChipNo_Y": int,
    "Coordinate_X": float,
    "Coordinate_Y": float,
    "P_No": int,
    "D_No": int,
    "Diff": bool,
    "Rel": bool,
    "Rel_MoveX": float,
    "Rel_MoveY": float,
    "Coordinate_X_r": float,
    "Coordinate_Y_r": float,
    "Parameter": str,
    # Named like an image but it is NOT a filename — it carries the same value
    # as P_No (user-confirmed 2026-07-27). The identically-named column on
    # IdpImageInfoRow *is* an image slot; the two are unrelated.
    "img_meas2": int
})

WaferAlignInfoRow = TypedDict("WaferAlignInfoRow", {
    "Align_No": int,
    "Chip.X": int,
    "Chip.Y": int,
    "Coordinate.X": float,
    "Coordinate.Y": float,
    "P.No": int
})

# Wafer-alignment reference images. Usually a pair (global + fine alignment).
AlignImageRow = TypedDict("AlignImageRow", {
    "label": str,
    "filename": str
})

IdpImageInfoRow = TypedDict("IdpImageInfoRow", {
    "Parameter": str,
    "img_add1": str,
    "img_add2": str,
    "img_meas1": str,
    "img_meas2": str,
    "SEQ": int,
    "Last_SEQ": int,
    "Region": int,
    "image_add3": str,
    # Three real ``bool`` columns in the parser output (office 확인
    # 2026-07-28). ``Mother_Para`` is NOT a parameter name: True means this
    # row's own parameter is a mother, whose image its sons measure from.
    # ``dnumber_removed`` True means the parameter's data is suppressed.
    "Addressing": bool,
    "Mother_Para": bool,
    "Double_Addressing": bool,
    "Meas_Counting": int,
    "dnumber_removed": bool
})


# Auto Meas Parameter (AMP) — one row per (parameter, image slot).
# Fields not applicable to a role come through as None.
AmpRow = TypedDict("AmpRow", {
    "parameter": str,
    "slot": str,
    "role": str,
    "stage": str,
    "Mag": str,
    "Vacc": str,
    "I_probe": str,
    "Frame": str,
    "Scan": str,
    "WD": str,
    "Det": str,
    "Template": str | None,
    "MatchScore": str | None,
    "SearchArea": str | None,
    "Rotation": str | None,
    "Algo": str | None,
    "ROI": str | None,
    "EdgeThr": str | None,
    "EdgeDir": str | None,
    "Smooth": str | None
})


class RecipeSearchResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    total: int
    rows: list[RecipeSearchRow]


class RecipeDetailResponse(TypedDict):
    wafer_mp_info: list[WaferMpInfoRow]
    wafer_align_info: list[WaferAlignInfoRow]
    align_images: list[AlignImageRow]
    idp_image_info: list[IdpImageInfoRow]
    amp_info: list[AmpRow]
    recipe_id: str
    fac_id: str
    tool_category: str
    timestamp: str


class CompareParameter(TypedDict):
    Parameter: str
    idp: dict[str, object]
    images: dict[str, str]
    amp: list[AmpRow]


class CompareRecipe(TypedDict):
    recipe_id: str
    fac_id: str
    parameters: list[CompareParameter]


class RecipeCompareResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    recipes: list[CompareRecipe]
