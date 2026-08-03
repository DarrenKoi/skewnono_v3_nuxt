"""Stable response contracts for recipe_search endpoints."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


__all__ = [
    "AlignDetailResponse",
    "AlignPoint",
    "CompareParameter",
    "CompareRecipe",
    "IdpImageInfoRow",
    "IdpLocator",
    "MeasurementPointsResponse",
    "ParamDetailRequestItem",
    "ParamDetailResponse",
    "ParamImage",
    "ParamInfoImage",
    "ParamInfoResponse",
    "ParamOccurrence",
    "ParameterListResponse",
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
    "value": str,
    # Which nested group this row came from, for readers that return a dict OF
    # dicts rather than a flat one. ENMP (read_af_pr_condition) is the only such
    # reader today: it returns eight groups — the addressing and measurement
    # sequences, their pattern-recognition settings and their auto-focus
    # settings (office 확인 2026-07-30).
    #
    # NotRequired, so the four FLAT readers construct their rows exactly as
    # before and render byte-identically. Absent and None mean the same thing:
    # this row belongs to no group.
    #
    # ★ The row's identity is (section, key), NOT key. Two groups routinely
    #   carry the SAME inner key — addressing pass 1 and pass 2 are the same
    #   kind of settings twice — so anything that dedupes or joins on key alone
    #   silently collapses pass 2 into pass 1 and shows one pass's value under
    #   both. recipeCompare.ts's buildSettingRows is where that matters.
    "section": NotRequired[str | None]
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

# One element of the param-detail POST body. ``slots`` is normally the row's
# five img_* values verbatim from idp_image_info — the client already holds
# them, so the server never re-parses the .idp to recover them.
#
# ★ A PARTIAL dict is legal and means "do not read the omitted slots". Both
#   adapters plan their reads through ``rawfiles.slot_sources``, which reads
#   every slot with ``slots.get(...)``, so an absent key takes the same branch
#   as an empty one and that file is never fetched. ``param-info``'s
#   ``include=`` is built on this, and it is the difference between narrowing
#   the READ and merely filtering the response — so an adapter must keep
#   planning through ``slot_sources`` rather than indexing ``slots`` directly.
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
    fab_name: str
    tool_category: str
    timestamp: str


class CompareParameter(TypedDict):
    Parameter: str
    idp: dict[str, object]
    images: dict[str, str]


class CompareRecipe(TypedDict):
    recipe_id: str
    fab_name: str
    # Per-recipe, because compare fetches AMP for the visible cell across every
    # selected recipe and each one lives on its own tool.
    locator: IdpLocator
    parameters: list[CompareParameter]


class RecipeCompareResponse(TypedDict):
    tool_type: ToolType
    fab_name: str | None
    recipes: list[CompareRecipe]


# ── tiered read endpoints (spec 2026-08-02) ───────────────────────────────
#
# Three responses split on READ COST, not on subject matter. idp_image_info and
# wafer_mp_info come from the .idp parse already in hand; amp, af_pr and each
# image's cond cost up to five FTP reads per occurrence off the measuring tool
# itself. Serving both from one endpoint would make every list-browsing script
# pay the deep tier's price against a production tool.


class ParameterListResponse(TypedDict):
    """Tier 0 — every idp_image_info row, no tool I/O.

    ``total_rows`` rather than ``total``: the grain is the ROW, and a bare
    ``total`` is the field a caller misreads as a parameter count. A row of
    idp_image_info is one image DEFINITION, so one parameter can occupy several
    rows — ``distinct_parameters`` is carried so the number a user actually
    wants needs no client-side dedup. ``mother_rows`` and ``addressing_rows``
    are row counts too, and are named to say so.

    The locator is returned so a caller can drop straight into POST
    param-detail for bulk work without a second recipe-detail call.
    """
    recipe_id: str
    fab_name: str | None
    tool_type: ToolType
    locator: IdpLocator
    total_rows: int
    distinct_parameters: int
    mother_rows: int
    addressing_rows: int
    rows: list[IdpImageInfoRow]


class MeasurementPointsResponse(TypedDict):
    """Tier 1 — wafer_mp_info filtered to one parameter. No tool I/O."""
    recipe_id: str
    parameter: str
    total: int
    points: list[WaferMpInfoRow]


# One image slot, flattened. The SettingBlock's file name moves to
# ``cond_source`` so the rows are a plain list; a caller wanting the block shape
# verbatim uses param-detail.
ParamInfoImage = TypedDict("ParamInfoImage", {
    "slot": str,
    "stage": str,
    "name": str,
    "cond": list[SettingRow],
    "cond_source": str | None
})

# One idp_image_info row's worth of raw-folder settings. Every settings key is
# NotRequired because ``include=`` omits the parts it was not asked for — and
# omits them by never READING their files, not by deleting them afterwards.
ParamOccurrence = TypedDict("ParamOccurrence", {
    "idp": IdpImageInfoRow,
    "amp": NotRequired[list[SettingRow]],
    "amp_source": NotRequired[str | None],
    "af_pr": NotRequired[list[SettingRow]],
    "af_pr_source": NotRequired[str | None],
    "images": NotRequired[list[ParamInfoImage]]
})


class ParamInfoResponse(TypedDict):
    """Tier 2 — the raw-recipe-folder settings for one parameter.

    ★ ``occurrences`` is a LIST because a parameter is not a row: Para_13 at
      SEQ 4/6 and at SEQ 11/15 name different files. A single-object response
      would have to pick one silently — the bug a param-keyed cache already
      caused once (``useRecipeParamDetail.ts:83``), reproduced for every
      caller instead of just the browser.
    """
    recipe_id: str
    fab_name: str | None
    tool_type: ToolType
    parameter: str
    locator: IdpLocator
    include: list[str]
    # How many rows name this parameter, before the cap. ``truncated`` says
    # whether ``occurrences`` is the whole story: a cap that quietly shortened
    # the list would be the very defect ``occurrences`` exists to prevent,
    # committed by the code meant to prevent it.
    total_occurrences: int
    truncated: bool
    occurrences: list[ParamOccurrence]
