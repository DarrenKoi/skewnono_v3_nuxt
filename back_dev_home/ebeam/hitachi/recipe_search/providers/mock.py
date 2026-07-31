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
    rng: random.Random | None = None,
    *,
    idp_rows: list[IdpImageInfoRow]
) -> list[WaferMpInfoRow]:
    """Generate dummy wafer measurement point information.

    ``idp_rows`` is required, and keyword-only so it cannot be passed by
    accident. This table does not stand on its own: two of its columns are
    determined by the parameter the point measures, and both were previously
    drawn independently here, so home data contradicted the office on every row.

      * ``P_No`` == that parameter's ``Region`` (office 확인 2026-07-28) — the
        integer key that joins the two tables. Drawing it separately made the
        documented join return another parameter's rows, which reads from here
        as "the doc is wrong" rather than "the mock is".
      * ``D_No == -1`` ⟺ that parameter's ``dnumber_removed`` (office 확인
        2026-07-28) — the same suppression fact, recorded per point on this
        side and per parameter on the other. ``randint(1, 100)`` never produced
        -1, so the suppressed case did not exist at home at all.
    """
    active_rng = rng or random.Random()
    data: list[WaferMpInfoRow] = []

    # Keyed by PARAMETER: Region and dnumber_removed are parameter-level, so the
    # several rows a parameter may own collapse to one entry here. (The img_*
    # slots, which are what genuinely differ between those rows, are not read.)
    pool = list({
        row["Parameter"]: (row["Region"], row["dnumber_removed"])
        for row in idp_rows
    }.items())
    if not pool:
        return data

    for _ in range(num_records):
        chip_x = active_rng.randint(1, 10)
        chip_y = active_rng.randint(1, 10)
        parameter, (region, dnumber_removed) = active_rng.choice(pool)
        # Drawn unconditionally so the suppressed branch does not shift the
        # random stream and make the seeded output depend on the coin flip.
        d_no = active_rng.randint(1, 100)

        data.append({
            "ChipNo_X": chip_x,
            "ChipNo_Y": chip_y,
            "Coordinate_X": round(active_rng.uniform(-50.0, 50.0), 3),
            "Coordinate_Y": round(active_rng.uniform(-50.0, 50.0), 3),
            "P_No": region,
            "D_No": -1 if dnumber_removed else d_no,
            "Diff": active_rng.choice([True, False]),
            "Rel": active_rng.choice([True, False]),
            "Rel_MoveX": round(active_rng.uniform(-5.0, 5.0), 3),
            "Rel_MoveY": round(active_rng.uniform(-5.0, 5.0), 3),
            "Coordinate_X_r": round(active_rng.uniform(-50.0, 50.0), 3),
            "Coordinate_Y_r": round(active_rng.uniform(-50.0, 50.0), 3),
            "Parameter": parameter,
            # NOT a filename: the real parser emits P_No's value here
            # (user-confirmed 2026-07-27). This mock previously fabricated
            # "IMG_MEAS_0001.jpg", which taught the frontend to expect a
            # string that office data never produces.
            "img_meas2": region
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
    """Generate dummy IDP image information.

    ★ The img_* slots belong to the ROW, not to the Parameter. A row is one image
      definition (docs/datatables/recipe_idp.txt), so the slots here are built
      from SEQ while `Parameter` is drawn at random and repeats — Para_13 at
      SEQ 4/6 names IMMP0004… and at SEQ 11/15 names IMMP0011….

      That is deliberate and worth keeping: anything downstream that caches or
      joins raw files per Parameter shows one row's images under another row's
      heading, with no error to notice. The recipe-open param-detail cache did
      exactly that until 2026-07-30, and this mock is what exposed it.

    ★ What is NOT row-level: ``Region`` and ``dnumber_removed`` describe the
      PARAMETER (docs/datatables/recipe_idp.txt), so the rows a parameter
      repeats across must agree on both. ``dnumber_removed`` used to be flipped
      per row, which let one parameter be suppressed and not suppressed at once
      — an ill-defined answer for anything grouping by parameter, and it makes
      the D_No ⟺ dnumber_removed invariant unsatisfiable by construction.
    """
    active_rng = rng or random.Random()
    data: list[IdpImageInfoRow] = []
    # Decided once per parameter, then reused by that parameter's other rows.
    removed_by_parameter: dict[str, bool] = {}

    for index in range(num_records):
        p_no = active_rng.randint(1, 20)
        seq = index + 1
        parameter = f"Para_{p_no}"
        if parameter not in removed_by_parameter:
            removed_by_parameter[parameter] = active_rng.choice([True, False])

        data.append({
            "Parameter": parameter,
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
            # Parameter-level, not row-level — see the note above. True means the
            # parameter's data is suppressed, which wafer_mp_info records as
            # D_No = -1 on every point measuring it.
            "dnumber_removed": removed_by_parameter[parameter]
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


# ALL FIVE readers were run against real files at the office (2026-07-30) via
# scripts/probe_recipe_ftp.py, so no raw file's FIELD NAMES are guessed any
# more — the counted placeholders that used to live here are gone. What remains
# unknown is narrower and is marked per field: some VALUES have never been seen,
# and those emit _unknown_value() rather than a plausible invention. Inventing
# credible-looking data is how AmpRow's sixteen fabricated fields went
# unquestioned for months.

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
# OFFICE-VERIFY — DEFERRED, cannot be confirmed for now (2026-07-30). It comes
# from ONE SEM sample, and whether a second recipe keeps the product is
# unanswered rather than merely unchecked. It stays because the alternative,
# drawing the two independently, asserts that they are UNRELATED — equally
# unverified and worse: it would render tables that contradict themselves. This
# is a mock-internal consistency choice, not a documented office rule, and the
# office adapter neither knows nor uses it.
#
# It is NOT applied to OM. The OM sample carries a Field_Size key with NO VALUE
# (user-confirmed 2026-07-30), so the mock emits an empty one, which the screen
# renders as a dash rather than a number. Deriving OM's field size from the SEM
# constant, as this did until 2026-07-30, invented a cross-optic relationship
# nobody has observed and printed 1297.788 um as though it had been read.
_FOV_MAG_PRODUCT = 134_970.0

# The OM magnification seen at the office. VARIED around it, not pinned to it:
# the OM values differ between recipes (user-confirmed 2026-07-30), so emitting
# 104 on every file — which this did until then, reasoning that an optical
# scope's magnification is fixed by its lens — taught a constant that is not one.
# The sample stays in the set; the rest is plausible spread, not office
# distribution.
_OM_MAGNIFICATIONS: tuple[int, ...] = (70, 104, 140, 200)


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
    magnification = (
        rng.choice(_OM_MAGNIFICATIONS) if om
        else rng.choice((20_000, 30_000, 50_000, 100_000, 150_000))
    )
    side = _FOV_MAG_PRODUCT / magnification
    return {
        "Accelerating_voltage": f"{rng.choice((300, 500, 800))} V",
        "Probe_current": f"{rng.choice((4.0, 8.0, 16.0)):.1f} pA",
        "Magnification": str(magnification),
        "Number_of_frames": str(rng.choice((8, 16, 32, 64))),
        "Image_rotation": f"{rng.choice((0.0, 90.0, 180.0, 270.0)):.1f} deg",
        # Die-relative for both optics. The OM sample read 0,0 — plausibly
        # because an align mark sits at a die origin — but OM values vary
        # between recipes (user-confirmed 2026-07-30), so 0,0 is drawn as ONE
        # possibility rather than emitted as OM's constant. The wafer coordinate
        # is the larger of the two either way: it spans a 300 mm wafer, i.e.
        # 300,000 um.
        "Chip_coordinate": _um_pair(0, 0) if om and rng.random() < 0.5
        else _um_pair(rng.randrange(0, 30_000), rng.randrange(0, 30_000)),
        "Wafer_coordinate": _um_pair(rng.randrange(0, 300_000), rng.randrange(0, 300_000)),
        # Empty for OM: the key is there, the value is not.
        "Field_Size": "" if om else f"{side:.3f} um, {side:.3f} um",
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
#     Edge_Number, Base_Line_Start_Point, Base_Line_Area. A width measurement has
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
    ("Base_Line_Start_Point", lambda r: _pair(r.choice((2, 3, 4)))),
    ("Base_Line_Area", lambda r: _pair(r.choice((8, 10, 12)))),
    ("Sum_Line_Point", None),
    ("Target", None),
)

# 'Edge_Search_Direct.' really does end in a period — a truncated "Direction"
# (user-confirmed 2026-07-30). Left verbatim because it is a contract key, and
# silently "fixing" a real one would make home and office disagree about a name.
#
# It is the ONLY one. Four odd spellings were flagged that day and THREE were
# our own transcription slips, corrected once asked: Base_Line_Start_Pint ->
# Point, "Pre does" -> "Pre Dose", "Measurement Excution" -> "Execution". Worth
# recording, because the instinct was to preserve all four as tool quirks. The
# cost is asymmetric — a preserved slip is a key the office never sends and the
# screen silently omits — so an odd spelling is worth one question every time.


def _pair(value: object) -> str:
    """'50, 50' — one setting per edge, ', ' separated (office 확인 2026-07-30)."""
    return f"{value}, {value}"


def _unknown_value(rng: random.Random) -> str:
    """A value that cannot be mistaken for a real one.

    Used where the key is confirmed but its format is not. Deliberately shares
    the look of ``_block``'s placeholders so "we have not seen this" reads the
    same everywhere on the screen.

    ALWAYS STARTS WITH A LETTER. Plain 4-digit hex is all-numeric about one time
    in sixteen, and the browser promptly showed `Mag = 1484` — a placeholder
    reading as a perfectly plausible magnification, which is the one thing this
    function exists to prevent. Leading A-F makes every one of them impossible
    to read as a number.
    """
    return f"{rng.choice('ABCDEF')}{rng.getrandbits(12):03X}"


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


# ── ENMP…, the AF/PR file (office 확인 2026-07-30) ─────────────────────────
#
# read_af_pr_condition is the ONE reader that returns a dict OF DICTS rather
# than a flat mapping. Eight groups, which is why SettingRow grew an optional
# ``section``: flattening them would put two passes of the same settings under
# one heading, and dotting the names together would leave the grouping
# recoverable only by string-splitting.
#
# A recipe measures in a basic sequence — addressing, then measurement — and
# addressing runs NONE, ONCE or TWICE depending on the parameter. With NONE,
# the addressing groups are simply absent from the parsed result
# (user-confirmed 2026-07-30), so the group list is not fixed.
#
# ★ ENMP's values are NOT all strings (office 확인 2026-07-30). It is the first
#   reader where that is false, and the mixture is WITHIN one group:
#   measurement_focusing's Wait(s) and Relative Position X/Y(um) come back as
#   Python floats while Offset(LSB), Method and Mag are str. cond.txt and AMP
#   are genuinely all-str, so "the readers return strings" was a per-file fact
#   about those two, never a property of this pipeline.
#
#   SettingRow.value is still str because the adapter's _to_rows stringifies
#   everything (a float 2.0 reaches the screen as "2.0"). Nothing here needs to
#   change for that — but nothing may assume the READER handed back a string.
#
# Each entry is (key, generator) with the same rule as _AMP_FIELDS: a generator
# of None means the value has never been seen and renders as obvious hex.
#
# Pass 1 and pass 2 SHARE their key tuples below rather than repeating them:
# "addressing_auto_focus2 is likewise as 1" is a fact, and two literal copies
# could drift apart while still passing every test.
# Every key's TYPE is known here, and Method's value (office 확인 2026-07-30).
# Method being 'Fast2' in BOTH auto-focus groups is the first evidence that the
# addressing and measurement focusing steps share a vocabulary — which is why
# the remaining values are still not copied across from measurement_focusing:
# one key agreeing is evidence, not proof, and an addressing focus may well wait
# longer than a measurement one.
#
# A known type is a known FORMAT for floats — only the magnitude is open — so
# those render float-shaped. `str` determines nothing on its own: in this one
# file it has meant '0', 'Fast2' and '50, 50', so str-typed keys whose value is
# unread stay hex placeholders.
# ── the dtype rule, INFERRED not read (2026-07-30) ────────────────────────
#
# Fourteen key types are confirmed across measurement_focusing and
# addressing_auto_focus, and they split cleanly on one signal: a key naming a
# PHYSICAL unit in parentheses is float, everything else is str.
#
#   float   Wait(s) · Relative Position X(um) · Relative Position Y(um)
#   str     Offset(LSB) · Mag · Method · Threshold · Charging Voltage
#
# Offset(LSB) is what makes it a rule about physical units rather than about
# parentheses: LSB is a digital quantum, counted, and it comes back as str.
#
# The unread groups below are typed by this rule at the user's direction rather
# than left blank. They are marked 추론 (inferred) wherever they appear, never
# `office 확인` — the distinction is the entire value of this file, and the rule
# has already been wrong once in spirit: nothing predicted that Mag would be a
# sentinel '0'. A wrong guess here shows up as a float rendered where the office
# sends a string, which the adapter absorbs (it stringifies everything) but the
# doc would be lying about.


def _wait_seconds(rng: random.Random) -> str:
    """A float Wait(s), biased to the 0.0 actually seen. The unit is in the key,
    so the value carries none. Spread is plausible, not office distribution."""
    return str(rng.choice((0.0, 0.0, 0.0, 0.5, 1.0, 2.0)))


def _relative_position(rng: random.Random) -> str:
    """A float Relative Position X/Y(um). One sample read 2.0."""
    return str(round(rng.uniform(-5.0, 5.0), 1))


_AF_FIELDS: tuple[tuple[str, object], ...] = (
    ("Method", lambda _: "Fast2"),
    ("Offset(LSB)", None),                   # str, value unread
    ("Wait(s)", _wait_seconds),
    ("Relative Position X(um)", _relative_position),
    ("Relative Position Y(um)", _relative_position),
    ("Mag", None),                           # str, value unread
    ("Threshold", None),                     # str, value unread
    ("Charging Voltage", None),              # str, value unread
)
# 추론 (2026-07-30): Wait(s) is float by the unit rule; Acceptance and ABC are
# str. Acceptance is deliberately NOT given ENAP's '200' — that is a different
# file, and Method already proved a shared key name carries its own vocabulary
# per file.
_PR_FIELDS: tuple[tuple[str, object], ...] = (
    ("Acceptance", None),
    ("Wait(s)", _wait_seconds),
    ("ABC", None),
)

# In the office's own key order. `sequence_*` groups list the STEPS of a
# sequence rather than settings — their keys are stage names, and the groups
# below them hold each stage's settings.
_AFPR_SECTION_FIELDS: dict[str, tuple[tuple[str, object], ...]] = {
    # 추론 (2026-07-30): every key here is a STAGE NAME, so its value says
    # whether that stage runs — no physical unit, therefore str by the rule
    # above. Left as placeholders: the rule types them, it does not tell us
    # whether the office writes 'ON'/'OFF', 'Yes'/'No' or an order number, and
    # those three would render very differently.
    "sequence_addressing": (
        ("Pre Dose", None), ("Auto Focus1", None), ("Pattern Recognition1", None),
        ("Pattern Recognition2", None), ("Auto Focus2", None),
    ),
    "sequence_measurement": (
        ("Focusing", None), ("Pattern Recognition", None),
        ("Measurement Execution", None), ("Image Save", None),
    ),
    # 추론 (2026-07-30): Wait(s) · Relative Position(um) · Offset(um) are float
    # by the unit rule — note Relative Position(um) has NO X/Y here, one key for
    # both axes, unlike the focusing groups. Acceptance, ABC, Centering and
    # Contrast Mode are str.
    "measurement_pattern_recognition": (
        ("Acceptance", None),
        ("Wait(s)", _wait_seconds),
        ("ABC", None),
        ("Centering", None),
        ("Relative Position(um)", _relative_position),
        ("Offset(um)", _relative_position),
        ("Contrast Mode", None),
    ),
    # The one group read END TO END — every key's type and a real value
    # (office 확인 2026-07-30). Note Wait(s) and Offset(LSB) both express "zero"
    # and do it with DIFFERENT dtypes, float 0.0 versus str '0', inside one
    # group. The dtypes are not semantically driven, so they cannot be reasoned
    # about — only read.
    "measurement_focusing": (
        ("Wait(s)", _wait_seconds),
        # str '0' — not the float 0.0 its neighbour uses for the same idea.
        ("Offset(LSB)", lambda _: "0"),
        # 'Fast2' — NOT AMP's Method vocabulary, which is 'Linear'. Same key
        # name in two files with two different domains, which is why a value is
        # never carried across from another file.
        ("Method", lambda _: "Fast2"),
        ("Relative Position X(um)", _relative_position),
        ("Relative Position Y(um)", _relative_position),
        # str '0' — a SENTINEL, not a magnitude: in an auto-focus group it means
        # "use the same magnification as the measurement" (user-confirmed
        # 2026-07-30). Asked whether it would be '30000' or '50.0K'; it was
        # neither, and it is not even a number on the same scale. The clearest
        # case yet for why an unseen value is never inferred from its key name.
        #
        # Shown verbatim as '0' and NOT annotated (user-confirmed 2026-07-30):
        # the engineers reading this screen already know what it means. Which
        # settles it the right way round — the frontend does not hard-code
        # meaning for one (section, key) pair, so the open key/value contract
        # stays intact and these names can still change freely.
        ("Mag", lambda _: "0"),
    ),
    # The addressing auto-focus groups repeat six of measurement_focusing's keys
    # and probably repeat its values too — but "probably" is not "read", and
    # Method already differs between AMP and ENMP for the same key name. Left as
    # placeholders so the screen keeps showing which group was actually opened.
    "addressing_auto_focus1": _AF_FIELDS,
    "addressing_pattern_recognition1": _PR_FIELDS,
    "addressing_auto_focus2": _AF_FIELDS,
    "addressing_pattern_recognition2": _PR_FIELDS,
}

# The groups an addressing pass contributes, in that same office order. Slicing
# this by pass count is what "none / once / twice" means here.
_AFPR_PASS_SECTIONS: tuple[tuple[str, ...], ...] = (
    ("sequence_addressing", "addressing_auto_focus1", "addressing_pattern_recognition1"),
    ("addressing_auto_focus2", "addressing_pattern_recognition2"),
)

# ★ ENMP is why a setting row's identity is (section, key) rather than key:
#   addressing_auto_focus1 and 2 carry the IDENTICAL key tuple, and
#   "Acceptance" alone appears in three ENMP groups AND in ENAP. Keying on the
#   bare name would collapse rows that mean different things.
#
# ★ A THIRD unit convention. cond.txt puts the unit in the VALUE ('500 V'), AMP
#   omits it entirely ('266.1'), and ENMP puts it in the KEY NAME — 'Wait(s)',
#   'Offset(LSB)', 'Relative Position X(um)'. Three files, three conventions, so
#   nothing downstream may assume any of them.
#
# OFFICE-VERIFY: most of the VALUES. Only measurement_focusing's have been
# looked at; every other group's are unseen and render as visibly-synthetic hex,
# the same treatment the AMP file's six valueless keys get. Inferring a format
# from a key name ('Wait(s)' is surely a number) is exactly the reasoning that
# produced AmpRow's sixteen invented fields — note that even for the one group
# we HAVE seen, the surprise was the dtype (float, not str) rather than the
# magnitude. Fill each in as a real sample turns up.
#
# These keys and values are expected to CHANGE as the office parser is refined
# (user-noted 2026-07-30). That costs one edit to this table: nothing keys off
# these strings in code, the contract is open key/value, and the frontend
# renders whatever arrives.


def _afpr_sections(rng: random.Random) -> tuple[str, ...]:
    """The groups this parameter's ENMP carries, for 0, 1 or 2 addressing passes.

    Office-side the passes are whatever the file itself contains. Here they are
    drawn from the block's seed, because get_param_detail is handed only the
    slot names — the idp_image_info row's Addressing / Double_Addressing flags,
    which are the same fact, stay on the client. Seeded, so a parameter's group
    list does not change between two views of the same recipe.

    Filtered from _AFPR_SECTION_FIELDS rather than concatenated, so the result
    keeps the office's own key order however many passes ran.
    """
    passes = rng.choice((0, 1, 1, 2))
    present = {
        section
        for group in _AFPR_PASS_SECTIONS[:passes]
        for section in group
    }
    return tuple(
        section for section in _AFPR_SECTION_FIELDS
        if not section.startswith(("sequence_addressing", "addressing_"))
        or section in present
    )


def _afpr_block(source: str | None, *scope: str) -> SettingBlock | None:
    """The ENMP… AF/PR file: real group and key names, most values still unseen."""
    if source is None:
        return None
    rng = _seeded_rng(source, *scope)
    return {
        "source": source,
        "rows": [
            {
                "key": key,
                "value": generate(rng) if generate else _unknown_value(rng),
                "section": section,
            }
            for section in _afpr_sections(rng)
            for key, generate in _AFPR_SECTION_FIELDS[section]
        ]
    }


# ── ENAP…, the align beam/PR file (office 확인 2026-07-30) ─────────────────
#
# get_align_beam_pr_conditions takes the whole ENAP list in one call and returns
# a dict keyed by OPTIC — {"OM": {...}, "SEM": {...}} — which settles the
# question the adapter was built to hedge against: its result CAN be split per
# align point, because P.No 1 is OM and P.No 2 is SEM.
#
# Both optics carry the same two keys. Note the SPACE in "Auto Focus": the only
# key across all five readers that is not underscore-joined, so nothing may
# assume identifier-shaped keys.
_ALIGNPR_FIELDS: tuple[tuple[str, object], ...] = (
    ("Acceptance", lambda r: str(r.choice((100, 150, 200, 250)))),
    ("Auto Focus", lambda _: "OFF"),
)


def _alignpr_block(source: str | None, *scope: str) -> SettingBlock | None:
    """One align point's ENAP block (office 확인 2026-07-30)."""
    if source is None:
        return None
    rng = _seeded_rng(source, *scope)
    return {
        "source": source,
        "rows": [
            {"key": key, "value": generate(rng)}
            for key, generate in _ALIGNPR_FIELDS
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
            "af_pr": _afpr_block(af_pr, *scope),
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
            "setting": _alignpr_block(setting, scope)
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
        "wafer_mp_info": generate_wafer_mp_info(rng=rng, idp_rows=idp_rows),
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
