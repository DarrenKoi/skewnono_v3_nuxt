"""``!Cursor_info`` parsing — backend/_core/cond_cursor.py.

Run from repo root:  .venv/bin/python -m pytest backend/_core -q
"""

from backend._core.cond_cursor import (
    cursor_info_from_cond,
    format_cursor_info,
    marks_from_rows,
    parse_cursor_info,
)

# The worked example from the auto_recipe_creator align work: (2097, 2561) on
# a 512 image is (209.7, 256.1) px, i.e. the fractions below.
_COND = "Pixel\t512,512\n!Cursor_info\t0,0,0,0,2097,2561,1600,1600,3520,3520\n"


def test_fractions_divide_by_the_5120_frame():
    assert cursor_info_from_cond(_COND) == {
        "pixel": [512, 512],
        "crosshair": [2097 / 5120, 2561 / 5120],
        "box": [1600 / 5120, 1600 / 5120, 3520 / 5120, 3520 / 5120],
    }


def test_rows_and_text_agree_and_the_key_spelling_varies():
    rows = [{"key": "Magnification", "value": "30000"}, {"key": "Pixel", "value": "512,512"},
            {"key": "!Cursor_inf", "value": "0,0,0,0,2097,2561,1600,1600,3520,3520"}]
    assert marks_from_rows(rows) == cursor_info_from_cond(_COND)
    assert marks_from_rows(rows[:2]) is None


def test_minus_one_means_no_mark():
    no_cross = parse_cursor_info("512,512", "0,0,0,0,-1,-1,100,100,200,200")
    assert no_cross["crosshair"] is None and no_cross["box"] is not None
    no_box = parse_cursor_info("512,512", "0,0,0,0,2560,2560,-1,-1,-1,-1")
    assert no_box["box"] is None and no_box["crosshair"] == [0.5, 0.5]
    assert parse_cursor_info("512,512", "0,0,0,0,-1,-1,-1,-1,-1,-1") is None


def test_unusable_input_is_none_not_an_error():
    assert parse_cursor_info(None, "0,0,0,0,1,1,1,1,1,1") is None
    assert parse_cursor_info("512,512", None) is None
    assert parse_cursor_info("0,512", "0,0,0,0,1,1,1,1,1,1") is None
    assert parse_cursor_info("512,512", "1,2,3") is None  # too short
    assert parse_cursor_info("512,512", "a,b,c,d,e,f,g,h,i,j") is None
    assert cursor_info_from_cond(None) is None
    assert cursor_info_from_cond("mag=30000\n") is None


def test_the_frame_is_5120_whatever_the_pixel():
    # office 확인 2026-10-29: the divisor is a fixed 5120, not Pixel x 10. The
    # two agree only at 512 px — a 1024 image read as x10 drew at half scale.
    marks = parse_cursor_info("1024,1024", "0,0,0,0,2560,2560,1280,1280,3840,3840")
    assert marks["pixel"] == [1024, 1024]
    assert marks["crosshair"] == [0.5, 0.5]
    assert marks["box"] == [0.25, 0.25, 0.75, 0.75]


def test_rectangular_pixel_still_uses_5120_on_each_axis():
    # OFFICE-VERIFY: "5120 fixed" was answered for square images.
    assert parse_cursor_info("1024,512", "0,0,0,0,2560,2560,-1,-1,-1,-1")["crosshair"] == [0.5, 0.5]


def test_format_is_the_inverse_of_parse():
    line = format_cursor_info((2097, 2561), (1600, 1600, 3520, 3520))
    assert line == "0,0,0,0,2097,2561,1600,1600,3520,3520"
    assert parse_cursor_info("512,512", line) == cursor_info_from_cond(_COND)
    assert format_cursor_info(None, (1, 2, 3, 4)) == "0,0,0,0,-1,-1,1,2,3,4"
