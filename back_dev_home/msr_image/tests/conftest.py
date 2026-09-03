"""Shared fixtures for the msr_image suite."""

from io import BytesIO

import pytest
from PIL import Image

# A 64x64 cond.txt placing the crosshair at (32, 16) px — 320,160 in the x10 frame.
CROSSHAIR_COND = "Pixel\t64,64\n!Cursor_info\t0,0,0,0,320,160,-1,-1,-1,-1\n"


@pytest.fixture
def crosshair_jpeg() -> bytes:
    """A flat grey 64x64 JPEG with a white crosshair drawn at (32, 16)."""
    im = Image.new("L", (64, 64), 100)
    for i in range(64):
        im.putpixel((32, i), 255)
        im.putpixel((i, 16), 255)
    out = BytesIO()
    im.save(out, "JPEG", quality=95)
    return out.getvalue()
