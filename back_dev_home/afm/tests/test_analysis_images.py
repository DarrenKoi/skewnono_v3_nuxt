"""Analysis-image gallery data-layer tests (active provider via data.py)."""

from back_dev_home.afm import data
from back_dev_home.afm.providers import mock


def _row_with(image_type):
    field = mock.IMAGE_TYPE_FIELDS[image_type]
    for row in data.list_afm_files(None):
        names = [n for n in row.get(field, []) if n != "no files"]
        if names:
            return row, names
    raise AssertionError(f"no mock measurement has {image_type} images")


def test_capture_dir_list_populated_for_every_row():
    for row in data.list_afm_files(None):
        assert row["capture_dir_list"]
        assert row["capture_dir_list"][0] != "no files"


def test_list_analysis_images_returns_entries_for_capture():
    row, names = _row_with("capture")
    images = data.list_analysis_images(row["filename"], "capture", row["tool_name"])
    assert [img["name"] for img in images] == names
    assert all("/images/capture/" in img["url"] for img in images)
    assert all(img["url"].startswith("/api/afm/files/") for img in images)


def test_list_analysis_images_unknown_type_is_empty():
    row = data.list_afm_files(None)[0]
    assert data.list_analysis_images(row["filename"], "bogus", row["tool_name"]) == []


def test_list_analysis_images_skips_sentinel():
    for row in data.list_afm_files(None):
        if row["align_dir_list"] == ["no files"]:
            assert data.list_analysis_images(row["filename"], "align", row["tool_name"]) == []
            return


def test_get_analysis_image_svg_valid_for_all_types():
    for image_type in ("align", "tip", "capture", "tiff"):
        row, names = _row_with(image_type)
        svg = data.get_analysis_image_svg(row["filename"], image_type, names[0], row["tool_name"])
        assert isinstance(svg, str)
        assert svg.startswith("<svg")


def test_get_analysis_image_svg_rejects_bad_inputs():
    row, names = _row_with("capture")
    assert data.get_analysis_image_svg(row["filename"], "bogus", names[0], row["tool_name"]) is None
    assert data.get_analysis_image_svg(row["filename"], "capture", "not-real.png", row["tool_name"]) is None
    assert data.get_analysis_image_svg("no-such-file.csv", "capture", names[0], row["tool_name"]) is None


def test_get_analysis_image_svg_is_deterministic():
    row, names = _row_with("capture")
    a = data.get_analysis_image_svg(row["filename"], "capture", names[0], row["tool_name"])
    b = data.get_analysis_image_svg(row["filename"], "capture", names[0], row["tool_name"])
    assert a == b
