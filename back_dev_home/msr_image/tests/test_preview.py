"""TIFF→WebP preview conversion (?preview=1) — msr_image/preview.py.

Conversion is by CONTENT sniff, not by name, so real TIFF bytes are built
here with Pillow and pushed through the real converter — including the 16-bit
grayscale shape SEM tools write, where a naive 8-bit cast renders near-black.

Run from repo root:  .venv/bin/python -m pytest back_dev_home/msr_image
"""

from io import BytesIO

import pytest
from PIL import Image

from back_dev_home.msr_image import preview
from back_dev_home.msr_image.contracts import FetchedImage


def _tiff_bytes(mode: str, extrema: tuple[int, int]) -> bytes:
    """A small gradient TIFF spanning ``extrema`` in ``mode``."""
    lo, hi = extrema
    im = Image.new(mode, (32, 32))
    im.putdata([lo + (hi - lo) * (i % 32) // 31 for i in range(32 * 32)])
    out = BytesIO()
    im.save(out, "TIFF")
    return out.getvalue()


def _decode(data: bytes) -> Image.Image:
    im = Image.open(BytesIO(data))
    im.load()
    return im


def test_8bit_tiff_converts_to_webp_and_keeps_cond():
    fetched = FetchedImage(_tiff_bytes("L", (0, 255)), "image/tiff", "mag=30000")
    out = preview.to_preview(fetched)

    assert out.content_type == "image/webp"
    assert out.data[:4] == b"RIFF" and out.data[8:12] == b"WEBP"
    assert out.cond == "mag=30000", "the cond sidecar must survive conversion"


def test_16bit_tiff_is_stretched_not_cast():
    """SEM TIFFs are often 16-bit. A plain 8-bit cast of values living in
    [1000, 5000] renders near-black (max ≈ 19); the percentile stretch must
    spread them across the visible range instead."""
    fetched = FetchedImage(_tiff_bytes("I;16", (1000, 5000)), "image/tiff", None)
    out = preview.to_preview(fetched)

    assert out.content_type == "image/webp"
    decoded = _decode(out.data).convert("L")
    lo, hi = decoded.getextrema()
    assert lo < 30, f"stretched floor should be near black, got {lo}"
    assert hi > 220, f"stretched ceiling should be near white, got {hi}"


def test_flat_16bit_frame_does_not_divide_by_zero():
    fetched = FetchedImage(_tiff_bytes("I;16", (777, 777)), "image/tiff", None)
    out = preview.to_preview(fetched)
    assert out.content_type == "image/webp"


def test_non_tiff_bytes_pass_through_untouched():
    """A JPEG asked for with preview=1 is already renderable — byte-identical
    passthrough, so the flag is always safe to send."""
    buf = BytesIO()
    Image.new("L", (8, 8)).save(buf, "JPEG")
    fetched = FetchedImage(buf.getvalue(), "image/jpeg", None)
    assert preview.to_preview(fetched) is fetched


def test_mock_svg_labeled_as_tiff_is_relabeled():
    """The home mock serves an SVG placeholder under image/tiff so the
    download-fallback path stays reachable without preview. With preview the
    honest content type is what the bytes are — which is what lets the
    frontend's inline-preview path run offline."""
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    out = preview.to_preview(FetchedImage(svg, "image/tiff", "mag=1"))
    assert out.content_type == "image/svg+xml"
    assert out.data == svg
    assert out.cond == "mag=1"


@pytest.mark.filterwarnings("ignore:Corrupt EXIF data")
def test_corrupt_tiff_degrades_to_the_original_bytes():
    """TIFF magic + garbage body: conversion fails, the original is served,
    and the frontend's <img> error state (with the download link) takes over.
    Never a 500 for one broken file."""
    corrupt = b"II*\x00" + b"\xde\xad\xbe\xef" * 8
    fetched = FetchedImage(corrupt, "image/tiff", None)
    assert preview.to_preview(fetched) is fetched


def test_rgb_and_palette_modes_convert():
    for mode in ("RGB", "P"):
        im = Image.new(mode, (8, 8))
        buf = BytesIO()
        im.save(buf, "TIFF")
        out = preview.to_preview(FetchedImage(buf.getvalue(), "image/tiff", None))
        assert out.content_type == "image/webp", mode
