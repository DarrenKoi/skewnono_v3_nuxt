"""The mock's param-detail obeys the naming rules and the empty sentinel.

These assertions are about DERIVATION, not about values: the fabricated settings
are meaningless, but which file each slot resolves to is an office contract the
office adapter will follow identically.
"""

import random
import re

from back_dev_home.ebeam.recipe_search import rawfiles
from back_dev_home.ebeam.recipe_search.providers import mock


LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}


def _detail(slots):
    item = {"locator": LOCATOR, "parameter": "Para_1", "slots": slots}
    return mock.get_param_detail([item])[0]


def test_amp_comes_from_img_meas2_used_as_is():
    detail = _detail({"img_meas2": "PRMS0007"})
    assert detail["amp"]["source"] == "PRMS0007"
    assert detail["amp"]["rows"], "amp rows must not be empty"
    assert set(detail["amp"]["rows"][0]) == {"key", "value"}


def test_af_pr_comes_from_img_add2_translated_pr_to_en():
    detail = _detail({"img_add2": "PRMP0007"})
    assert detail["af_pr"]["source"] == "ENMP0007"


def test_the_empty_sentinel_produces_no_block_and_no_image():
    detail = _detail({
        "img_meas2": "non", "img_add2": "non", "img_add1": "non",
        "img_meas1": "non", "image_add3": "non",
    })
    assert detail["amp"] is None
    assert detail["af_pr"] is None
    assert detail["images"] == []


def test_only_the_three_image_slots_produce_images():
    """img_add2 and img_meas2 name settings, not images.

    img_meas1 may expand to several stem-suffixed files (the HV-SEM shape,
    2026-08-08), so its pin is membership; the addressing slots never expand
    (user-confirmed 2026-08-08), so theirs is the exact bare-stem file.
    """
    stem_of = {
        "img_add1": "IMMP0001", "image_add3": "I2MP0001", "img_meas1": "IMMS0001",
    }
    detail = _detail({**stem_of, "img_add2": "PRMP0001", "img_meas2": "PRMS0001"})

    assert detail["images"], "the three stems must produce at least one image"
    assert list(dict.fromkeys(i["slot"] for i in detail["images"])) == list(
        rawfiles.IMAGE_SLOT_KEYS
    )
    for image in detail["images"]:
        stem = stem_of[image["slot"]]
        if image["slot"] == "img_meas1":
            assert re.fullmatch(rf"{stem}(-[A-Z]+)?\.jpeg", image["name"]), image["name"]
        else:
            assert image["name"] == f"{stem}.jpeg"


def test_addressing_slots_never_expand_to_suffixed_files():
    """Addressing tops out at its two slots, one file each — no -U/-T/-M/-L
    (user-confirmed 2026-08-08). Sweep enough stems that a reintroduced
    seeded draw on the addressing slots could not slip through."""
    for seq in range(1, 40):
        slots = {"img_add1": f"IMMP{seq:04d}", "image_add3": f"I2MP{seq:04d}"}
        names = [image["name"] for image in _detail(slots)["images"]]
        assert names == [f"IMMP{seq:04d}.jpeg", f"I2MP{seq:04d}.jpeg"]


def test_a_slot_can_expand_to_several_suffixed_files_each_with_its_own_cond():
    """The HV-SEM shape (user-confirmed 2026-08-08): one img_meas1 stem, several
    -U/-T/-M/-L files, one cond sidecar per FILE — so `slot` repeats and the
    cond source follows the suffixed name, not the stem."""
    for seq in range(1, 40):
        stem = f"IMMS{seq:04d}"
        detail = _detail({"img_meas1": stem})
        names = [image["name"] for image in detail["images"]]
        if len(names) <= 1:
            continue
        suffixes = [name[len(stem) + 1:].split(".")[0] for name in names]
        assert all(name.startswith(f"{stem}-") for name in names)
        assert suffixes == list(rawfiles.KNOWN_STEM_SUFFIXES[: len(names)])
        assert [image["slot"] for image in detail["images"]] == ["img_meas1"] * len(names)
        assert [image["cond"]["source"] for image in detail["images"]] == [
            f".{name}/cond.txt" for name in names
        ]
        return
    raise AssertionError("no img_meas1 stem expanded to suffixed files")


def test_the_single_file_cd_sem_shape_still_occurs():
    """Both shapes must exist at home or the CD-SEM path goes untested."""
    for seq in range(1, 40):
        stem = f"IMMS{seq:04d}"
        names = [image["name"] for image in _detail({"img_meas1": stem})["images"]]
        if names == [f"{stem}.jpeg"]:
            return
    raise AssertionError("no img_meas1 stem kept the single bare-stem file")


def test_each_image_carries_its_condition_block():
    detail = _detail({"img_meas1": "IMMS0001"})
    assert detail["images"][0]["cond"]["source"] == ".IMMS0001.jpeg/cond.txt"


def test_each_image_carries_the_stage_label_the_screen_shows():
    detail = _detail({"img_add1": "IMMP0001"})
    assert detail["images"][0]["stage"] == "Addressing 1"


def test_one_response_per_requested_item_in_order():
    items = [
        {"locator": LOCATOR, "parameter": "Para_A", "slots": {"img_meas2": "PRMS0001"}},
        {"locator": LOCATOR, "parameter": "Para_B", "slots": {"img_meas2": "PRMS0002"}},
    ]
    assert [d["parameter"] for d in mock.get_param_detail(items)] == [
        "Para_A", "Para_B",
    ]


def test_different_files_yield_different_settings():
    """Guards a stand-in that ignores its input and returns one constant."""
    first = _detail({"img_meas2": "PRMS0001"})["amp"]["rows"]
    second = _detail({"img_meas2": "PRMS0002"})["amp"]["rows"]
    assert first != second


def test_param_detail_is_stable_across_calls():
    """Compare is derived from open, so a recipe compared against itself must
    not show differences."""
    slots = {"img_meas2": "PRMS0007", "img_add1": "IMMP0007"}
    assert _detail(slots) == _detail(slots)


def test_align_detail_returns_one_sorted_point_per_unique_p_number():
    align = mock.get_align_detail(LOCATOR, [3, 1, 1, 2])
    assert [point["P_No"] for point in align["points"]] == [1, 2, 3]


def test_align_point_names_the_image_and_the_en_setting():
    point = mock.get_align_detail(LOCATOR, [1])["points"][0]
    assert point["image"] == "IMAP0001.jpeg"
    assert point["setting"]["source"] == "ENAP0001"
    assert point["cond"]["source"] == ".IMAP0001.jpeg/cond.txt"


def test_align_points_past_nine_stay_four_digit_padded():
    point = mock.get_align_detail(LOCATOR, [12])["points"][0]
    assert point["image"] == "IMAP0012.jpeg"
    assert point["setting"]["source"] == "ENAP0012"


def test_recipe_image_returns_bytes_and_a_content_type():
    data, content_type = mock.fetch_recipe_image(LOCATOR, "IMMP0001.jpeg")
    assert isinstance(data, bytes) and data
    assert content_type == "image/svg+xml"


def test_recipe_image_is_stable_and_name_dependent():
    first, _ = mock.fetch_recipe_image(LOCATOR, "IMMP0001.jpeg")
    again, _ = mock.fetch_recipe_image(LOCATOR, "IMMP0001.jpeg")
    other, _ = mock.fetch_recipe_image(LOCATOR, "IMMP0002.jpeg")
    assert first == again
    assert first != other


def test_the_mock_does_not_import_the_office_only_parser():
    """The mock must run on a clean checkout.

    ``office_utils`` is gitignored, so a fresh clone does not have it. The
    office adapter importing it is correct — it only ever runs where the real
    package exists — but the mock is what every home session and CI actually
    run against, and it briefly imported it too: 19 tests failed the moment the
    folder was absent. Asserting on the source keeps that from creeping back
    through a helper that only fails on someone else's machine.
    """
    import ast
    import pathlib

    source = pathlib.Path(mock.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported += [alias.name for alias in node.names]

    offenders = [name for name in imported if name.split(".")[0] == "office_utils"]
    assert not offenders, f"mock.py must not import office_utils: {offenders}"


def test_two_recipes_sharing_a_filename_get_different_settings():
    """Seeded on the recipe as well as the file.

    Slot values repeat across recipes (both have a SEQ 1 row, so both name
    PRMS0001). Seeding on the filename alone would hand two genuinely different
    recipes identical settings, and the compare screen would show no diff where
    the office shows one.
    """
    slots = {"img_meas2": "PRMS0001"}
    first = mock.get_param_detail([{
        "locator": {**LOCATOR, "idp": "IDP_ONE"}, "parameter": "Para_1", "slots": slots,
    }])[0]
    second = mock.get_param_detail([{
        "locator": {**LOCATOR, "idp": "IDP_TWO"}, "parameter": "Para_1", "slots": slots,
    }])[0]

    assert first["amp"]["source"] == second["amp"]["source"] == "PRMS0001"
    assert first["amp"]["rows"] != second["amp"]["rows"]


def test_align_settings_also_vary_by_recipe():
    one = mock.get_align_detail({**LOCATOR, "idp": "IDP_ONE"}, [1])["points"][0]
    two = mock.get_align_detail({**LOCATOR, "idp": "IDP_TWO"}, [1])["points"][0]
    assert one["setting"]["rows"] != two["setting"]["rows"]


# ── align points are optics, not positions (user-confirmed 2026-07-29) ────


def test_generated_align_rows_only_ever_name_point_one_or_two():
    """P.No identifies the optic (1 = OM, 2 = SEM), so it is not a free index.

    A mock drawing P.No from 1..20 made the unknown-optic path the common case
    at home while the office sees it almost never — the screen would then be
    full of 파일 없음 here and full of conditions there.
    """
    rows = mock.generate_wafer_align_info(rng=random.Random(7))
    assert {row["P.No"] for row in rows} <= {1, 2}


def test_align_rows_usually_carry_both_optics_and_sometimes_only_om():
    seen = {
        frozenset(row["P.No"] for row in mock.generate_wafer_align_info(rng=random.Random(seed)))
        for seed in range(40)
    }
    assert frozenset({1, 2}) in seen
    assert frozenset({1}) in seen


def test_the_om_image_condition_is_a_subset_of_the_sem_one():
    """Point 1 and point 2 read the same kind of file through different optics
    and get DIFFERENT KEYS for it (office 확인 2026-07-30): OM carries five
    fields and SEM twelve, because an optical microscope has no beam.

    This used to assert distinct placeholder prefixes (ALIGNOM_/ALIGNSEM_),
    which only proved the mock told the two apart. Now that the real fields are
    known it asserts the office's own distinction, so a point sent to the wrong
    optic is caught by what it CONTAINS rather than by a mock-only label.
    """
    om, sem = mock.get_align_detail(LOCATOR, [1, 2])["points"]
    om_keys = [row["key"] for row in om["cond"]["rows"]]
    sem_keys = [row["key"] for row in sem["cond"]["rows"]]

    assert om_keys == [
        "Magnification", "Chip_coordinate", "Wafer_coordinate", "Field_Size", "Pixel",
        "!Cursor_info",
    ]
    assert set(om_keys) < set(sem_keys)
    assert "Accelerating_voltage" in sem_keys and "Accelerating_voltage" not in om_keys


def test_cursor_info_lives_in_the_pixel_times_ten_frame():
    """``!Cursor_info`` (user-confirmed 2026-09-03) is ten ints in a frame ten
    times ``Pixel``; the screen divides by that to place the crosshair. A mock
    value outside the frame would draw the mark off the image."""
    from back_dev_home._core.cond_cursor import parse_cursor_info

    seen_cross = seen_none = False
    for p_no in (1, 2):
        for idp in range(12):
            locator = {**LOCATOR, "idp": f"{LOCATOR['idp']}_{idp}"}
            rows = {r["key"]: r["value"] for r in mock.get_align_detail(locator, [p_no])["points"][0]["cond"]["rows"]}
            info = parse_cursor_info(rows["Pixel"], rows["!Cursor_info"])
            assert info is not None and info.box is not None
            assert all(0.0 <= v <= 1.0 for v in info.box)
            if info.crosshair is None:
                seen_none = True
            else:
                seen_cross = True
                assert all(0.0 <= v <= 1.0 for v in info.crosshair)
    assert seen_cross and seen_none, "both the marked and the unmarked image kinds must occur"


def test_the_sem_align_condition_matches_the_measurement_one_field_for_field():
    """P.No 2 goes through read_align_image_condition and a measurement image
    through read_meas_image_condition — different functions, but the office
    writes the same twelve keys in both files. Asserted because the two are
    generated from one vocabulary here, and a future edit that forks them would
    otherwise pass."""
    sem_align = mock.get_align_detail(LOCATOR, [2])["points"][0]["cond"]
    measurement = _detail({"img_meas1": "IMMS0001"})["images"][0]["cond"]

    assert [row["key"] for row in sem_align["rows"]] == [
        row["key"] for row in measurement["rows"]
    ]


def test_condition_values_are_strings_carrying_their_own_units():
    """Nothing downstream may parse these as numbers: the unit lives inside the
    value, and the unitless ones are strings anyway (office 확인 2026-07-30)."""
    rows = {
        row["key"]: row["value"]
        for row in _detail({"img_meas1": "IMMS0001"})["images"][0]["cond"]["rows"]
    }

    assert rows["Accelerating_voltage"].endswith(" V")
    assert rows["Probe_current"].endswith(" pA")
    assert rows["Image_rotation"].endswith(" deg")
    assert rows["Magnification"].isdigit()          # str, not int
    assert all(isinstance(value, str) for value in rows.values())


def test_field_size_never_contradicts_magnification():
    """Guards the MOCK's internal consistency, not a documented office rule.

    One SEM sample read 4.499 um at 30000x and the office cannot confirm the
    relationship for now (2026-07-30), so it is deferred rather than
    established. The product stays because the alternative — drawing the two
    independently — asserts they are UNRELATED, equally unverified and worse:
    the screen would show a field size contradicting its own magnification.
    The office adapter neither knows nor uses this.
    """
    for slot in ("IMMS0001", "IMMS0002", "IMMS0009"):
        rows = {
            row["key"]: row["value"]
            for row in _detail({"img_meas1": slot})["images"][0]["cond"]["rows"]
        }
        magnification = int(rows["Magnification"])
        side = float(rows["Field_Size"].split(" um")[0])
        # Tolerance rather than equality: the office writes field size to THREE
        # decimals ('4.499 um'), so the product it implies is only good to
        # ±0.0005 um — 50 um·x at 100000x. Demanding exactness here would be
        # asserting a precision the real file does not carry.
        assert abs(side * magnification - 134_970) <= magnification * 0.0005


def test_amp_carries_the_measurement_definition_fields():
    """PRMS… says how the parameter is measured off the image, where cond.txt
    says how the image was taken (office 확인 2026-07-30)."""
    rows = {row["key"]: row["value"] for row in _detail({"img_meas2": "PRMS0001"})["amp"]["rows"]}

    assert rows["Measurement"] == "Width"
    assert rows["Kind"] == "Multi_Point"
    # No unit, unlike every dimensioned value in cond.txt — whether a value
    # carries its unit is per-file, so nothing may assume it either way.
    assert " nm" not in rows["Design_Value"]
    assert float(rows["Design_Value"]) > 0


def test_amp_pair_fields_hold_one_setting_per_edge():
    """A width measurement has two edges and each takes its own setting, joined
    with the same ', ' cond.txt uses for coordinates."""
    rows = {row["key"]: row["value"] for row in _detail({"img_meas2": "PRMS0001"})["amp"]["rows"]}

    for key in ("Threshold", "Edge_Number", "Base_Line_Start_Point", "Base_Line_Area"):
        assert len(rows[key].split(", ")) == 2, key
    assert rows["Edge_Search_Direct."] == "Normal, Normal"


def test_amp_keys_with_no_confirmed_value_are_visibly_synthetic():
    """Six keys arrived named but valueless. Emitting a plausible value there
    would repeat the AmpRow mistake one layer down — right key, invented data —
    so they render as obvious placeholders until a real sample turns up."""
    rows = {row["key"]: row["value"] for row in _detail({"img_meas2": "PRMS0001"})["amp"]["rows"]}

    for key in ("Search_Area", "Inspect_Area", "Smoothing",
                "Differential", "Sum_Line_Point", "Target"):
        assert re.fullmatch(r"[A-F][0-9A-F]{3}", rows[key]), (key, rows[key])


def test_amp_reproduces_the_office_key_spellings_including_their_typos():
    """'Edge_Search_Direct.' ends in a period and 'Base_Line_Start_Point' reads
    as a misspelt "Point". Both are contract keys; correcting either here would
    make home and office disagree about a key name."""
    keys = [row["key"] for row in _detail({"img_meas2": "PRMS0001"})["amp"]["rows"]]

    assert "Edge_Search_Direct." in keys
    assert "Base_Line_Start_Point" in keys


def test_af_pr_rows_are_grouped_into_the_office_section_names():
    """ENMP is the one reader returning a dict OF dicts (office 확인 2026-07-30).
    The groups are real; the keys inside them are still placeholders."""
    sections: set[str] = set()
    for seq in range(1, 30):
        block = _detail({"img_add2": f"PRMP{seq:04d}"})["af_pr"]
        sections |= {row["section"] for row in block["rows"]}

    assert sections <= {
        "sequence_addressing", "sequence_measurement",
        "measurement_pattern_recognition", "measurement_focusing",
        "addressing_auto_focus1", "addressing_pattern_recognition1",
        "addressing_auto_focus2", "addressing_pattern_recognition2",
    }
    # The measurement half runs whatever the addressing choice is.
    assert {"sequence_measurement", "measurement_pattern_recognition",
            "measurement_focusing"} <= sections


def _afpr_by_section(seq: int) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in _detail({"img_add2": f"PRMP{seq:04d}"})["af_pr"]["rows"]:
        grouped.setdefault(row["section"], []).append(row["key"])
    return grouped


def test_af_pr_groups_carry_the_office_key_names():
    """Keys within the groups, not just the group names (office 확인 2026-07-30).

    These are expected to change as the office parser is refined — that costs
    one edit to _AFPR_SECTION_KEYS, because nothing keys off these strings in
    code and the contract is open key/value.
    """
    for seq in range(1, 40):
        grouped = _afpr_by_section(seq)
        if "measurement_focusing" not in grouped:
            continue
        assert grouped["measurement_focusing"] == [
            "Wait(s)", "Offset(LSB)", "Method",
            "Relative Position X(um)", "Relative Position Y(um)", "Mag",
        ]
        assert grouped["sequence_measurement"] == [
            "Focusing", "Pattern Recognition", "Measurement Execution", "Image Save",
        ]
        return
    raise AssertionError("no parameter produced a measurement group")


def test_the_two_addressing_passes_carry_identical_keys():
    """"addressing_auto_focus2 is likewise as 1" — asserted rather than assumed,
    because the mock shares one tuple and a later edit could fork them."""
    for seq in range(1, 60):
        grouped = _afpr_by_section(seq)
        if "addressing_auto_focus2" not in grouped:
            continue
        assert grouped["addressing_auto_focus1"] == grouped["addressing_auto_focus2"]
        assert grouped["addressing_pattern_recognition1"] == \
            grouped["addressing_pattern_recognition2"]
        return
    raise AssertionError("no parameter ran two addressing passes")


def test_one_key_name_recurs_across_groups_and_files():
    """'Acceptance' is in three ENMP groups AND in ENAP — the concrete reason a
    row's identity has to be (section, key) rather than key."""
    for seq in range(1, 60):
        grouped = _afpr_by_section(seq)
        holders = [s for s, keys in grouped.items() if "Acceptance" in keys]
        if len(holders) < 2:
            continue
        assert len(holders) >= 2
        break
    else:
        raise AssertionError("never saw Acceptance in two groups at once")

    enap = mock.get_align_detail(LOCATOR, [1])["points"][0]["setting"]
    assert "Acceptance" in [row["key"] for row in enap["rows"]]


def test_only_the_seen_af_pr_group_carries_real_values():
    """measurement_focusing's values were read (office 확인 2026-07-30); every
    other group's are still unseen and render as obvious placeholders.

    Inferring a format from a key name ('Wait(s)' is surely a number) is the
    reasoning that produced AmpRow's sixteen invented fields — and for the one
    group we HAVE seen, the surprise was the dtype rather than the magnitude.
    """
    for seq in range(1, 40):
        rows = _detail({"img_add2": f"PRMP{seq:04d}"})["af_pr"]["rows"]
        focusing = {r["key"]: r["value"] for r in rows
                    if r["section"] == "measurement_focusing"}
        if not focusing:
            continue

        assert focusing["Method"] == "Fast2"
        # float in the reader, stringified by the adapter — '2.0', not '2'.
        assert re.fullmatch(r"-?\d+\.\d", focusing["Relative Position X(um)"])
        assert re.fullmatch(r"\d+\.\d", focusing["Wait(s)"])
        # '0', not a magnification: a sentinel for "same as the measurement".
        # Guessed as '30000'/'50.0K' before it was read — not merely the wrong
        # number, but not a magnitude on that scale at all.
        assert focusing["Mag"] == "0"
        assert focusing["Offset(LSB)"] == "0"

        # The sequence_* groups are stage lists with no physical unit anywhere,
        # so the dtype rule types them all str and nothing predicts their
        # values — 'ON'/'OFF', 'Yes'/'No' and an order number would all render
        # differently. Entirely placeholders.
        sequences = [r for r in rows if r["section"].startswith("sequence_")]
        assert sequences
        assert all(re.fullmatch(r"[A-F][0-9A-F]{3}", r["value"]) for r in sequences)
        return
    raise AssertionError("no parameter produced measurement_focusing")


def test_every_physical_unit_key_renders_as_a_float():
    """The INFERRED dtype rule (2026-07-30), applied across all eight groups.

    Fourteen confirmed types split on one signal: a key naming a PHYSICAL unit
    in parentheses is float, everything else is str. Offset(LSB) is what makes
    it about physical units rather than parentheses — LSB is a counted digital
    quantum and comes back as str.

    Asserted so a later edit cannot type one group's Wait(s) differently from
    another's, which is the drift this rule exists to prevent.
    """
    seen: set[str] = set()
    for seq in range(1, 60):
        for row in _detail({"img_add2": f"PRMP{seq:04d}"})["af_pr"]["rows"]:
            key, value = row["key"], row["value"]
            if key.endswith(("(s)", "(um)")):
                assert re.fullmatch(r"-?\d+\.\d", value), (row["section"], key, value)
                seen.add(key)
            elif key.endswith("(LSB)"):
                # A parenthesised unit that is NOT physical, and not a float.
                assert not re.fullmatch(r"-?\d+\.\d", value), (key, value)

    assert {"Wait(s)", "Relative Position X(um)", "Offset(um)"} <= seen


def test_the_auto_focus_groups_know_their_types_but_not_all_their_values():
    """addressing_auto_focus's eight TYPES are known and Method's value is
    (office 확인 2026-07-30). float is a complete format — only the magnitude is
    open — so those render float-shaped. `str` describes nothing on its own: in
    this one file it has meant '0', 'Fast2' and '50, 50', so str-typed keys
    whose value is unread stay placeholders.
    """
    for seq in range(1, 60):
        rows = {
            r["key"]: r["value"]
            for r in _detail({"img_add2": f"PRMP{seq:04d}"})["af_pr"]["rows"]
            if r["section"] == "addressing_auto_focus1"
        }
        if not rows:
            continue

        assert rows["Method"] == "Fast2"
        assert re.fullmatch(r"\d+\.\d", rows["Wait(s)"])
        assert re.fullmatch(r"-?\d+\.\d", rows["Relative Position X(um)"])
        for key in ("Offset(LSB)", "Mag", "Threshold", "Charging Voltage"):
            assert re.fullmatch(r"[A-F][0-9A-F]{3}", rows[key]), key
        return
    raise AssertionError("no parameter ran an addressing pass")


def test_one_group_expresses_zero_as_both_a_float_and_a_string():
    """Wait(s) is float 0.0 and Offset(LSB) is str '0' — the same idea, two
    dtypes, in one group (office 확인 2026-07-30). The dtypes are not driven by
    meaning, so they can only be read, never reasoned about."""
    for seq in range(1, 40):
        rows = {
            r["key"]: r["value"]
            for r in _detail({"img_add2": f"PRMP{seq:04d}"})["af_pr"]["rows"]
            if r["section"] == "measurement_focusing"
        }
        if not rows:
            continue
        assert "." in rows["Wait(s)"]          # float-shaped
        assert "." not in rows["Offset(LSB)"]  # str, bare
        return
    raise AssertionError("no parameter produced measurement_focusing")


def test_af_pr_method_does_not_borrow_the_amp_vocabulary():
    """'Method' is 'Fast2' in ENMP and 'Linear' in AMP — same key name, two
    files, two domains. A value is never carried across from another file."""
    amp = {r["key"]: r["value"] for r in _detail({"img_meas2": "PRMS0001"})["amp"]["rows"]}
    assert amp["Method"] == "Linear"

    for seq in range(1, 40):
        rows = _detail({"img_add2": f"PRMP{seq:04d}"})["af_pr"]["rows"]
        focusing = [r for r in rows if r["section"] == "measurement_focusing"]
        if not focusing:
            continue
        assert {r["value"] for r in focusing if r["key"] == "Method"} == {"Fast2"}
        return
    raise AssertionError("no parameter produced measurement_focusing")


def test_enmp_puts_its_units_in_the_key_name():
    """A THIRD unit convention: cond.txt puts the unit in the value ('500 V'),
    AMP omits it ('266.1'), ENMP puts it in the key. Nothing may assume one."""
    keys = {row["key"] for row in _detail({"img_add2": "PRMP0001"})["af_pr"]["rows"]}

    assert any(key.endswith("(s)") for key in keys)
    assert any(key.endswith("(um)") for key in keys)


def test_af_pr_addressing_groups_appear_in_pass_order():
    """Addressing runs none, once or twice, and pass 2's groups can never show
    up without pass 1's — otherwise the screen implies a second pass that the
    basic sequence never ran."""
    for seq in range(1, 40):
        sections = {
            row["section"]
            for row in _detail({"img_add2": f"PRMP{seq:04d}"})["af_pr"]["rows"]
        }
        if "addressing_auto_focus2" in sections:
            assert "addressing_auto_focus1" in sections, seq
            assert "sequence_addressing" in sections, seq


def test_only_af_pr_carries_sections():
    """The other four readers are flat, so their rows must not grow a section —
    that is what keeps their tables rendering exactly as before."""
    detail = _detail({"img_meas2": "PRMS0001", "img_meas1": "IMMS0001"})

    assert all("section" not in row for row in detail["amp"]["rows"])
    assert all("section" not in row for row in detail["images"][0]["cond"]["rows"])


def test_addressing_none_drops_every_addressing_group():
    """With addressing = none the addressing settings are simply absent from
    the parsed result (user-confirmed 2026-07-30) — including
    sequence_addressing, which was inferred until then."""
    for seq in range(1, 60):
        grouped = _afpr_by_section(seq)
        if any(s.startswith("addressing_") for s in grouped):
            continue
        assert "sequence_addressing" not in grouped
        assert set(grouped) == {
            "sequence_measurement", "measurement_pattern_recognition",
            "measurement_focusing",
        }
        return
    raise AssertionError("no parameter ran zero addressing passes")


def test_the_om_field_size_key_is_present_but_empty():
    """The OM sample has the key with NO value (user-confirmed 2026-07-30).

    Until then the mock derived it from the SEM Magnification x Field_Size
    constant and printed '1297.788 um' as though it had been read — a
    cross-optic relationship nobody has observed.
    """
    om, sem = mock.get_align_detail(LOCATOR, [1, 2])["points"]
    om_rows = {row["key"]: row["value"] for row in om["cond"]["rows"]}
    sem_rows = {row["key"]: row["value"] for row in sem["cond"]["rows"]}

    assert "Field_Size" in om_rows
    assert om_rows["Field_Size"] == ""
    assert sem_rows["Field_Size"].endswith(" um")


def test_align_setting_carries_the_two_enap_fields():
    """get_align_beam_pr_conditions returns {'OM': ..., 'SEM': ...} and both
    optics carry the same two keys (office 확인 2026-07-30)."""
    points = mock.get_align_detail(LOCATOR, [1, 2])["points"]

    for point in points:
        rows = {row["key"]: row["value"] for row in point["setting"]["rows"]}
        assert set(rows) == {"Acceptance", "Auto Focus"}
        assert rows["Acceptance"].isdigit()
        assert rows["Auto Focus"] == "OFF"


def test_an_office_key_contains_a_space():
    """'Auto Focus' is the only confirmed key across all five readers that is
    not underscore-joined, so nothing may assume identifier-shaped keys."""
    rows = mock.get_align_detail(LOCATOR, [1])["points"][0]["setting"]["rows"]

    assert any(" " in row["key"] for row in rows)


def test_paired_values_keep_the_separator_the_tool_wrote():
    """Coordinates use ', ' and Pixel a bare ',' — a real inconsistency in the
    file that the screen shows verbatim rather than tidying up."""
    rows = {
        row["key"]: row["value"]
        for row in _detail({"img_meas1": "IMMS0001"})["images"][0]["cond"]["rows"]
    }

    assert ", " in rows["Chip_coordinate"] and rows["Chip_coordinate"].count(" um") == 2
    assert ", " in rows["Field_Size"]
    assert "," in rows["Pixel"] and ", " not in rows["Pixel"]


def test_a_point_that_is_neither_om_nor_sem_has_no_image_condition():
    """The office cannot call the reader without knowing the optic, so it
    renders 파일 없음; the mock has to agree or home and office disagree about
    what an unexpected align point looks like."""
    point = mock.get_align_detail(LOCATOR, [3])["points"][0]
    assert point["cond"] is None
    assert point["setting"] is not None
