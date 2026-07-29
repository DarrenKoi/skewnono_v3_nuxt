"""The raw-recipe contract types exist and carry the keys the frontend indexes.

Cheap, but it is the gate that a rename on one side of the wire cannot pass
silently: the frontend reads these keys by string, so a typo here surfaces as an
empty panel rather than an error.
"""

from back_dev_home.ebeam.hitachi.recipe_search import contracts


def test_setting_block_is_open_key_value():
    """Open rows, not fixed columns: the readers' real field names are still
    OFFICE-VERIFY, and an unknown key must render rather than vanish."""
    assert set(contracts.SettingRow.__annotations__) == {"key", "value"}
    assert set(contracts.SettingBlock.__annotations__) == {"source", "rows"}


def test_param_detail_carries_amp_af_pr_and_images():
    assert set(contracts.ParamDetailResponse.__annotations__) == {
        "parameter", "amp", "af_pr", "images",
    }


def test_param_image_names_the_file_the_image_endpoint_takes():
    assert set(contracts.ParamImage.__annotations__) == {
        "slot", "stage", "name", "cond",
    }


def test_align_point_carries_both_the_cond_and_the_en_setting():
    """Two different files per align point: .IMAP0001.jpeg/cond.txt is the beam
    condition, ENAP0001 is the focus / pattern-recognition setting."""
    assert set(contracts.AlignPoint.__annotations__) == {
        "P_No", "image", "cond", "setting",
    }


def test_align_detail_wraps_the_points():
    assert set(contracts.AlignDetailResponse.__annotations__) == {"points"}


def test_locator_carries_the_four_ftp_path_fields():
    assert set(contracts.IdpLocator.__annotations__) == {
        "eqp_ip", "class_name", "idw", "idp",
    }


def test_param_detail_request_item_carries_the_slots_verbatim():
    """The client sends the idp_image_info row's own values; the server must
    never have to re-parse the .idp to recover them."""
    assert set(contracts.ParamDetailRequestItem.__annotations__) == {
        "locator", "parameter", "slots",
    }


def test_every_new_name_is_exported():
    for name in (
        "AlignDetailResponse", "AlignPoint", "IdpLocator",
        "ParamDetailRequestItem", "ParamDetailResponse", "ParamImage",
        "SettingBlock", "SettingRow",
    ):
        assert name in contracts.__all__, name
