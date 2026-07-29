"""Stable response contracts for recipe_search endpoints."""

from __future__ import annotations

from typing import Literal, TypedDict


__all__ = [
    "AlignDetailResponse",
    "AlignPoint",
    "CompareParameter",
    "CompareRecipe",
    "IdpImageInfoRow",
    "IdpLocator",
    "ParamDetailRequestItem",
    "ParamDetailResponse",
    "ParamImage",
    "RecipeCompareResponse",
    "RecipeDetailResponse",
    "RecipeSearchResponse",
    "RecipeSearchRow",
    "SettingBlock",
    "SettingRow",
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


# ── raw-recipe folder (spec 2026-07-29) ───────────────────────────────────


# The resolved FTP location of a recipe's .idp. recipe-detail hands this to the
# client so follow-up calls reach the raw folder without re-downloading or
# re-parsing the .idp. Mirrors msr_image, where the client holds
# eqp_ip/class_name/msr and sends them back on each image GET.
IdpLocator = TypedDict("IdpLocator", {
    "eqp_ip": str,
    "class_name": str,
    "idw": str,
    "idp": str
})

# One parsed setting. Open key/value rather than fixed columns: the field names
# office_utils.idp_amp_reader returns are still OFFICE-VERIFY, and an open shape
# renders an unexpected key instead of dropping it. This replaces AmpRow, whose
# sixteen optical fields were named at home and never seen in a real file.
SettingRow = TypedDict("SettingRow", {
    "key": str,
    "value": str
})

SettingBlock = TypedDict("SettingBlock", {
    # The file these rows came from, e.g. "PRMS0000". Shown on screen so a
    # surprising value can be traced to a file without reading a server log.
    "source": str,
    # The reader's own key order, preserved. Nothing sorts or renames, so a
    # field the office adds appears without a code change here.
    "rows": list[SettingRow]
})

# One image slot of one parameter. ``name`` is the full filename, ready to hand
# straight to the recipe-image endpoint.
ParamImage = TypedDict("ParamImage", {
    "slot": str,
    "stage": str,
    "name": str,
    "cond": SettingBlock | None
})

# One element of the param-detail POST body. ``slots`` is the row's five img_*
# values verbatim from idp_image_info — the client already holds them, so the
# server never re-parses the .idp to recover them.
ParamDetailRequestItem = TypedDict("ParamDetailRequestItem", {
    "locator": IdpLocator,
    "parameter": str,
    "slots": dict[str, str]
})


class ParamDetailResponse(TypedDict):
    parameter: str
    # img_meas2 -> read_amp_info. None when the slot holds "non", the file is
    # absent, or the reader could not parse it — all three render 파일 없음.
    amp: SettingBlock | None
    # img_add2 -> PR->EN -> read_af_pr_condition.
    af_pr: SettingBlock | None
    images: list[ParamImage]


AlignPoint = TypedDict("AlignPoint", {
    "P_No": int,
    "image": str | None,
    "cond": SettingBlock | None,
    "setting": SettingBlock | None
})


class AlignDetailResponse(TypedDict):
    points: list[AlignPoint]


class RecipeSearchResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    total: int
    rows: list[RecipeSearchRow]


class RecipeDetailResponse(TypedDict):
    wafer_mp_info: list[WaferMpInfoRow]
    wafer_align_info: list[WaferAlignInfoRow]
    idp_image_info: list[IdpImageInfoRow]
    # Where this recipe's raw folder is. Carried so param-detail, align-detail
    # and recipe-image reach it without re-downloading or re-parsing the .idp.
    # ``amp_info`` and ``align_images`` USED to sit here and were fabricated at
    # the office as well as at home; they are now fetched per click through
    # those three endpoints (spec 2026-07-29).
    locator: IdpLocator
    recipe_id: str
    fac_id: str
    tool_category: str
    timestamp: str


class CompareParameter(TypedDict):
    Parameter: str
    idp: dict[str, object]
    images: dict[str, str]


class CompareRecipe(TypedDict):
    recipe_id: str
    fac_id: str
    # Per-recipe, because compare fetches AMP for the visible cell across every
    # selected recipe and each one lives on its own tool.
    locator: IdpLocator
    parameters: list[CompareParameter]


class RecipeCompareResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    recipes: list[CompareRecipe]
