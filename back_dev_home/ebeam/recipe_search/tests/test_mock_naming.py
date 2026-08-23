"""The mock's img_* VALUES must follow the office naming convention.

Not cosmetic. ``rawfiles.py`` derives every raw-folder path from these strings,
so a mock emitting ``IMG_ADD1_0001.jpg`` — as this one did until 2026-07-29 —
makes the whole path layer untestable at home and lets a wrong derivation pass
here and fail only at the office. That is the failure mode
``docs/datatables/hitachi/recipe_idp.txt`` warns about in its header, reached through
values instead of column names.
"""

import random
import re

from back_dev_home.ebeam.recipe_search import rawfiles
from back_dev_home.ebeam.recipe_search.providers import mock


PREFIX = {
    "img_add1": "IMMP",
    "img_add2": "PRMP",
    "img_meas1": "IMMS",
    "img_meas2": "PRMS",
    "image_add3": "I2MP",
}


def _rows(seed: int = 3):
    return mock.generate_idp_image_info(num_records=40, rng=random.Random(seed))


def test_every_slot_is_prefix_plus_four_digits_or_the_sentinel():
    for row in _rows():
        for column, prefix in PREFIX.items():
            value = row[column]
            assert value == rawfiles.EMPTY_SLOT or re.fullmatch(
                rf"{prefix}\d{{4}}", value
            ), f"{column}={value!r}"


def test_no_slot_carries_a_file_extension():
    """Extensions are added by rawfiles, never stored in the column."""
    for row in _rows():
        for column in PREFIX:
            assert "." not in row[column], f"{column}={row[column]!r}"


def test_the_empty_sentinel_is_actually_exercised():
    """A mock that never emits 'non' leaves the no-file path unreachable at
    home, which is exactly where that path has to be proven."""
    values = [row[column] for row in _rows() for column in PREFIX]
    assert rawfiles.EMPTY_SLOT in values


def test_the_required_slots_are_never_empty():
    """img_add1, img_meas1 and img_meas2 always name a file; only the third
    addressing image and the AF/PR setting are optional."""
    for row in _rows():
        for column in ("img_add1", "img_meas1", "img_meas2"):
            assert row[column] != rawfiles.EMPTY_SLOT, column


def test_slot_values_survive_the_rawfiles_derivation():
    """The point of the whole task: real derivation over mock values."""
    for row in _rows():
        assert rawfiles.setting_name(row["img_meas2"]) == row["img_meas2"]
        if row["img_add2"] != rawfiles.EMPTY_SLOT:
            assert rawfiles.setting_name(
                row["img_add2"], pr_to_en=True
            ) == f"EN{row['img_add2'][2:]}"
        assert rawfiles.image_name(row["img_add1"]) == f"{row['img_add1']}.jpeg"


def test_generation_is_stable_for_a_given_seed():
    first = mock.generate_idp_image_info(num_records=5, rng=random.Random(7))
    second = mock.generate_idp_image_info(num_records=5, rng=random.Random(7))
    assert first == second
