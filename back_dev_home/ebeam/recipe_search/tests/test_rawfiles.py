"""Naming rules for the raw-recipe folder. Pure — these run anywhere.

Every assertion here encodes an office fact from
``docs/datatables/recipe_idp.txt`` — see its "raw recipe folder — AMP / focus /
beam condition" section.
A change to one of them is a change to what the office was observed to do, not a
refactor — so each test is named for the fact it holds rather than the function
it calls.
"""

import pytest

from back_dev_home.ebeam.recipe_search import rawfiles


def test_raw_dir_is_the_idp_sibling_folder():
    assert rawfiles.raw_dir("CLS", "IDW_A", "IDP_B") == (
        "/HITACHI/DEVICE/HD/CLS/data/IDW_A/IDP_B"
    )


def test_image_name_appends_jpeg():
    assert rawfiles.image_name("IMMP0001") == "IMMP0001.jpeg"
    assert rawfiles.image_name("I2MP0000") == "I2MP0000.jpeg"
    assert rawfiles.image_name("IMMS0000") == "IMMS0000.jpeg"


@pytest.mark.parametrize("value", ["non", "NON", "  non  ", "", None])
def test_empty_sentinel_yields_no_file(value):
    """'non' is French, not a truncated 'none'."""
    assert rawfiles.is_empty(value) is True
    assert rawfiles.image_name(value) is None
    assert rawfiles.setting_name(value) is None
    assert rawfiles.setting_name(value, pr_to_en=True) is None


def test_none_string_is_not_the_sentinel():
    """Guards the obvious misreading: 'none' is an ordinary eight-char value."""
    assert rawfiles.is_empty("none") is False
    assert rawfiles.image_name("none") == "none.jpeg"


def test_img_meas2_is_used_as_is():
    assert rawfiles.setting_name("PRMS0000") == "PRMS0000"


def test_img_add2_translates_pr_to_en():
    assert rawfiles.setting_name("PRMP0000", pr_to_en=True) == "ENMP0000"


def test_pr_to_en_only_touches_the_first_two_characters():
    """A value containing a later 'PR' must not have that occurrence rewritten."""
    assert rawfiles.setting_name("PRMPPR01", pr_to_en=True) == "ENMPPR01"


def test_pr_to_en_rejects_a_value_that_does_not_start_with_pr():
    """Translating blindly would fetch a PR file while believing it is an EN
    file. Refusing surfaces the surprise instead of serving wrong settings."""
    assert rawfiles.setting_name("IMMP0001", pr_to_en=True) is None


def test_align_names_pad_to_four_digits():
    assert rawfiles.align_names(1) == ("IMAP0001.jpeg", "ENAP0001")


def test_align_names_stay_eight_characters_past_nine():
    """'ENAP000' + str(p) breaks at p=10; four-digit padding is the rule."""
    assert rawfiles.align_names(12) == ("IMAP0012.jpeg", "ENAP0012")
    assert rawfiles.align_names(100) == ("IMAP0100.jpeg", "ENAP0100")


def test_cond_sidecar_lives_in_a_dot_prefixed_hidden_directory():
    raw = rawfiles.raw_dir("CLS", "IDW_A", "IDP_B")
    assert rawfiles.cond_remote_path(raw, "IMMP0001.jpeg") == (
        "/HITACHI/DEVICE/HD/CLS/data/IDW_A/IDP_B/.IMMP0001.jpeg/cond.txt"
    )


def test_remote_path_joins_without_doubling_the_separator():
    raw = rawfiles.raw_dir("CLS", "IDW_A", "IDP_B")
    assert rawfiles.remote_path(raw, "PRMS0000") == (
        "/HITACHI/DEVICE/HD/CLS/data/IDW_A/IDP_B/PRMS0000"
    )


def test_image_slot_keys_exclude_the_two_setting_only_columns():
    """img_add2 and img_meas2 name settings, not images — and image_add3 does
    name an image despite breaking the img_* naming run."""
    assert rawfiles.IMAGE_SLOT_KEYS == ("img_add1", "image_add3", "img_meas1")


# ── HV-SEM: one slot, several stem-suffixed files (user-confirmed 2026-08-08) ─


def test_image_variants_finds_the_exact_stem_and_its_suffixed_files():
    listing = [
        "IMMS0001.jpeg",          # the CD-SEM shape
        "IMMS0001-U.jpeg",        # the HV-SEM shape ...
        "IMMS0001-L.jpeg",
        "IMMS0001-M.tif",         # ... including a tif-only sub-position
        "IMMS0002.jpeg",          # a different slot's file
        "IMMS00010.jpeg",         # NOT this stem: 'IMMS0001' + '0', no dash
        ".IMMS0001-U.jpeg",       # hidden sidecar dir name, not an image
        "PRMS0001",               # setting file: no image extension
    ]
    assert rawfiles.image_variants("IMMS0001", listing) == [
        "IMMS0001.jpeg", "IMMS0001-U.jpeg", "IMMS0001-M.tif", "IMMS0001-L.jpeg",
    ]


def test_image_variants_orders_known_suffixes_as_reported_then_the_rest():
    """U, T, M, L is the reported order (2026-08-08); an unknown suffix is
    listed after them rather than dropped — matching is open, order is not."""
    listing = [
        "IMMS0001-X.jpeg", "IMMS0001-L.jpeg", "IMMS0001-T.jpeg", "IMMS0001-U.jpeg",
    ]
    assert rawfiles.image_variants("IMMS0001", listing) == [
        "IMMS0001-U.jpeg", "IMMS0001-T.jpeg", "IMMS0001-L.jpeg", "IMMS0001-X.jpeg",
    ]


def test_image_variants_accepts_full_paths_and_returns_basenames():
    listing = ["/HITACHI/DEVICE/HD/CLS/data/IDW_A/IDP_B/IMMS0001-U.jpeg"]
    assert rawfiles.image_variants("IMMS0001", listing) == ["IMMS0001-U.jpeg"]


def test_slot_sources_with_a_listing_expands_each_slot_to_every_file():
    """`slot` repeats across the triples — one entry per FILE, each with its
    own cond sidecar derived from the suffixed name."""
    listing = ["IMMS0001-U.jpeg", "IMMS0001-L.jpeg", "IMMP0001.jpeg"]
    _amp, _af_pr, images = rawfiles.slot_sources(
        {"img_add1": "IMMP0001", "img_meas1": "IMMS0001"}, listing=listing
    )
    assert images == [
        ("img_add1", "IMMP0001.jpeg", ".IMMP0001.jpeg/cond.txt"),
        ("img_meas1", "IMMS0001-U.jpeg", ".IMMS0001-U.jpeg/cond.txt"),
        ("img_meas1", "IMMS0001-L.jpeg", ".IMMS0001-L.jpeg/cond.txt"),
    ]


def test_slot_sources_falls_back_to_the_derived_name_when_unlisted():
    """listing=None (failed listing) and a listed folder with no match both
    degrade to the pre-discovery single {stem}.jpeg plan — never to nothing."""
    expected = [("img_meas1", "IMMS0001.jpeg", ".IMMS0001.jpeg/cond.txt")]
    for listing in (None, [], ["OTHER0001.jpeg"]):
        _amp, _af_pr, images = rawfiles.slot_sources(
            {"img_meas1": "IMMS0001"}, listing=listing
        )
        assert images == expected, f"listing={listing!r}"
