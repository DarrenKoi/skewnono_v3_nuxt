"""The mock's param-detail obeys the naming rules and the empty sentinel.

These assertions are about DERIVATION, not about values: the fabricated settings
are meaningless, but which file each slot resolves to is an office contract the
office adapter will follow identically.
"""

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
