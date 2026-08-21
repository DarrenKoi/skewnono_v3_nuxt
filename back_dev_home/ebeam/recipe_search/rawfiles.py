"""Pure path arithmetic for the raw-recipe folder beside the .idp.

No I/O, no phase, no office dependency — which is the point. Naming is the part
of this feature most likely to be wrong and the part that cannot be checked from
home against a live tool, so it is isolated here where it needs no tool at all.
Same reasoning that already separates ``providers/office_example.py``'s
``_to_detail_response``.

Layout (user-confirmed 2026-07-29), under
``/HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}/``::

    IMMP0001.jpeg          img_add1    addressing image 1
    .IMMP0001.jpeg/cond.txt            its beam condition (hidden sibling dir)
    ENMP0000               img_add2    AF/PR setting  (column value is PRMP0000)
    I2MP0000.jpeg          image_add3  addressing image 3
    IMMS0000.jpeg          img_meas1   measurement image
    PRMS0000               img_meas2   AMP setting    (column value used as-is)
    IMAP0001.jpeg          P.No = 1    align image     (P.No 1 = OM, 2 = SEM)
    ENAP0001               P.No = 1    align setting

Every value is ``{kind}{stage}{NNNN}`` — ``IM``/``I2`` name images, ``PR`` names
a setting key the tool wrote, ``EN`` names the condition file that key resolves
to, and the stage is ``MP`` (addressing), ``MS`` (measurement) or ``AP`` (align).

ONE SLOT IS NOT ALWAYS ONE FILE (user-confirmed 2026-08-08). The layout above
is the CD-SEM shape: the slot stem plus ``.jpeg`` IS the file. HV-SEM tools
shoot one image slot as SEVERAL files, suffixing the shared stem per targeting
sub-position — ``IMMS0001-U.jpeg`` / ``-T`` / ``-M`` / ``-L``. Which suffixes a
slot actually has cannot be derived (it depends on the targeting measurement
point), so a name can only be DISCOVERED from the raw folder's listing:
``slot_sources`` takes one and expands each slot to every matching file, and
``image_name`` remains only as the no-listing fallback (exactly the pre-2026-08-08
behavior, which is also the CD-SEM fast path).

Schema of record: ``docs/datatables/recipe_idp.txt``. If that file and this one
disagree, that file wins and this one is stale.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from back_dev_home._core.image_naming import HV_SEM_STEM_SUFFIXES
from back_dev_home.msr_image.cache import PREVIEW_SUFFIX
from back_dev_home.msr_image.paths import cond_path

__all__ = [
    "ALIGN_OPTICS",
    "EMPTY_SLOT",
    "IMAGE_EXTENSIONS",
    "IMAGE_SLOT_KEYS",
    "KNOWN_STEM_SUFFIXES",
    "PART_SLOTS",
    "SETTING_SLOT",
    "SLOT_PREFIX",
    "align_names",
    "align_optics",
    "align_point_of",
    "align_reference_images",
    "slot_sources",
    "cond_remote_path",
    "cond_source",
    "image_name",
    "image_stem",
    "image_variants",
    "is_empty",
    "raw_dir",
    "recipe_image_cache_key",
    "remote_path",
    "setting_name",
]

# Shared with msr_image (office 확인 2026-07-24): images/{msr} and data/{idw}
# are siblings under one tree, on the same servers.
_ROOT = "/HITACHI/DEVICE/HD"

# French "non", NOT a truncated "none" (user-confirmed 2026-07-29). A slot
# holding this has no file and must not produce an FTP request. "none" is an
# ordinary value here and is deliberately not treated as a sentinel.
EMPTY_SLOT = "non"

# The columns that name an image. img_add2 and img_meas2 are setting keys and
# have no image of their own; image_add3 breaks the img_* naming run but IS an
# image, which is exactly why it is listed rather than derived from a prefix.
IMAGE_SLOT_KEYS: tuple[str, ...] = ("img_add1", "image_add3", "img_meas1")

# The slot each SETTING file is named by. Read by ``slot_sources`` below, so the
# names exist once rather than as literals inside it — ``param_info`` needs the
# same mapping to decide which slots an ``include=`` request may drop, and a
# second copy there would let a renamed slot make ``include=amp`` fetch nothing
# while ``slot_sources`` kept reading the real file.
SETTING_SLOT: dict[str, str] = {"amp": "img_meas2", "af_pr": "img_add2"}

# Every part a caller can ask for, to the slots naming its files. The union of
# these is what ``slot_sources`` consults, which is what makes dropping a slot
# equivalent to not reading its file.
PART_SLOTS: dict[str, tuple[str, ...]] = {
    "amp": (SETTING_SLOT["amp"],),
    "af_pr": (SETTING_SLOT["af_pr"],),
    "images": IMAGE_SLOT_KEYS,
}

# The prefixes wafer-align files carry. Named rather than inlined because the
# derivation (align_names) and the discovery (align_point_of) have to agree
# about them, and two literals four functions apart is how they stop agreeing.
ALIGN_IMAGE_PREFIX = "IMAP"

# ``IMAP0001``, or ``IMAP0001-U`` — the four-digit padding and the optional
# stem suffix in one statement. Fixed-width ``\d{4}`` is what makes
# ``IMAP00010`` a different file rather than P.No 1 with a stray digit: it
# cannot give a digit back to satisfy the anchor.
#
# There is no ENAP twin. The setting files are only ever DERIVED (align_names);
# nothing discovers them, so a second constant would be surface with no second
# reader to keep honest.
_ALIGN_STEM = re.compile(rf"{re.escape(ALIGN_IMAGE_PREFIX)}(\d{{4}})(-.*)?$")

# Which optic took an align image, by align point number (user-confirmed
# 2026-07-29). Align points are not scattered positions on the wafer so much as
# the same alignment seen through two optics, which is why there are usually
# exactly two and why the number alone identifies the instrument.
ALIGN_OPTICS: dict[int, str] = {1: "OM", 2: "SEM"}

# The {kind}{stage} prefix each column's value carries. Exported so the mock
# generates values on the same convention this module parses, rather than a
# second hand-written table that could drift onto a branch the office never
# takes (a slot not starting with "PR" makes setting_name return None).
SLOT_PREFIX: dict[str, str] = {
    "img_add1": "IMMP",
    "img_add2": "PRMP",
    "img_meas1": "IMMS",
    "img_meas2": "PRMS",
    "image_add3": "I2MP",
}

# Extensions an image file in the raw folder may carry. Same set msr_image
# accepts (office 확인 2026-07-24 there): tools serve JPEG previews and
# sometimes only a TIFF original, so filtering to .jpeg would make a tif-only
# variant undiscoverable.
IMAGE_EXTENSIONS: tuple[str, ...] = (".jpeg", ".jpg", ".tif", ".tiff")

# The HV-SEM stem suffixes, in the order the tools report them. ORDERING ONLY
# here — matching is open (any "-{suffix}" after the stem counts), so a fifth
# letter appearing on a tool is listed after these rather than dropped.
# Defined in _core because msr_file and msr_image must agree with this reader.
KNOWN_STEM_SUFFIXES: tuple[str, ...] = HV_SEM_STEM_SUFFIXES
_SUFFIX_RANK: dict[str, int] = {s: i for i, s in enumerate(KNOWN_STEM_SUFFIXES)}


def is_empty(value: str | None) -> bool:
    """Does this slot name no file? Case- and whitespace-insensitive."""
    return not value or value.strip().lower() == EMPTY_SLOT


def recipe_image_cache_key(locator, *, preview: bool = False) -> str:
    """Where one raw-recipe image sits in the shared image cache.

    ``{eqp_ip}/{class_name}/{idw}/{idp}/{name}`` — the raw folder's own path,
    so an object is inspectable without consulting code, exactly as
    msr_image's key is. ``locator`` carries the name too, because this is
    called as a cache backend's key function and those take one argument.

    It shares a MinIO prefix with msr_image's ``{eqp_ip}/{class_name}/{msr}/
    {name}``, and cannot collide with it: this key has five segments and that
    one has four, and ``msr`` can never supply the extra separator because
    ``validate_segment`` rejects "/" before any key is built. One prefix means
    ONE retention rule, which matters because the office enforces it twice —
    this app's nightly sweep and a flask_modules Airflow DAG — and a second
    prefix would be invisible to the second.
    """
    key = (
        f"{locator['eqp_ip']}/{locator['class_name']}/"
        f"{locator['idw']}/{locator['idp']}/{locator['name']}"
    )
    return key + PREVIEW_SUFFIX if preview else key


def raw_dir(class_name: str, idw_stem: str, idp_stem: str) -> str:
    """The raw-recipe folder: the .idp's sibling directory of the same name."""
    return f"{_ROOT}/{class_name}/data/{idw_stem}/{idp_stem}"


def remote_path(raw: str, name: str) -> str:
    return f"{raw}/{name}"


def image_stem(value: str | None) -> str | None:
    """The slot's 8-char stem (``'IMMP0001'``); an empty slot -> ``None``."""
    if is_empty(value):
        return None
    assert value is not None  # is_empty() already rejected None
    return value.strip()


def image_name(value: str | None) -> str | None:
    """``'IMMP0001' -> 'IMMP0001.jpeg'``; an empty slot -> ``None``.

    The DERIVED name — correct on CD-SEM, and only the fallback elsewhere:
    HV-SEM files suffix this stem (``IMMP0001-U.jpeg``), which no arithmetic
    can predict. Callers holding a raw-folder listing must expand through
    ``image_variants`` / ``slot_sources`` instead.
    """
    stem = image_stem(value)
    return None if stem is None else f"{stem}.jpeg"


def _image_file(entry: str) -> tuple[str, str] | None:
    """``(basename, stem)`` for a listing entry that names an image, else None.

    The rule both readers below match by, in one place: a listing entry may be
    a full path, only its basename counts, and only the four image extensions
    are images. A hidden cond sidecar (``.IMMP0001.jpeg/cond.txt``) fails on
    its ``.txt``; the sidecar DIRECTORY itself (``.IMMP0001.jpeg``) passes here
    and is rejected by the stem comparison, whose leading dot it keeps.
    """
    base = str(entry).replace("\\", "/").rsplit("/", 1)[-1]
    dot = base.rfind(".")
    if dot < 0 or base[dot:].lower() not in IMAGE_EXTENSIONS:
        return None
    return base, base[:dot]


def image_variants(stem: str, listing: Iterable[str]) -> list[str]:
    """Every file in the raw-folder ``listing`` that belongs to this slot.

    A file belongs when its extension is an image's and its own stem is either
    exactly ``stem`` (CD-SEM: one file per slot) or ``stem`` plus a ``-suffix``
    (HV-SEM: one file per targeting sub-position, user-confirmed 2026-08-08).
    Order is deterministic for the screen: the exact-stem file first, then the
    known suffixes in their reported order (U, T, M, L), then anything else
    alphabetically. Listing entries may be full paths; only the basename is
    compared, and the basename is what is returned.
    """
    ranked: list[tuple[int, int, str, str]] = []
    for entry in listing:
        parsed = _image_file(entry)
        if parsed is None:
            continue
        base, file_stem = parsed
        if file_stem == stem:
            ranked.append((0, 0, "", base))
        elif file_stem.startswith(f"{stem}-"):
            suffix = file_stem[len(stem) + 1:]
            ranked.append((1, _SUFFIX_RANK.get(suffix, len(_SUFFIX_RANK)), suffix, base))
    return [base for *_, base in sorted(ranked)]


def setting_name(value: str | None, *, pr_to_en: bool = False) -> str | None:
    """The setting file's name. ``pr_to_en`` for img_add2, off for img_meas2.

    Returns ``None`` rather than translating a value that does not start with
    ``PR``: a blind ``replace`` would request a PR file while the caller
    believes it holds EN settings, which reads as plausible wrong data instead
    of an error. The office reports the prefix is always ``PR``, so hitting this
    branch is a finding.
    """
    if is_empty(value):
        return None
    assert value is not None  # is_empty() already rejected None
    name = value.strip()
    if pr_to_en:
        if not name.startswith("PR"):
            return None
        name = f"EN{name[2:]}"
    return name


def align_optics(p_no: int) -> str | None:
    """``P.No -> "OM" | "SEM"``, or None when the point is not one of the two.

    ``read_align_image_condition`` needs this as its second argument, and it is
    the one argument that cannot be derived from a filename — the align image's
    cond.txt does not say which optic took it, the align point's NUMBER does
    (user-confirmed 2026-07-29): point 1 is the optical microscope, point 2 the
    SEM. Most recipes have both; some have only point 1.

    Returns None rather than defaulting for anything else, because both answers
    are wrong in the same way: a guessed "SEM" renders OM optics under a SEM
    heading and reads as perfectly ordinary data. Callers are expected to skip
    the condition and log, which shows up on screen as 파일 없음.
    """
    return ALIGN_OPTICS.get(p_no)


def align_names(p_no: int) -> tuple[str, str]:
    """``P.No -> (image, setting)``, both zero-padded to four digits.

    The padding is the rule, not the concatenation it looks like: ``"ENAP000" +
    str(p)`` agrees for p < 10 and breaks at p = 10, where it would produce a
    nine-character name in a folder where every name is eight.
    """
    return f"{align_image_stem(p_no)}.jpeg", f"ENAP{p_no:04d}"


def align_image_stem(p_no: int) -> str:
    """``1 -> 'IMAP0001'``. The padding rule, in the one place that owns it."""
    return f"{ALIGN_IMAGE_PREFIX}{p_no:04d}"


def align_point_of(entry: str) -> int | None:
    """The P.No a raw-folder entry names, or ``None`` if it names no align image.

    The reading half of ``align_names``, on the same rule ``image_variants``
    matches by: an image extension, the ``IMAP`` prefix, exactly four digits,
    and then either nothing or a ``-suffix``. ``IMAP00010.jpeg`` is therefore
    NOT P.No 1, and the hidden ``.IMAP0001.jpeg/`` sidecar directory is not an
    image — its basename keeps the leading dot, so it fails the prefix test.
    """
    parsed = _image_file(entry)
    match = _ALIGN_STEM.match(parsed[1]) if parsed else None
    return int(match.group(1)) if match else None


def align_reference_images(listing: Iterable[str]) -> list[tuple[int, str, str]]:
    """``[(p_no, optic, file_name), ...]`` for a recipe's align reference set.

    ONE definition for both providers. The office adapter and the mock have to
    name the same files here — a second copy of "point 1 is IMAP0001.jpeg and
    it is the OM" would let the mock teach a name the office never serves.

    DISCOVERED from ``listing``, not computed from ALIGN_OPTICS. Until
    2026-08-22 this returned both optics unconditionally, on the reasoning that
    align points are the same alignment through two instruments rather than
    scattered positions (user-confirmed 2026-07-29) and so are computable. The
    reasoning holds; the conclusion did not. A recipe with only P.No 1 exists
    (`docs/datatables/recipe_idp.txt`), and for one the computed P.No 2 sent
    the browser after a file the folder does not hold — which ``recipe-image``,
    alone on this feature's read surface, has to answer 404 rather than 파일
    없음, because a per-file GET has nowhere to drop a missing file to.
    Discovery also settles the open question of whether a tool splits align
    images into ``-U``/``-T``/``-M``/``-L`` the way HV-SEM splits its
    measurement slots (OFFICE-VERIFY): if one does, the files are found instead
    of the screen going blank on a fab-wide run of 404s.

    ``listing`` is REQUIRED, with no derived stand-in for a folder that could
    not be read. A caller that cannot list has not learned "this recipe has no
    align images" — it has learned nothing, and the two are different answers
    to the engineer reading the screen. Saying so is the caller's job (the
    office adapter raises SourceUnavailable, the 503 this surface already uses
    for a connect/login/listing failure); an empty return here means the folder
    was read and holds none.
    """
    # Materialized, not normalized: both readers below take full paths and
    # compare basenames themselves, but `listing` may be a one-shot iterable
    # and this reads it twice.
    entries = list(listing)
    points = sorted({
        p_no for p_no in map(align_point_of, entries) if p_no is not None
    })
    return [
        # An unknown point is reported WITHOUT an optic rather than skipped:
        # align_optics refuses to guess (a wrong "SEM" renders OM optics under
        # a SEM heading and reads as ordinary data), but the file is really
        # there and hiding it would be its own kind of lie.
        (p_no, align_optics(p_no) or "", name)
        for p_no in points
        for name in image_variants(align_image_stem(p_no), entries)
    ]


def cond_source(image_file_name: str) -> str:
    """The condition sidecar's name RELATIVE to the raw folder.

    ``'IMMP0001.jpeg' -> '.IMMP0001.jpeg/cond.txt'``. This is the form both
    providers want: the mock has no absolute path at all, and the office
    adapter keys its fetch results by name. It is also what reaches the screen
    as ``SettingBlock.source``, so both providers put the same string there.

    Derived from msr_image's ``cond_path`` rather than spelled out here — the
    hidden-directory layout was proven there (office 확인 2026-07-24), and two
    copies of a rule like this drift.
    """
    return cond_path(image_file_name)


def cond_remote_path(raw: str, image_file_name: str) -> str:
    """The sidecar's ABSOLUTE path, for a caller that needs one."""
    return remote_path(raw, cond_source(image_file_name))


def slot_sources(
    slots: dict[str, str],
    listing: Iterable[str] | None = None,
) -> tuple[str | None, str | None, list[tuple[str, str, str]]]:
    """One parameter's five slot values -> the files they name.

    Returns ``(amp, af_pr, [(slot, image, cond)])``. Lives here rather than in
    either provider because both need exactly this mapping and provider parity
    is the thing the contract tests exist to protect — two hand-kept-in-sync
    copies would be parity by discipline instead of by construction.

    ``listing`` is the raw folder's actual file list when the caller has one
    (the office adapter lists it; the mock synthesizes one). With it, a slot
    expands to EVERY matching file — several per slot on HV-SEM — so ``slot``
    is NOT unique across the returned triples. Without it, or when a slot has
    no match in it, the derived single ``{stem}.jpeg`` stands in, which keeps
    a failed or absent listing exactly as good as the pre-discovery behavior.
    """
    amp = setting_name(slots.get(SETTING_SLOT["amp"]))
    af_pr = setting_name(slots.get(SETTING_SLOT["af_pr"]), pr_to_en=True)
    listed = list(listing) if listing is not None else None
    images: list[tuple[str, str, str]] = []
    for slot in IMAGE_SLOT_KEYS:
        stem = image_stem(slots.get(slot))
        if stem is None:
            continue
        names = image_variants(stem, listed) if listed is not None else []
        if not names:
            names = [f"{stem}.jpeg"]
        images.extend((slot, name, cond_source(name)) for name in names)
    return amp, af_pr, images
