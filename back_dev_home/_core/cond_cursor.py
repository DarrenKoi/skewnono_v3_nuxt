"""The ``!Cursor_info`` line of a Hitachi ``cond.txt`` image sidecar.

Every tool image (recipe align key, measurement image) carries a hidden
``.<image>/cond.txt``. Besides the beam settings the screen already lists,
one line records WHERE the tool's algorithm put its marks, in a coordinate
frame ten times the image (user-confirmed 2026-09-03, from the
auto_recipe_creator align work — see docs/align-crosshair/):

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

Only the geometry is parsed here. Fractions of the frame (``x / (Pixel × 10)``)
are what a consumer wants — the browser overlays an SVG whose viewBox is the
Pixel size, and the cleaner works on the decoded image — and the division
happens in ONE place so the ×10 is never applied twice.
"""

from dataclasses import dataclass

OVERSAMPLE = 10

_CROSSHAIR_IDX = (4, 5)
_BOX_IDX = (6, 7, 8, 9)


@dataclass(frozen=True)
class CursorInfo:
    """Marks as FRACTIONS of the image (0..1), so no consumer needs Pixel."""

    pixel: tuple[int, int]
    crosshair: tuple[float, float] | None
    box: tuple[float, float, float, float] | None


def _norm_key(key: str) -> str:
    return key.lstrip("!").strip().lower()


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
    """``key -> raw value`` for every ``key<ws>value`` line, key normalised."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if parts:
            out[_norm_key(parts[0])] = parts[1].strip() if len(parts) > 1 else ""
    return out


def cursor_value(text: str) -> str | None:
    """The raw ``!Cursor_info`` value, whichever spelling the tool used."""
    return next((v for k, v in cond_lines(text).items() if k.startswith("cursor_inf")), None)


def parse_cursor_info(pixel: str | None, cursor: str | None) -> CursorInfo | None:
    """From the two raw values (as strings) to fractions. None when either is unusable."""
    if not pixel or not cursor:
        return None
    px = _ints(pixel.split(","))
    if len(px) < 2 or not px[0] or not px[1] or px[0] <= 0 or px[1] <= 0:
        return None
    w, h = px[0] * OVERSAMPLE, px[1] * OVERSAMPLE
    values = _ints(cursor.split(","))
    crosshair = box = None
    if _present(values, _CROSSHAIR_IDX):
        crosshair = (values[4] / w, values[5] / h)
    if _present(values, _BOX_IDX):
        box = (values[6] / w, values[7] / h, values[8] / w, values[9] / h)
    if crosshair is None and box is None:
        return None
    return CursorInfo((px[0], px[1]), crosshair, box)


def cursor_info_from_cond(text: str | None) -> CursorInfo | None:
    """``parse_cursor_info`` straight from a cond.txt body."""
    if not text:
        return None
    lines = cond_lines(text)
    return parse_cursor_info(lines.get("pixel"), cursor_value(text))
