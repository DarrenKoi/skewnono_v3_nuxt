"""The measurement box on param-detail's img_meas1 image (2026-10-29).

The geometry is office_utils.meas_marks' job and is faked here. What this file
guards is the WIRING: which bytes go in, the origin fallback order (ENMP
msr_info -> image-stem VIMMS blob -> centre), that only the measurement image
gets a box, and that a host without the module still answers.
"""

import sys
import types

import pytest

from backend.ebeam.recipe_search.providers import mock
from backend.ebeam.recipe_search.providers import office_example as oe

LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}
SLOTS = {
    "img_add1": "IMMP0001", "img_add2": "PRMP0000", "image_add3": "non",
    "img_meas1": "IMMS0002", "img_meas2": "PRMS0000",
}
MARKS = {"pixel": [1024, 1024], "bars": [(0.4, 0.5, 0.05, 0.3)], "circles": []}


def _fake_office(monkeypatch, files, *, msr=None, vimms=None, with_module=True):
    calls = {}
    reader = types.ModuleType("office_utils.idp_amp_reader")
    reader.read_amp_info = lambda payload: {"Kind": "Multi_Point"}
    reader.read_af_pr_condition = lambda payload: {}
    reader.read_meas_image_condition = lambda payload: {
        "Pixel": "1024,1024", "Field_Size": "4.499 um, 4.499 um",
    }
    monkeypatch.setitem(sys.modules, "office_utils", types.ModuleType("office_utils"))
    monkeypatch.setitem(sys.modules, "office_utils.idp_amp_reader", reader)
    if with_module:
        meas = types.ModuleType("office_utils.meas_marks")
        meas.msr_info_offset = lambda text, pixel: msr
        meas.vimms_mp_offset = lambda blob, pixel: vimms

        def marks_from_amp(amp, pixel, field_um=None, mp_offset=None):
            calls.update(pixel=pixel, field_um=field_um, mp_offset=mp_offset)
            return MARKS
        meas.marks_from_amp = marks_from_amp
        monkeypatch.setitem(sys.modules, "office_utils.meas_marks", meas)
    else:
        monkeypatch.setitem(sys.modules, "office_utils.meas_marks", None)
    monkeypatch.setattr(oe, "_list_raw_dirs", lambda keys: dict.fromkeys(keys))

    def fetch(wanted):
        calls["wanted"] = sorted(next(iter(wanted.values())))
        return {key: {n: b"x" for n in names if n in files} for key, names in wanted.items()}
    monkeypatch.setattr(oe, "_fetch_many", fetch)
    return calls


def _images(monkeypatch, files, **kw):
    calls = _fake_office(monkeypatch, files, **kw)
    detail = oe.get_param_detail([{"locator": LOCATOR, "parameter": "P", "slots": SLOTS}])[0]
    return {img["slot"]: img for img in detail["images"]}, calls


ALL = {"PRMS0000", "ENMP0000", "IMMS0002", ".IMMS0002.jpeg/cond.txt", ".IMMP0001.jpeg/cond.txt"}


@pytest.mark.parametrize("files, msr, vimms, origin, offset", [
    (ALL, (3, 4), (9, 9), "msr", (3, 4)),
    (ALL, None, (9, 9), "vimms", (9, 9)),
    (ALL - {"IMMS0002"}, None, (9, 9), "center", None),
    (ALL - {"ENMP0000"}, (3, 4), None, "center", None),
])
def test_origin_falls_back_msr_then_vimms_then_centre(monkeypatch, files, msr, vimms, origin, offset):
    images, calls = _images(monkeypatch, files, msr=msr, vimms=vimms)
    assert images["img_meas1"]["meas"]["origin"] == origin
    assert calls["mp_offset"] == offset
    assert calls["field_um"] == 4.499
    assert calls["pixel"] == "1024,1024"   # raw, the module converts


def test_only_the_measurement_image_gets_a_box_and_the_blob_rides_the_same_visit(monkeypatch):
    images, calls = _images(monkeypatch, ALL, msr=(1, 1))
    assert images["img_add1"]["meas"] is None
    assert images["img_meas1"]["meas"] == {
        "pixel": [1024, 1024], "bars": [[0.4, 0.5, 0.05, 0.3]], "circles": [], "origin": "msr",
    }
    assert "IMMS0002" in calls["wanted"]


def test_a_host_without_meas_marks_still_answers(monkeypatch):
    images, _ = _images(monkeypatch, ALL, with_module=False)
    assert images["img_meas1"]["meas"] is None
    assert images["img_meas1"]["cond"] is not None


def test_mock_boxes_only_img_meas1_and_never_a_formula():
    items = [
        {"locator": LOCATOR, "parameter": f"Para_{n}", "slots": SLOTS} for n in range(40)
    ]
    seen = set()
    for detail in mock.get_param_detail(items):
        for image in detail["images"]:
            meas = image["meas"]
            if image["slot"] != "img_meas1":
                assert meas is None
                continue
            if meas is None:
                continue
            seen.add("bars" if meas["bars"] else "circles")
            assert meas["origin"] in {"msr", "vimms", "center"}
            for shape in meas["bars"] + meas["circles"]:
                assert all(0 <= v <= 1 for v in shape)
    assert seen == {"bars", "circles"}, "the mock must exercise both render paths"
    formula = mock._formula_parameter_name("IDP_B")
    detail = mock.get_param_detail([{"locator": LOCATOR, "parameter": formula, "slots": SLOTS}])[0]
    assert all(image["meas"] is None for image in detail["images"])


def test_mock_amp_names_the_branch_in_its_own_field():
    # office 확인 2026-10-29: Kind / Object / Measurement each carry some branches.
    for n in range(40):
        param = f"Para_{n}"
        kind = mock._meas_kind("IDP_B", param)
        rows = {r["key"]: r["value"] for r in mock._amp_block("PRMS0000", "IDP_B", param)["rows"]}
        assert rows[mock._MEAS_KIND_FIELD[kind]] == kind
