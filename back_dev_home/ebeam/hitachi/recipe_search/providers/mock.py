"""Recipe Search mock catalog and recipe-open payloads.

Office counterpart — schema of record: `docs/datatables/recipe_name_list.txt`.
Only the recipe NAME LIST is wired office-side, as one Redis hash per family:

    v3_cdsem_unique_rcp_list / v3_hvsem_unique_rcp_list

field = the fab name in LOWERCASE ("m14a", "r3"), value = that fab's list of
recipe names. Two office quirks the adapter absorbs so nothing above it has to:
routes uppercase `?fab_name=` and the lowercasing happens only at the Redis
boundary (the response echoes the caller's uppercase spelling), and the stored
list may be JSON (`["a","b"]`) or a Python repr (`['a','b']`) depending on the
writer, with a comma-split as a last resort (recipe names carry `/` and `_` but
never commas).

Searching the name list rather than 측정 이력 is deliberate: a recipe that has
never been measured still exists and must be findable.

★ COMPARE STILL RUNS OFF THIS MOCK AT THE OFFICE.
`recipe_search/providers/office*.py` RE-EXPORTS `get_recipe_compare_data` from
THIS module, so that generator runs in production and its output there is
fabricated, not 사내 data. It is re-exported rather than reimplemented so it
stays derived from open — the invariant this module guarantees. Recipe open
itself is wired (2026-07-27) and returns parsed IDP data, so open and compare
DISAGREE office-side until the batched fetch lands; see MIGRATION.md.

The SOURCE is no longer unknown, though: the IDP file lives on the measuring
tool's FTP server and a 사내 parser turns it into exactly the three tables
below (`docs/datatables/recipe_idp.txt`):

    v3_{cdsem,hvsem}_rcp_loc_{fab}       field full_name -> [idw_name, idp_name]
    v3_{cdsem,hvsem}_tools_in_rcp_{fab}  field full_name -> [eqp_id, ...]
                                           -> sem_list roster -> eqp_ip
      full_name's "/" prefix -> {class}   (neither hash carries class_name)
      (fallback: meas_hist_* -> eqp_ip + class_name + idw_name + idp_name)
        -> /HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}.idp
        -> office_utils.read_idp_info.combined_idp_info(path)
        -> {"wafer_mp_info": df, "wafer_align_info": df, "idp_image_info": df}

So the COLUMN NAMES here are a contract, not a convenience — `office_utils`
exists only at the office, and a name that drifts passes at home and fails
there. Two were wrong until 2026-07-27 and are now corrected: `Rel_MoveY`
(was RelMoveY), and `img_meas2`, which carries P_No's value rather than a
filename.

`align_images` and `amp_info` are NOT among the parser's keys. Their source is
the RAW-RECIPE FOLDER beside the .idp (`data/{idw}/{idp}/`), read by a second
사내 parser, `office_utils.idp_amp_reader` — see the 2026-07-29 spec and
`rawfiles.py`.

That makes the five `img_*` VALUES a contract too, not just their column names:
`rawfiles.py` derives every raw-folder path from them. They are generated here
in the office shape (user-confirmed 2026-07-29) — `IMMP0001`, `PRMP0000`,
`IMMS0000`, `PRMS0000`, `I2MP0000`, eight characters, no extension — with the
French `"non"` sentinel appearing on the optional slots so the no-file path is
exercised at home rather than first met at the office. The NUMBERING is still
fabricated; only the shape imitates.
"""

import hashlib
import random
from datetime import datetime
from functools import lru_cache

from back_dev_home.ebeam.hitachi.recipe_search import rawfiles
from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    AlignDetailResponse,
    AlignPoint,
    CompareParameter,
    CompareRecipe,
    IdpImageInfoRow,
    IdpLocator,
    ParamDetailRequestItem,
    ParamDetailResponse,
    ParamImage,
    RecipeCompareResponse,
    RecipeDetailResponse,
    RecipeSearchResponse,
    RecipeSearchRow,
    SettingBlock,
    ToolType,
    WaferAlignInfoRow,
    WaferMpInfoRow,
)


__all__ = [
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
    "fetch_recipe_image",
    "get_align_detail",
    "get_param_detail",
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

    for _ in range(num_records):
        chip_x = active_rng.randint(1, 10)
        chip_y = active_rng.randint(1, 10)
        p_no = active_rng.randint(1, 20)

        data.append({
            "ChipNo_X": chip_x,
            "ChipNo_Y": chip_y,
            "Coordinate_X": round(active_rng.uniform(-50.0, 50.0), 3),
            "Coordinate_Y": round(active_rng.uniform(-50.0, 50.0), 3),
            "P_No": p_no,
            "D_No": active_rng.randint(1, 100),
            "Diff": active_rng.choice([True, False]),
            "Rel": active_rng.choice([True, False]),
            "Rel_MoveX": round(active_rng.uniform(-5.0, 5.0), 3),
            "Rel_MoveY": round(active_rng.uniform(-5.0, 5.0), 3),
            "Coordinate_X_r": round(active_rng.uniform(-50.0, 50.0), 3),
            "Coordinate_Y_r": round(active_rng.uniform(-50.0, 50.0), 3),
            "Parameter": f"Para_{active_rng.randint(1, 20)}",
            # NOT a filename: the real parser emits P_No's value here
            # (user-confirmed 2026-07-27). This mock previously fabricated
            # "IMG_MEAS_0001.jpg", which taught the frontend to expect a
            # string that office data never produces.
            "img_meas2": p_no
        })

    return data


def generate_wafer_align_info(
    num_records: int = 10,
    rng: random.Random | None = None
) -> list[WaferAlignInfoRow]:
    """Generate dummy wafer alignment information.

    ``P.No`` is 1 or 2, never an arbitrary index (user-confirmed 2026-07-29):
    the align point identifies the optic that took the image — 1 = OM, 2 = SEM —
    and the table repeats those two across its rows. Roughly one recipe in four
    has only point 1.

    ``get_align_detail`` turns that number into ``read_align_image_condition``'s
    ``which`` argument, so a mock emitting P.No = 17 would make the unknown-optic
    path the common case at home and the OM/SEM path the rare one — exactly
    backwards from the office.
    """
    active_rng = rng or random.Random()
    data: list[WaferAlignInfoRow] = []

    p_numbers = [1] if active_rng.random() < 0.25 else [1, 2]
    for index in range(num_records):
        data.append({
            "Align_No": index + 1,
            "Chip.X": active_rng.randint(1, 10),
            "Chip.Y": active_rng.randint(1, 10),
            "Coordinate.X": round(active_rng.uniform(-100.0, 100.0), 3),
            "Coordinate.Y": round(active_rng.uniform(-100.0, 100.0), 3),
            "P.No": p_numbers[index % len(p_numbers)]
        })

    return data


# Slots that legitimately hold no file. Parameters routinely lack a third
# addressing image or an AF/PR setting, so the sentinel has to appear at home or
# the no-file path is never exercised until the office run — the same reason
# msr_image's mock emits .tif names it cannot preview.
_MAY_BE_EMPTY: tuple[str, ...] = ("img_add2", "image_add3")


def _slot(column: str, seq: int, rng: random.Random) -> str:
    if column in _MAY_BE_EMPTY and rng.random() < 0.25:
        return rawfiles.EMPTY_SLOT
    # Prefixes come from rawfiles, not a local table: this mock exists to
    # exercise rawfiles' own derivation, so a private copy could drift onto a
    # branch the office never takes.
    return f"{rawfiles.SLOT_PREFIX[column]}{seq:04d}"


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
            "img_add1": _slot("img_add1", seq, active_rng),
            "img_add2": _slot("img_add2", seq, active_rng),
            "img_meas1": _slot("img_meas1", seq, active_rng),
            "img_meas2": _slot("img_meas2", seq, active_rng),
            "SEQ": seq,
            "Last_SEQ": seq + active_rng.randint(0, 5),
            "Region": p_no,
            "image_add3": _slot("image_add3", seq, active_rng),
            "Addressing": active_rng.choice([True, False]),
            # A mother is the parameter whose image its sons measure from —
            # usually the SEQ 1 row (office 확인 2026-07-28), not a name.
            "Mother_Para": seq == 1,
            "Double_Addressing": active_rng.choice([True, False]),
            "Meas_Counting": active_rng.randint(1, 10),
            "dnumber_removed": active_rng.choice([True, False])
        })

    return data


def get_recipe_catalog(tool_type: ToolType, fab_name: str | None = None) -> RecipeSearchResponse:
    rows = list(_generate_recipe_rows(tool_type, fab_name))
    return {
        "tool_type": tool_type,
        "fab_name": fab_name,
        "total": len(rows),
        "rows": rows
    }


# ── raw-recipe folder (spec 2026-07-29) ───────────────────────────────────


# Field-name stems for the raw-file kinds whose reader output NOBODY HAS SEEN.
# Deliberately NOT plausible optical names (Mag, Vacc): those field names are
# still OFFICE-VERIFY, and a mock that invents credible ones teaches the
# frontend to expect columns the office may never send — exactly how AmpRow's
# sixteen invented fields went unquestioned for months.
#
# Three readers have LEFT this group, all confirmed by running
# scripts/probe_recipe_ftp.py at the office (2026-07-30): both cond.txt readers
# and read_amp_info. Their fields are named below rather than counted.
# read_af_pr_condition (ENMP…) and get_align_beam_pr_conditions (ENAP…) remain.
_AFPR_FIELDS = 6
# ENAP goes to get_align_beam_pr_conditions, a DIFFERENT function from the
# parameter-side readers, so its block keeps its own prefix. A block that says
# AFPR_ under an align point means somebody routed ENAP to read_af_pr_condition
# again — the mistake the adapter actually made until 2026-07-29.
_ALIGNPR_FIELDS = 4

# ── cond.txt (office 확인 2026-07-30) ──────────────────────────────────────
#
# The measurement/addressing cond.txt (.IMMP / .I2MP / .IMMS) and the wafer-align
# one (.IMAP{p:04d}) share ONE vocabulary; they are read by different functions
# and differ only in WHICH of these keys are present. Every value is a str.
#
# Four properties the screen depends on and a field COUNT could never have taught:
#
#   * the UNIT lives inside the value ("500 V", "0.0 deg"), so nothing
#     downstream may parse these as numbers;
#   * Magnification, Number_of_frames and Pixel carry no unit at all and are
#     still strings — "30000", not 30000;
#   * three keys pack an X,Y PAIR into one string, and the separators DIFFER:
#     Chip_coordinate / Wafer_coordinate / Field_Size use ", " while Pixel uses
#     a bare ",". Kept verbatim rather than normalised — a screen that tidies
#     this up hides what the tool actually wrote;
#   * the OM align file is a strict SUBSET, not a different vocabulary. It has
#     no beam settings at all, because an optical microscope has no beam.
_COND_KEYS_SEM: tuple[str, ...] = (
    "Accelerating_voltage",
    "Probe_current",
    "Magnification",
    "Number_of_frames",
    "Image_rotation",
    "Chip_coordinate",
    "Wafer_coordinate",
    "Field_Size",
    "Optics",
    "Scan",
    "Pixel",
    "Filter",
)

# P.No 1 — the optical microscope. Five keys, in the order the file lists them.
_COND_KEYS_OM: tuple[str, ...] = (
    "Magnification",
    "Chip_coordinate",
    "Wafer_coordinate",
    "Field_Size",
    "Pixel",
)

# Field size and magnification are ONE setting seen twice: the sample read at
# the office was 30000x -> "4.499 um", and 4.499 * 30000 = 134,970. Reproducing
# the product rather than drawing two independent numbers keeps the mock from
# teaching that a screen may show a field size contradicting its magnification.
#
# OFFICE-VERIFY: derived from ONE SEM sample. Whether a second recipe keeps the
# product, and whether the OM optic shares this constant at all, is unchecked —
# the OM sample came with a Field_Size key but no value.
_FOV_MAG_PRODUCT = 134_970.0

# The OM magnification seen at the office. Emitted verbatim rather than varied:
# it is one sample, and an optical scope's magnification is fixed by its lens,
# so a range here would be invention rather than imitation.
_OM_MAGNIFICATION = 104


def _um_pair(x: float, y: float) -> str:
    """'9737 um, 14710 um' — per-component unit, ', ' separator (office 확인)."""
    return f"{x:g} um, {y:g} um"


def _cond_values(rng: random.Random, optic: str) -> dict[str, str]:
    """Every cond.txt key this mock knows how to write, for one optic.

    Built as a whole rather than per-key so Magnification and Field_Size are
    drawn ONCE and stay consistent — see _FOV_MAG_PRODUCT. Keys the caller's
    optic does not use are still computed and then dropped, which costs nothing
    and keeps the two field lists a selection of one vocabulary instead of two
    definitions that can drift apart.

    Only the SHAPE imitates the office. Magnitudes are plausible-for-a-CD-SEM,
    not office distributions, and where exactly one real value is known
    (Optics / Scan / Filter, and OM's magnification and chip coordinate) that
    one value is emitted verbatim on every file — a single sample can teach a
    format, never a value domain.
    """
    om = optic == "OM"
    magnification = _OM_MAGNIFICATION if om else rng.choice((20_000, 30_000, 50_000, 100_000, 150_000))
    side = _FOV_MAG_PRODUCT / magnification
    return {
        "Accelerating_voltage": f"{rng.choice((300, 500, 800))} V",
        "Probe_current": f"{rng.choice((4.0, 8.0, 16.0)):.1f} pA",
        "Magnification": str(magnification),
        "Number_of_frames": str(rng.choice((8, 16, 32, 64))),
        "Image_rotation": f"{rng.choice((0.0, 90.0, 180.0, 270.0)):.1f} deg",
        # OM aligns in WAFER coordinates, so its chip coordinate is 0,0
        # (office 확인 2026-07-30). SEM images are addressed inside a die, so
        # theirs is die-relative. The wafer one is the larger of the two either
        # way: it spans a 300 mm wafer, i.e. 300,000 um.
        "Chip_coordinate": _um_pair(0, 0) if om
        else _um_pair(rng.randrange(0, 30_000), rng.randrange(0, 30_000)),
        "Wafer_coordinate": _um_pair(rng.randrange(0, 300_000), rng.randrange(0, 300_000)),
        "Field_Size": f"{side:.3f} um, {side:.3f} um",
        "Optics": "High Reso.",
        "Scan": "TV",
        "Pixel": rng.choice(("512,512", "1024,1024")),
        "Filter": "OFF",
    }


def _cond_block(source: str | None, optic: str, *scope: str) -> SettingBlock | None:
    """A cond.txt block with its REAL field names, for OM or SEM.

    Split from ``_block`` on purpose. The two answer different questions — this
    one reproduces field names we have seen, ``_block`` stands in for readers
    whose output is still unknown — and merging them would make placeholder keys
    and confirmed ones indistinguishable at the call site, which is the one
    thing a reader of this file most needs to tell apart.

    ``optic`` is "OM" or "SEM", the same argument the office passes to
    read_align_image_condition. Measurement and addressing images are always
    SEM; only wafer align has an OM file, at P.No 1.
    """
    if source is None:
        return None
    values = _cond_values(_seeded_rng(source, *scope), optic)
    keys = _COND_KEYS_OM if optic == "OM" else _COND_KEYS_SEM
    return {
        "source": source,
        "rows": [{"key": key, "value": values[key]} for key in keys]
    }


def _seeded_rng(source: str, *scope: str) -> random.Random:
    """Stable per (recipe, file) — see ``_block`` for why scope is not optional."""
    digest = hashlib.sha256(":".join((*scope, source)).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


# ── PRMS…, the AMP file (office 확인 2026-07-30) ───────────────────────────
#
# read_amp_info's eighteen fields — how one parameter is actually measured off
# the image, where cond.txt says how the image was taken. Every value is a str.
#
# Two things this file does that cond.txt does not:
#
#   * NO UNITS ANYWHERE. Design_Value is '266.1', not '266.1 nm'. So "does a
#     value carry its unit" is per-FILE, not a property of this pipeline, and
#     nothing may assume either way.
#   * FIVE fields are ', '-joined PAIRS — Threshold, Edge_Search_Direct.,
#     Edge_Number, Base_Line_Start_Pint, Base_Line_Area. A width measurement has
#     two edges and each takes its own setting. Same ', ' separator cond.txt
#     uses for coordinates, and the same rule applies: shown verbatim.
#
# A generator of None means the KEY is confirmed but its VALUE FORMAT is not —
# the office sample listed the key without a value. Those emit the same obviously
# synthetic hex that the still-unknown readers do (_block), so the block shows
# the right contract without teaching a format nobody has seen. Fill one in the
# moment a real value turns up.
_AMP_FIELDS: tuple[tuple[str, object], ...] = (
    # Enumerated strings: exactly one real value known each, so it is emitted
    # verbatim on every file. One sample teaches a format, never a domain.
    ("Measurement", lambda _: "Width"),
    ("Object", lambda _: "Space"),
    ("Kind", lambda _: "Multi_Point"),
    ("Measurement_Point", lambda r: str(r.choice((16, 32, 64)))),
    ("Data", lambda _: "Mean"),
    ("Method", lambda _: "Linear"),
    # The parameter's target CD. Varied — a compare screen whose Design_Value is
    # identical across two different recipes would show no difference where the
    # office shows the whole point of the comparison.
    ("Design_Value", lambda r: f"{r.uniform(40.0, 400.0):.1f}"),
    ("Search_Area", None),
    ("Inspect_Area", None),
    ("Smoothing", None),
    ("Differential", None),
    ("Threshold", lambda r: _pair(r.choice((40, 50, 60)))),
    ("Edge_Search_Direct.", lambda _: _pair("Normal")),
    ("Edge_Number", lambda r: _pair(r.choice((1, 2)))),
    ("Base_Line_Start_Pint", lambda r: _pair(r.choice((2, 3, 4)))),
    ("Base_Line_Area", lambda r: _pair(r.choice((8, 10, 12)))),
    ("Sum_Line_Point", None),
    ("Target", None),
)

# OFFICE-VERIFY: two key SPELLINGS above are reproduced exactly as the office
# sample gave them and both look like the tool's own typos rather than ours —
# 'Edge_Search_Direct.' ends in a period (a truncated "Direction") and
# 'Base_Line_Start_Pint' reads as "Point" misspelled. Left verbatim on purpose:
# these are contract keys, and silently correcting one would make home and
# office disagree about a key name, which is the exact class of bug this file
# exists to prevent. Confirm against a second sample.


def _pair(value: object) -> str:
    """'50, 50' — one setting per edge, ', ' separated (office 확인 2026-07-30)."""
    return f"{value}, {value}"


def _unknown_value(rng: random.Random) -> str:
    """A value that cannot be mistaken for a real one.

    Used where the key is confirmed but its format is not. Deliberately shares
    the look of ``_block``'s placeholders so "we have not seen this" reads the
    same everywhere on the screen.
    """
    return f"{rng.getrandbits(16):04X}"


def _amp_block(source: str | None, *scope: str) -> SettingBlock | None:
    """The PRMS… AMP file, with its REAL field names (office 확인 2026-07-30)."""
    if source is None:
        return None
    rng = _seeded_rng(source, *scope)
    return {
        "source": source,
        "rows": [
            {"key": key, "value": generate(rng) if generate else _unknown_value(rng)}
            for key, generate in _AMP_FIELDS
        ]
    }


def _block(source: str | None, prefix: str, count: int, *scope: str) -> SettingBlock | None:
    """Fabricated settings for one raw file, or None when the slot names none.

    Generated HERE rather than through ``office_utils.idp_amp_reader``: that
    package is office-only and gitignored, so importing it would make the mock —
    the thing every home session and a fresh clone actually run — depend on a
    file that is not in the repository. The office adapter imports it; this one
    must not.

    ``scope`` carries the recipe identity as well as the filename. Seeding on
    the filename alone would make two different recipes that share a SEQ return
    identical settings, so a compare of two genuinely different recipes would
    silently show no differences.
    """
    if source is None:
        return None
    digest = hashlib.sha256(":".join((*scope, source)).encode("utf-8")).hexdigest()
    return {
        "source": source,
        "rows": [
            {
                "key": f"{prefix}_FIELD_{index + 1}",
                "value": digest[index * 4:(index + 1) * 4].upper()
            }
            for index in range(count)
        ]
    }


def _fake_locator(recipe_id: str) -> IdpLocator:
    """A plausible-shaped FTP locator for one recipe.

    Office-side this is resolved from meas_hist (eqp_ip, class_name, idw_name,
    idp_name). At home there is no such lookup, so it is derived from the recipe
    id — stable, and shaped so the frontend's round-trip (detail -> locator ->
    param-detail) is genuinely exercised rather than stubbed out.

    The IP is inside 10.0.0.0/8 so it survives ``validate_tool_ip``; nothing
    listens on it, which is correct — at home no adapter opens a socket.
    """
    seed = _seed_for_values("locator", recipe_id)
    return {
        "eqp_ip": f"10.{seed % 251}.{(seed // 251) % 251}.{(seed // 63001) % 251}",
        "class_name": "MOCKCLS",
        "idw": f"IDW_{seed % 10000:04d}",
        "idp": f"IDP_{seed % 10000:04d}"
    }


def get_param_detail(
    items: list[ParamDetailRequestItem]
) -> list[ParamDetailResponse]:
    """Settings and image names for each requested (recipe, parameter).

    List-shaped because compare fans out across recipes and ``/api/*`` allows
    only 20 requests per 5 s per user — as N separate calls a 20-recipe compare
    would trip the limit on the first cell a user looked at.
    """
    stage_of = {slot["key"]: slot["stage"] for slot in IMAGE_SLOTS}
    out: list[ParamDetailResponse] = []
    for item in items:
        # Same planner the office adapter uses, so the two cannot disagree
        # about which file a slot names.
        amp, af_pr, images = rawfiles.slot_sources(item.get("slots") or {})
        locator = item.get("locator") or {}
        scope = (str(locator.get("idp", "")), item.get("parameter", ""))
        out.append({
            "parameter": item.get("parameter", ""),
            "amp": _amp_block(amp, *scope),
            "af_pr": _block(af_pr, "AFPR", _AFPR_FIELDS, *scope),
            "images": [
                {
                    "slot": slot,
                    "stage": stage_of.get(slot, slot),
                    "name": name,
                    # Always SEM: an optical microscope takes no measurement or
                    # addressing image. Only wafer align has an OM file.
                    "cond": _cond_block(cond, "SEM", *scope)
                }
                for slot, name, cond in images
            ]
        })
    return out


def get_align_detail(
    locator: IdpLocator,
    p_numbers: list[int]
) -> AlignDetailResponse:
    """Wafer-align image, beam condition and AF/PR setting per align point.

    Points are the sorted unique ``P.No`` values — the align table repeats a
    P.No across rows, and each distinct one names exactly one file set.

    Office-side these two files go to align-specific readers rather than the
    parameter ones: the ENAP setting to ``get_align_beam_pr_conditions`` (once
    for the whole list) and the image's cond.txt to
    ``read_align_image_condition``, which additionally needs to be told whether
    the point is OM or SEM. The mock cannot call either — it fabricates — but it
    mirrors the CONSEQUENCES, which is what the screen sees: distinct field
    prefixes per reader, and no image condition at all for a point that is
    neither 1 nor 2.
    """
    scope = str((locator or {}).get("idp", ""))
    points: list[AlignPoint] = []
    for p_no in sorted({int(p) for p in p_numbers}):
        image, setting = rawfiles.align_names(p_no)
        points.append({
            "P_No": p_no,
            "image": image,
            # The image condition is read PER OPTIC, and only points 1 and 2
            # have one (1 = OM, 2 = SEM). An unexpected point number leaves the
            # office with no `which` to pass, so it renders 파일 없음 there and
            # must render the same here.
            #
            # The optic is not just a label: OM writes FIVE keys and SEM the
            # full twelve (office 확인 2026-07-30), so a point routed to the
            # wrong optic shows the wrong number of rows rather than merely a
            # wrong heading.
            "cond": _cond_block(
                rawfiles.cond_source(image),
                optics,
                scope,
            ) if (optics := rawfiles.align_optics(p_no)) else None,
            "setting": _block(setting, "ALIGNPR", _ALIGNPR_FIELDS, scope)
        })
    return {"points": points}


def fetch_recipe_image(locator: IdpLocator, name: str) -> tuple[bytes, str]:
    """A seeded SVG placeholder, exactly as msr_image's mock does it.

    An SVG renders in the same ``<img>`` the office JPEG will, without
    pretending to be a SEM photograph — a fabricated micrograph is the one kind
    of mock data that could be mistaken for a measurement.
    """
    hue = _seed_for_values("recipe-image", name) % 360
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240">'
        f'<rect width="320" height="240" fill="hsl({hue} 30% 18%)"/>'
        f'<text x="160" y="118" fill="hsl({hue} 55% 80%)" font-size="15" '
        'font-family="monospace" text-anchor="middle">'
        f'{name}</text>'
        f'<text x="160" y="140" fill="hsl({hue} 40% 60%)" font-size="11" '
        'font-family="monospace" text-anchor="middle">mock placeholder</text>'
        '</svg>'
    )
    return svg.encode("utf-8"), "image/svg+xml"


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
        "idp_image_info": idp_rows,
        "locator": _fake_locator(resolved_recipe_id),
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
    """Compact per-recipe comparison payload: IDP fields + slot image names.

    Reuses get_recipe_open_data so compare matches open. AMP is NOT included:
    it is fetched per visible cell through param-detail, so compare shows the
    same real settings the open screen does rather than its own fabrication.
    Each recipe carries its locator because those fetches are per tool.
    """
    recipes: list[CompareRecipe] = []
    for name in recipe_names:
        clean = (name or "").strip()
        if not clean:
            continue
        detail = get_recipe_open_data(
            recipe_id=clean, fac_id=fab_name, tool_category=tool_type
        )

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
                # The five img_* values verbatim — this is exactly what the
                # client posts back as param-detail's `slots`.
                "images": {slot["key"]: idp[slot["key"]] for slot in IMAGE_SLOTS}
            })
        recipes.append({
            "recipe_id": detail["recipe_id"],
            "fac_id": detail["fac_id"],
            "locator": detail["locator"],
            "parameters": parameters
        })

    return {"tool_type": tool_type, "fab_name": fab_name, "recipes": recipes}
