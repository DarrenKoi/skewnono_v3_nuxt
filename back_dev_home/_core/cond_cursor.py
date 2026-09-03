"""The ``!Cursor_info`` line of a Hitachi ``cond.txt`` image sidecar.

Every tool image (recipe align key, measurement image) carries a hidden
``.<image>/cond.txt``. Besides the beam settings the screen already lists,
one line records WHERE the tool's algorithm put its marks, in a coordinate
frame ten times the image (user-confirmed 2026-09-03, from the
auto_recipe_creator align work):

    Pixel         512,512
    !Cursor_info  a,b,c,d,cx,cy,left,top,right,bottom[,...]

* ``[4],[5]`` — the crosshair (the align / measurement point). Both ``-1``
  means the tool drew none; on a failed align that absence is the signal.
* ``[6..9]`` — the white box the recipe drew around its unique area.
  ``[8],[9]`` at ``-1`` means no box.
* The numbers are in a ``Pixel × 10`` oversample frame: image px = value / 10.
  So ``2097,2561`` on a ``512,512`` image is ``(209.7, 256.1)``.

The key is spelled ``!Cursor_inf`` on some tools and ``!Cursor_info`` on
others (user-confirmed), so it is matched by prefix. What ``[0..3]`` mean and
whether the line appears on every image kind are OFFICE-VERIFY.

This is the ONE parser. Both providers of every image-bearing response attach
the result as ``marks`` (fractions of the image, 0..1), so the browser draws
and the cleaner erases from the same numbers and nothing downstream knows
about Pixel, the ×10, or the token layout. When the office corrects any of
those, this file is the only place that changes.
"""

from collections.abc import Iterable, Mapping
from typing import TypedDict

OVERSAMPLE = 10

_CROSSHAIR_IDX = (4, 5)
_BOX_IDX = (6, 7, 8, 9)


class CursorMarks(TypedDict):
    """The tool's marks as FRACTIONS of the image, plus the Pixel size they
    were derived from (the overlay's viewBox aspect)."""

    pixel: list[int]                # [width, height]
    crosshair: list[float] | None   # [x, y]
    box: list[float] | None         # [left, top, right, bottom]


def is_cursor_key(key: str) -> bool:
    return key.lstrip("!").strip().lower().startswith("cursor_inf")


def _ints(tokens: list[str]) -> list[int | None]:
    out: list[int | None] = []
    for tok in tokens:
        try:
            out.append(int(tok.strip()))
        except ValueError:
            out.append(None)
    return out


def _present(values: list[int | None], idx: tuple[int, ...]) -> bool:
    return max(idx) < len(values) and all(values[i] not in (None, -1) for i in idx)


def cond_lines(text: str) -> dict[str, str]:
    """``key -> raw value`` for every ``key<ws>value`` line; keys keep their spelling."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if parts:
            out[parts[0]] = parts[1].strip() if len(parts) > 1 else ""
    return out


def parse_cursor_info(pixel: str | None, cursor: str | None) -> CursorMarks | None:
    """From the two raw values to fractions. None when either is unusable or
    neither mark is present."""
    if not pixel or not cursor:
        return None
    px = _ints(pixel.split(","))
    if not _present(px, (0, 1)) or px[0] <= 0 or px[1] <= 0:
        return None
    w, h = px[0] * OVERSAMPLE, px[1] * OVERSAMPLE
    values = _ints(cursor.split(","))
    crosshair = box = None
    if _present(values, _CROSSHAIR_IDX):
        crosshair = [values[4] / w, values[5] / h]
    if _present(values, _BOX_IDX):
        box = [values[6] / w, values[7] / h, values[8] / w, values[9] / h]
    if crosshair is None and box is None:
        return None
    return CursorMarks(pixel=[px[0], px[1]], crosshair=crosshair, box=box)


def _from_pairs(pairs: Iterable[tuple[str, str]]) -> CursorMarks | None:
    pixel = cursor = None
    for key, value in pairs:
        if key.strip().lower() == "pixel":
            pixel = value
        elif is_cursor_key(key):
            cursor = value
    return parse_cursor_info(pixel, cursor)


def cursor_info_from_cond(text: str | None) -> CursorMarks | None:
    """Marks straight from a cond.txt body (the office adapters hold the bytes)."""
    return _from_pairs(cond_lines(text).items()) if text else None


def marks_from_rows(rows: Iterable[Mapping[str, str]]) -> CursorMarks | None:
    """Marks from a SettingBlock's ``{key, value}`` rows (the mock builds those)."""
    return _from_pairs((row["key"], row["value"]) for row in rows)


def format_cursor_info(
    crosshair: tuple[int, int] | None,
    box: tuple[int, int, int, int] | None,
) -> str:
    """The inverse, for mocks: raw frame ints -> the ten-token line value.
    ``[0..3]`` are written as 0 (their meaning is OFFICE-VERIFY)."""
    cx, cy = crosshair if crosshair else (-1, -1)
    left, top, right, bottom = box if box else (-1, -1, -1, -1)
    return ",".join(str(v) for v in (0, 0, 0, 0, cx, cy, left, top, right, bottom))
