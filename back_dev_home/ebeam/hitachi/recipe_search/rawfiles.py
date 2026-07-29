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
    IMAP0001.jpeg          P.No = 1    align image
    ENAP0001               P.No = 1    align setting

Every value is ``{kind}{stage}{NNNN}`` — ``IM``/``I2`` name images, ``PR`` names
a setting key the tool wrote, ``EN`` names the condition file that key resolves
to, and the stage is ``MP`` (addressing), ``MS`` (measurement) or ``AP`` (align).

Schema of record: ``docs/datatables/recipe_idp.txt``. If that file and this one
disagree, that file wins and this one is stale.
"""

from __future__ import annotations

from back_dev_home.msr_image.paths import cond_path

__all__ = [
    "EMPTY_SLOT",
    "IMAGE_SLOT_KEYS",
    "align_names",
    "cond_remote_path",
    "image_name",
    "is_empty",
    "raw_dir",
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


def is_empty(value: str | None) -> bool:
    """Does this slot name no file? Case- and whitespace-insensitive."""
    return not value or value.strip().lower() == EMPTY_SLOT


def raw_dir(class_name: str, idw_stem: str, idp_stem: str) -> str:
    """The raw-recipe folder: the .idp's sibling directory of the same name."""
    return f"{_ROOT}/{class_name}/data/{idw_stem}/{idp_stem}"


def remote_path(raw: str, name: str) -> str:
    return f"{raw}/{name}"


def image_name(value: str | None) -> str | None:
    """``'IMMP0001' -> 'IMMP0001.jpeg'``; an empty slot -> ``None``."""
    if is_empty(value):
        return None
    assert value is not None  # is_empty() already rejected None
    return f"{value.strip()}.jpeg"


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


def align_names(p_no: int) -> tuple[str, str]:
    """``P.No -> (image, setting)``, both zero-padded to four digits.

    The padding is the rule, not the concatenation it looks like: ``"ENAP000" +
    str(p)`` agrees for p < 10 and breaks at p = 10, where it would produce a
    nine-character name in a folder where every name is eight.
    """
    return f"IMAP{p_no:04d}.jpeg", f"ENAP{p_no:04d}"


def cond_remote_path(raw: str, image_file_name: str) -> str:
    """The image's hidden condition sidecar: ``.{image}.jpeg/cond.txt``.

    Delegates to msr_image's ``cond_path`` rather than re-deriving it — the
    layout was proven there (office 확인 2026-07-24) and two copies of a rule
    like this drift.
    """
    return cond_path(remote_path(raw, image_file_name))
