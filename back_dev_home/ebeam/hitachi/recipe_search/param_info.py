"""Composition for the three tiered recipe-search read endpoints.

Pure: takes an already-fetched ``RecipeDetailResponse`` and a fetcher, returns
the response body. No Flask and no I/O of its own, so the cost behaviour that
matters — which slots reach the provider — is unit-testable without a tool.

The tiers exist because two very different costs hide behind "parameter info":
``idp_image_info`` and ``wafer_mp_info`` come from the .idp parse already in
hand, while ``amp``/``af_pr``/``cond`` cost up to five FTP reads per occurrence
off the measuring tool itself. Serving both from one endpoint would make every
list-browsing script pay the deep tier's price against a production tool.

Spec: ``docs/superpowers/specs/2026-08-02-recipe-param-export-and-api-design.md``
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from back_dev_home.ebeam.hitachi.recipe_search import rawfiles
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    IdpImageInfoRow,
    MeasurementPointsResponse,
    ParamDetailRequestItem,
    ParamDetailResponse,
    ParameterListResponse,
    ParamInfoImage,
    ParamInfoResponse,
    ParamOccurrence,
    RecipeDetailResponse,
    SettingBlock,
    SettingRow,
    ToolType,
)


__all__ = [
    "INCLUDE_PARTS",
    "MAX_OCCURRENCES",
    "build_measurement_points",
    "build_param_info",
    "build_parameter_list",
    "parse_include",
    "rows_for_parameter",
]


# Which slot each part's files are named by, taken WHOLE from rawfiles rather
# than restated. Dropping a slot is what makes ``include=`` a real cost control:
# both adapters plan reads through ``rawfiles.slot_sources``, which reads every
# slot with ``slots.get(...)``, so an ABSENT key takes the same branch as an
# empty one and the read never happens. Filtering the RESPONSE instead would
# cost the same FTP session.
#
# That is exactly why the table cannot live here: a slot renamed in
# ``slot_sources`` but not here would make ``include=amp`` drop the slot the
# planner still reads from, so the endpoint would return nothing while paying
# for the file — and no test would fail.
_PART_SLOTS = rawfiles.PART_SLOTS

# The parts a caller may ask for, in response order. Derived so the two cannot
# disagree about what a legal part is.
INCLUDE_PARTS: tuple[str, ...] = ("amp", "af_pr", "images")
assert set(INCLUDE_PARTS) == set(_PART_SLOTS), (
    "every include= part must name the slots it reads"
)

# The ceiling routes.py applies to param-detail's item list, which is where
# these items end up. Defined here and imported there rather than written twice:
# lowering the POST cap while this one silently stayed at 200 would send a
# provider more items than the route layer considers legal.
MAX_OCCURRENCES = 200


def parse_include(raw: str | None) -> tuple[str, ...]:
    """``"amp, images"`` -> ``("amp", "images")``. Absent means every part.

    Raises:
        ValueError: a part that is not in INCLUDE_PARTS.
    """
    text = (raw or "").strip()
    if not text:
        return INCLUDE_PARTS
    parts = tuple(piece.strip() for piece in text.split(",") if piece.strip())
    unknown = [part for part in parts if part not in INCLUDE_PARTS]
    if unknown:
        raise ValueError(
            f"include must name only {', '.join(INCLUDE_PARTS)}; "
            f"got {', '.join(unknown)}"
        )
    return parts or INCLUDE_PARTS


def build_parameter_list(
    detail: RecipeDetailResponse,
    tool_type: ToolType,
    fab_name: str | None,
) -> ParameterListResponse:
    """Tier 0 — every idp_image_info row, plus roll-ups. No tool I/O."""
    rows = list(detail.get("idp_image_info") or [])
    return {
        "recipe_id": detail.get("recipe_id", ""),
        "fab_name": fab_name,
        "tool_type": tool_type,
        "locator": detail.get("locator", {}),
        "total_rows": len(rows),
        # Only rows that actually name a parameter. Counting `row.get(...)`
        # unguarded lets a sparse office row contribute `None` as if it were a
        # distinct parameter — invisible against the mock, which always fills
        # the column.
        "distinct_parameters": len({
            row.get("Parameter") for row in rows if row.get("Parameter")
        }),
        "mother_rows": sum(1 for row in rows if row.get("Mother_Para")),
        "addressing_rows": sum(1 for row in rows if row.get("Addressing")),
        "rows": rows,
    }


def build_measurement_points(
    detail: RecipeDetailResponse,
    parameter: str,
) -> MeasurementPointsResponse:
    """Tier 1 — wafer_mp_info for one parameter. No tool I/O."""
    points = [
        row for row in (detail.get("wafer_mp_info") or [])
        if row.get("Parameter") == parameter
    ]
    return {
        "recipe_id": detail.get("recipe_id", ""),
        "parameter": parameter,
        "total": len(points),
        "points": points,
    }


def rows_for_parameter(
    detail: RecipeDetailResponse,
    parameter: str,
) -> list[IdpImageInfoRow]:
    """Every idp_image_info row naming this parameter, in table order.

    A LIST, because a row is one image DEFINITION rather than one parameter:
    Para_13 at SEQ 4/6 and SEQ 11/15 resolve to different files.
    """
    return [
        row for row in (detail.get("idp_image_info") or [])
        if row.get("Parameter") == parameter
    ]


def _slots_to_keep(include: Iterable[str]) -> frozenset[str]:
    """The slots the requested parts are named by. Computed once per request,
    not once per occurrence — it depends only on ``include``."""
    return frozenset(slot for part in include for slot in _PART_SLOTS[part])


def _trimmed_slots(row: IdpImageInfoRow, keep: frozenset[str]) -> dict[str, str]:
    return {slot: str(row.get(slot) or "") for slot in keep}


def _flatten(block: SettingBlock | None) -> tuple[list[SettingRow], str | None]:
    if not block:
        return [], None
    return list(block.get("rows") or []), block.get("source")


def _occurrence(
    row: IdpImageInfoRow,
    detail: ParamDetailResponse,
    parts: frozenset[str],
) -> ParamOccurrence:
    occurrence: ParamOccurrence = {"idp": row}
    if "amp" in parts:
        occurrence["amp"], occurrence["amp_source"] = _flatten(detail.get("amp"))
    if "af_pr" in parts:
        occurrence["af_pr"], occurrence["af_pr_source"] = _flatten(detail.get("af_pr"))
    if "images" in parts:
        images: list[ParamInfoImage] = []
        for image in detail.get("images") or []:
            rows, source = _flatten(image.get("cond"))
            images.append({
                "slot": image.get("slot", ""),
                "stage": image.get("stage", ""),
                "name": image.get("name", ""),
                "cond": rows,
                "cond_source": source,
            })
        occurrence["images"] = images
    return occurrence


def build_param_info(
    detail: RecipeDetailResponse,
    parameter: str,
    tool_type: ToolType,
    fab_name: str | None,
    include: Iterable[str],
    fetch: Callable[[list[ParamDetailRequestItem]], list[ParamDetailResponse]],
    rows: list[IdpImageInfoRow] | None = None,
) -> ParamInfoResponse:
    """Tier 2 — one occurrence per idp_image_info row naming ``parameter``.

    ``fetch`` is injected rather than imported so the slot trimming — the part
    that decides how many files come off a production tool — can be asserted
    without one.

    ``rows`` lets a caller that has already filtered (the route does, to answer
    404 before spending a tool session) pass its result in rather than have the
    same scan run twice per request.
    """
    include = frozenset(include)
    locator = detail.get("locator", {})
    if rows is None:
        rows = rows_for_parameter(detail, parameter)
    # SAID, not silently done. This function argues a few lines below that
    # zipping loosely is unacceptable because it would drop occurrences without
    # a cue; a cap that truncated silently would be the same defect wearing a
    # constant's name — a caller would read N occurrences and have no way to
    # know the parameter had more.
    total_occurrences = len(rows)
    rows = rows[:MAX_OCCURRENCES]
    keep_slots = _slots_to_keep(include)
    items: list[ParamDetailRequestItem] = [
        {
            "locator": locator,
            "parameter": parameter,
            "slots": _trimmed_slots(row, keep_slots),
        }
        for row in rows
    ]
    details = fetch(items) if items else []
    return {
        "recipe_id": detail.get("recipe_id", ""),
        "fab_name": fab_name,
        "tool_type": tool_type,
        "parameter": parameter,
        "locator": locator,
        # Sorted so the echoed list is stable regardless of the frozenset's
        # iteration order — a response field a caller may assert on.
        "include": [part for part in INCLUDE_PARTS if part in include],
        "total_occurrences": total_occurrences,
        "truncated": total_occurrences > len(rows),
        # strict=True on purpose. Both adapters contract to return exactly one
        # entry per item; a mismatch means a provider bug, and zipping loosely
        # would silently DROP occurrences — the same class of quiet wrong answer
        # the occurrences list exists to prevent.
        "occurrences": [
            _occurrence(row, found, include)
            for row, found in zip(rows, details, strict=True)
        ],
    }
