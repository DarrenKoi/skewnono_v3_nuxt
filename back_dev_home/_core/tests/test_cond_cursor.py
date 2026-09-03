"""``!Cursor_info`` parsing — back_dev_home/_core/cond_cursor.py.

Run from repo root:  .venv/bin/python -m pytest back_dev_home/_core -q
"""

from back_dev_home._core.cond_cursor import (
    cursor_info_from_cond,
    cursor_value,
    parse_cursor_info,
)

# The worked example from docs/align-crosshair: (2097, 2561) on a 512 image
# is (209.7, 256.1) px, i.e. the fractions below.
_COND = "Pixel\t512,512\n!Cursor_info\t0,0,0,0,2097,2561,1600,1600,3520,3520\n"


def test_fractions_divide_by_pixel_times_ten():
    info = cursor_info_from_cond(_COND)
    assert info is not None
    assert info.pixel == (512, 512)
    assert info.crosshair == (2097 / 5120, 2561 / 5120)
    assert info.box == (1600 / 5120, 1600 / 5120, 3520 / 5120, 3520 / 5120)


def test_key_spelling_varies_between_tools():
    assert cursor_value("!Cursor_inf 1,2,3,4,5,6,7,8,9,10") == "1,2,3,4,5,6,7,8,9,10"
    assert cursor_value("Magnification 30000") is None


def test_minus_one_means_no_mark():
    no_cross = parse_cursor_info("512,512", "0,0,0,0,-1,-1,100,100,200,200")
    assert no_cross is not None and no_cross.crosshair is None and no_cross.box is not None
    no_box = parse_cursor_info("512,512", "0,0,0,0,2560,2560,-1,-1,-1,-1")
    assert no_box is not None and no_box.box is None and no_box.crosshair == (0.5, 0.5)
    assert parse_cursor_info("512,512", "0,0,0,0,-1,-1,-1,-1,-1,-1") is None


def test_unusable_input_is_none_not_an_error():
    assert parse_cursor_info(None, "0,0,0,0,1,1,1,1,1,1") is None
    assert parse_cursor_info("512,512", None) is None
    assert parse_cursor_info("0,512", "0,0,0,0,1,1,1,1,1,1") is None
    assert parse_cursor_info("512,512", "1,2,3") is None  # too short
    assert parse_cursor_info("512,512", "a,b,c,d,e,f,g,h,i,j") is None
    assert cursor_info_from_cond(None) is None
    assert cursor_info_from_cond("mag=30000\n") is None


def test_rectangular_pixel_uses_each_axis():
    info = parse_cursor_info("1024,512", "0,0,0,0,5120,2560,-1,-1,-1,-1")
    assert info is not None and info.crosshair == (0.5, 0.5)
