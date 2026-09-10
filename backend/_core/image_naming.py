"""Image-name facts that more than one feature has to agree on.

A PROTOCOL fact lives here, not a preference: these are things the tools do,
so every backend that reads tool filenames must read them the same way. Three
features had their own copy of the suffix tuple until 2026-08-09 — msr_file's
``_MP_IMAGE_SUFFIXES``, msr_image's ``_STEM_SUFFIXES`` and recipe_search's
``KNOWN_STEM_SUFFIXES``. Nothing breaks when copies disagree; they just
disagree, and recipe_search starts discovering images the other two refuse to
name.
"""

from __future__ import annotations


# The stem suffixes HV-SEM tools append when ONE targeting point is shot as
# several images: IMMS0001-U.jpeg / -T / -M / -L, and the same on MSR result
# images (S04_M0004-01MP-U.jpeg). user-confirmed 2026-08-08.
#
# ORDER IS PART OF THE FACT. The pickle's mp_image_name 01..NN columns list
# them in this order, and consumers rank by it.
#
# The list is OPEN, not a filter: matching code accepts any "-{suffix}" after
# the stem and ranks unknown letters after these, so a fifth suffix appearing
# on a tool is still discovered. Add it here — in one place — once the office
# confirms one, and the mocks and the reader learn it together.
HV_SEM_STEM_SUFFIXES: tuple[str, ...] = ("U", "T", "M", "L")
