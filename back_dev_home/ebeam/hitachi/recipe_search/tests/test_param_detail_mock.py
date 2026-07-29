"""The mock's param-detail obeys the naming rules and the empty sentinel.

These assertions are about DERIVATION, not about values: the fabricated settings
are meaningless, but which file each slot resolves to is an office contract the
office adapter will follow identically.
"""

import random

from back_dev_home.ebeam.hitachi.recipe_search import rawfiles
from back_dev_home.ebeam.hitachi.recipe_search.providers import mock


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
    """img_add2 and img_meas2 name settings, not images."""
    detail = _detail({
        "img_add1": "IMMP0001", "img_add2": "PRMP0001", "image_add3": "I2MP0001",
        "img_meas1": "IMMS0001", "img_meas2": "PRMS0001",
    })
    assert [image["name"] for image in detail["images"]] == [
        "IMMP0001.jpeg", "I2MP0001.jpeg", "IMMS0001.jpeg",
    ]
    assert [image["slot"] for image in detail["images"]] == list(
        rawfiles.IMAGE_SLOT_KEYS
    )


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


def test_the_image_condition_is_fabricated_per_optic():
    """Point 1 and point 2 read the same kind of file through different optics,
    so their blocks must not be interchangeable — mirroring the office, where
    `which` is what read_align_image_condition is told."""
    points = mock.get_align_detail(LOCATOR, [1, 2])["points"]
    keys = [next(iter(row["key"] for row in point["cond"]["rows"])) for point in points]

    assert keys[0].startswith("ALIGNOM_")
    assert keys[1].startswith("ALIGNSEM_")


def test_a_point_that_is_neither_om_nor_sem_has_no_image_condition():
    """The office cannot call the reader without knowing the optic, so it
    renders 파일 없음; the mock has to agree or home and office disagree about
    what an unexpected align point looks like."""
    point = mock.get_align_detail(LOCATOR, [3])["points"][0]
    assert point["cond"] is None
    assert point["setting"] is not None
