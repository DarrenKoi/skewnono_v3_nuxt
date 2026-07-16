"""Recipe Search mock catalog and recipe-open payloads.

The office source is expected to return only a large Redis-backed recipe-name
list. Recipe-open detail data is generated separately to mimic the IDP payload
the frontend will request after a user chooses one recipe.
"""

import hashlib
import random
from datetime import datetime
from functools import lru_cache

from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    AlignImageRow,
    AmpRow,
    CompareParameter,
    CompareRecipe,
    IdpImageInfoRow,
    RecipeCompareResponse,
    RecipeDetailResponse,
    RecipeSearchResponse,
    RecipeSearchRow,
    ToolType,
    WaferAlignInfoRow,
    WaferMpInfoRow,
)


__all__ = [
    "AmpRow",
    "CompareParameter",
    "CompareRecipe",
    "IMAGE_SLOTS",
    "IdpImageInfoRow",
    "RecipeCompareResponse",
    "RecipeDetailResponse",
    "RecipeSearchResponse",
    "RecipeSearchRow",
    "ToolType",
    "WaferAlignInfoRow",
    "WaferMpInfoRow",
    "get_recipe_catalog",
    "get_recipe_compare_data",
    "get_recipe_open_data"
]


IMAGE_SLOTS: tuple[dict[str, str], ...] = (
    {"key": "img_add1",   "label": "img_add1",   "role": "address", "stage": "Addressing 1"},
    {"key": "img_add2",   "label": "img_add2",   "role": "address", "stage": "Addressing 2"},
    {"key": "image_add3", "label": "image_add3", "role": "address", "stage": "Addressing 3"},
    {"key": "img_meas1",  "label": "img_meas1",  "role": "measure", "stage": "Measure 1"},
    {"key": "img_meas2",  "label": "img_meas2",  "role": "measure", "stage": "Measure 2"}
)


COMPARE_IDP_FIELDS: tuple[str, ...] = (
    "Addressing", "Double_Addressing", "Mother_Para",
    "Region", "Meas_Counting", "dnumber_removed"
)


RECIPE_COUNT = 50_000

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


def _seed_for_values(*values: str | None) -> int:
    digest = hashlib.sha256(":".join(value or "" for value in values).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _seed_for(tool_type: ToolType, fab_name: str | None) -> int:
    return _seed_for_values(tool_type, fab_name or "ALL")


def _build_recipe_name(index: int, rng: random.Random) -> str:
    class_name, base_name = NAME_PATTERNS[index % len(NAME_PATTERNS)]
    variant = rng.choice(("STD", "MON", "ENG", "QUAL", "PROD"))
    suffix = f"{index + 1:05d}"

    # Every mock name includes ABC123 so "ABC" and "123" remain useful
    # smoke-searches while preserving the slash-heavy recipe-name shape.
    return f"{class_name}/{base_name}_ABC123_{variant}_{suffix}"


@lru_cache(maxsize=16)
def _generate_recipe_rows(tool_type: ToolType, fab_name: str | None) -> tuple[RecipeSearchRow, ...]:
    rng = random.Random(_seed_for(tool_type, fab_name))
    return tuple(_build_recipe_name(index, rng) for index in range(RECIPE_COUNT))


def generate_wafer_mp_info(
    num_records: int = 50,
    rng: random.Random | None = None
) -> list[WaferMpInfoRow]:
    """Generate dummy wafer measurement point information."""
    active_rng = rng or random.Random()
    data: list[WaferMpInfoRow] = []

    for index in range(num_records):
        chip_x = active_rng.randint(1, 10)
        chip_y = active_rng.randint(1, 10)

        data.append({
            "ChipNo_X": chip_x,
            "ChipNo_Y": chip_y,
            "Coordinate_X": round(active_rng.uniform(-50.0, 50.0), 3),
            "Coordinate_Y": round(active_rng.uniform(-50.0, 50.0), 3),
            "P_No": active_rng.randint(1, 20),
            "D_No": active_rng.randint(1, 100),
            "Diff": active_rng.choice([True, False]),
            "Rel": active_rng.choice([True, False]),
            "Rel_MoveX": round(active_rng.uniform(-5.0, 5.0), 3),
            "RelMoveY": round(active_rng.uniform(-5.0, 5.0), 3),
            "Coordinate_X_r": round(active_rng.uniform(-50.0, 50.0), 3),
            "Coordinate_Y_r": round(active_rng.uniform(-50.0, 50.0), 3),
            "Parameter": f"Para_{active_rng.randint(1, 20)}",
            "img_meas2": f"IMG_MEAS_{index + 1:04d}.jpg"
        })

    return data


def generate_wafer_align_info(
    num_records: int = 10,
    rng: random.Random | None = None
) -> list[WaferAlignInfoRow]:
    """Generate dummy wafer alignment information."""
    active_rng = rng or random.Random()
    data: list[WaferAlignInfoRow] = []

    for index in range(num_records):
        data.append({
            "Align_No": index + 1,
            "Chip.X": active_rng.randint(1, 10),
            "Chip.Y": active_rng.randint(1, 10),
            "Coordinate.X": round(active_rng.uniform(-100.0, 100.0), 3),
            "Coordinate.Y": round(active_rng.uniform(-100.0, 100.0), 3),
            "P.No": active_rng.randint(1, 20)
        })

    return data


def generate_wafer_align_images(
    rng: random.Random | None = None
) -> list[AlignImageRow]:
    """Generate the pair of wafer-alignment reference images for a recipe."""
    active_rng = rng or random.Random()
    return [
        {"label": "Global Align", "filename": f"ALIGN_GLOBAL_{active_rng.randint(1, 9999):04d}.jpg"},
        {"label": "Fine Align", "filename": f"ALIGN_FINE_{active_rng.randint(1, 9999):04d}.jpg"}
    ]


def generate_idp_image_info(
    num_records: int = 20,
    rng: random.Random | None = None
) -> list[IdpImageInfoRow]:
    """Generate dummy IDP image information."""
    active_rng = rng or random.Random()
    data: list[IdpImageInfoRow] = []

    for index in range(num_records):
        p_no = active_rng.randint(1, 20)
        seq = index + 1

        data.append({
            "Parameter": f"Para_{p_no}",
            "img_add1": f"IMG_ADD1_{seq:04d}.jpg",
            "img_add2": f"IMG_ADD2_{seq:04d}.jpg",
            "img_meas1": f"IMG_MEAS1_{seq:04d}.jpg",
            "img_meas2": f"IMG_MEAS2_{seq:04d}.jpg",
            "SEQ": seq,
            "Last_SEQ": seq + active_rng.randint(0, 5),
            "Region": p_no,
            "image_add3": f"IMG_ADD3_{seq:04d}.jpg",
            "Addressing": active_rng.choice(["Yes", "No"]),
            "Mother_Para": f"Para_{active_rng.randint(1, 5)}",
            "Double_Addressing": active_rng.choice([True, False]),
            "Meas_Counting": active_rng.randint(1, 10),
            "dnumber_removed": active_rng.randint(0, 3)
        })

    return data


_ADDR_ONLY_NONE = {
    "Algo": None,
    "ROI": None,
    "EdgeThr": None,
    "EdgeDir": None,
    "Smooth": None
}

_MEAS_ONLY_NONE = {
    "Template": None,
    "MatchScore": None,
    "SearchArea": None,
    "Rotation": None
}


def generate_amp_info(idp_rows: list[IdpImageInfoRow]) -> list[AmpRow]:
    """Generate Auto Meas Parameter rows for every (parameter, image slot).

    Seeded deterministically off the parameter string so refreshes return the
    same values for the same recipe.
    """
    rows: list[AmpRow] = []

    for idp in idp_rows:
        parameter = idp["Parameter"]
        param_rng = random.Random(_seed_for_values("amp", parameter))

        for slot in IMAGE_SLOTS:
            common = {
                "parameter": parameter,
                "slot": slot["key"],
                "role": slot["role"],
                "stage": slot["stage"],
                "WD": f"{param_rng.uniform(4.5, 6.0):.1f}"
            }

            if slot["role"] == "address":
                rows.append({
                    **common,
                    "Mag": param_rng.choice(["1.0K", "3.0K", "5.0K", "10.0K"]),
                    "Vacc": param_rng.choice(["300", "500", "800"]),
                    "I_probe": param_rng.choice(["20", "40", "80"]),
                    "Frame": param_rng.choice(["2", "4", "8"]),
                    "Scan": param_rng.choice(["TV", "Fast"]),
                    "Det": "SE",
                    "Template": (
                        f"TPL_{param_rng.choice(['LINE', 'PAD', 'VIA', 'CRN'])}"
                        f"_{param_rng.randint(100, 999)}"
                    ),
                    "MatchScore": str(param_rng.randint(60, 95)),
                    "SearchArea": param_rng.choice(["128", "256", "384", "512"]),
                    "Rotation": f"{param_rng.uniform(-1.0, 1.0):.2f}",
                    **_ADDR_ONLY_NONE
                })
            else:
                rows.append({
                    **common,
                    "Mag": param_rng.choice(["30.0K", "50.0K", "80.0K", "100.0K"]),
                    "Vacc": param_rng.choice(["800", "1000", "1500"]),
                    "I_probe": param_rng.choice(["200", "400", "800"]),
                    "Frame": param_rng.choice(["8", "16", "32"]),
                    "Scan": param_rng.choice(["Slow1", "Slow2", "TV"]),
                    "Det": param_rng.choice(["SE", "BSE"]),
                    "Algo": param_rng.choice(["Linear", "Top-Bottom", "Threshold", "Box"]),
                    "ROI": param_rng.choice(["256", "384", "512", "640"]),
                    "EdgeThr": param_rng.choice(["40", "50", "60", "70"]),
                    "EdgeDir": param_rng.choice(["L->R", "R->L", "Both"]),
                    "Smooth": param_rng.choice(["Off", "3x3", "5x5", "Gauss"]),
                    **_MEAS_ONLY_NONE
                })

    return rows


def get_recipe_catalog(tool_type: ToolType, fab_name: str | None = None) -> RecipeSearchResponse:
    rows = list(_generate_recipe_rows(tool_type, fab_name))
    return {
        "tool_type": tool_type,
        "fab_name": fab_name,
        "total": len(rows),
        "rows": rows
    }


def get_recipe_open_data(
    recipe_id: str | None = None,
    fac_id: str | None = None,
    tool_category: str | None = None
) -> RecipeDetailResponse:
    """Generate all three recipe-open tables for one recipe."""
    resolved_recipe_id = recipe_id or "DUMMY_RECIPE_001"
    resolved_fac_id = fac_id or "R3"
    resolved_tool_category = tool_category or "cd-sem"
    rng = random.Random(_seed_for_values(resolved_recipe_id, resolved_fac_id, resolved_tool_category))

    idp_rows = generate_idp_image_info(rng=rng)

    return {
        "wafer_mp_info": generate_wafer_mp_info(rng=rng),
        "wafer_align_info": generate_wafer_align_info(rng=rng),
        "align_images": generate_wafer_align_images(rng=rng),
        "idp_image_info": idp_rows,
        "amp_info": generate_amp_info(idp_rows),
        "recipe_id": resolved_recipe_id,
        "fac_id": resolved_fac_id,
        "tool_category": resolved_tool_category,
        "timestamp": datetime.now().isoformat()
    }


def get_recipe_compare_data(
    tool_type: ToolType,
    fab_name: str | None,
    recipe_names: list[str]
) -> RecipeCompareResponse:
    """Compact per-recipe comparison payload: IDP fields + slot image filenames +
    AMP rows per parameter. Reuses get_recipe_open_data so compare matches open."""
    recipes: list[CompareRecipe] = []
    for name in recipe_names:
        clean = (name or "").strip()
        if not clean:
            continue
        detail = get_recipe_open_data(
            recipe_id=clean, fac_id=fab_name, tool_category=tool_type
        )
        amp_by_param: dict[str, list[AmpRow]] = {}
        for amp in detail["amp_info"]:
            amp_by_param.setdefault(amp["parameter"], []).append(amp)

        seen: set[str] = set()
        parameters: list[CompareParameter] = []
        for idp in detail["idp_image_info"]:
            param = idp["Parameter"]
            if param in seen:
                continue
            seen.add(param)
            parameters.append({
                "Parameter": param,
                "idp": {field: idp[field] for field in COMPARE_IDP_FIELDS},
                "images": {slot["key"]: idp[slot["key"]] for slot in IMAGE_SLOTS},
                "amp": amp_by_param.get(param, [])
            })
        recipes.append({
            "recipe_id": detail["recipe_id"],
            "fac_id": detail["fac_id"],
            "parameters": parameters
        })

    return {"tool_type": tool_type, "fab_name": fab_name, "recipes": recipes}
