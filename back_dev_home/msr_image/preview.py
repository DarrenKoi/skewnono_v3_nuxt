"""Browser-renderable previews for TIFF originals (``?preview=1``).

Chromium cannot decode TIFF in an ``<img>`` or blob URL, so until 2026-08-08
every TIFF rendered as a download-only card. That was tolerable while each
TIFF had a JPEG preview twin on the tool (office 확인 2026-07-24), but HV-SEM
sub-images sometimes exist ONLY as .tif (user-confirmed 2026-08-08) — for
those the card was the only view. This module converts the original bytes to
WebP at serve time so the screen can show the micrograph inline; the 원본
다운로드 link keeps serving the untouched TIFF.

Design constraints, in order:

* CONVERSION IS BY CONTENT, NOT BY NAME. The bytes are sniffed for the TIFF
  magic (``II*\\0`` / ``MM\\0*``); anything else passes through untouched. This
  is what lets one code path serve three worlds: a real office TIFF converts,
  a JPEG asked for with ``preview=1`` is returned as-is, and the home mock's
  SVG placeholder (labeled ``image/tiff`` so the no-preview path stayed
  reachable) is relabeled to the SVG it actually is — which is exactly the
  "converted preview renders inline" experience, exercised offline.
* 16-BIT NORMALIZATION IS A DISPLAY DECISION. SEM TIFFs are often 16-bit
  grayscale; a plain 8-bit cast renders near-black. A 0.5/99.5 percentile
  stretch is applied instead — robust to hot pixels, and honest in the sense
  that it changes CONTRAST only, never geometry. OFFICE-VERIFY: tune against
  a real office TIFF once one is in hand; the percentile pair lives in one
  constant below.
* A FAILED CONVERSION DEGRADES, NEVER ERRORS. Corrupt or exotic TIFFs return
  the original bytes (logged); the frontend's ``<img>`` error state then shows
  이미지 없음 with the download link — the pre-2026-08-08 behavior, scoped to
  the one broken file.
* CONVERTED PER REQUEST, NOT CACHED. The original is already in the image
  cache, so a preview request never re-fetches from the tool; re-encoding a
  micrograph-sized image is milliseconds, and a second cache entry would have
  to mirror the two office retention sweeps (image_cache 7d — see
  project memory) byte-for-byte to stay honest. Revisit only if profiling
  says otherwise.

Pillow is imported lazily so this module (imported by routes.py) never makes
Pillow a boot-time requirement: an office host missing the new dependency
still serves everything except ``preview=1``.
"""

import logging
from io import BytesIO

from back_dev_home._core.cond_cursor import cursor_info_from_cond
from back_dev_home.msr_image.contracts import FetchedImage

_LOG = logging.getLogger(__name__)

_TIFF_MAGICS = (b"II*\x00", b"MM\x00*")

# Percentile stretch for high-bit-depth frames. 0.5/99.5 clips hot/dead pixels
# without flattening real signal — a DISPLAY choice, see the module docstring.
_STRETCH_PERCENTILES = (0.5, 99.5)

_WEBP_QUALITY = 90

# Pillow modes that need normalization before an 8-bit encode. "I;16*" are the
# common SEM cases; "I"/"F" are 32-bit int/float frames some writers emit.
_HIGH_DEPTH_MODES = ("I;16", "I;16B", "I;16L", "I;16N", "I", "F")


def is_tiff_bytes(data: bytes) -> bool:
    return data[:4] in _TIFF_MAGICS


def _looks_like_svg(data: bytes) -> bool:
    head = data[:256].lstrip().lower()
    return head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in head)


def _tiff_to_webp(data: bytes) -> bytes:
    from PIL import Image  # lazy — see module docstring

    import numpy as np

    with Image.open(BytesIO(data)) as im:
        im.load()  # first frame of a multi-page TIFF; sub-pages are not shown
        if im.mode in _HIGH_DEPTH_MODES:
            arr = np.asarray(im, dtype="float64")
            lo, hi = np.percentile(arr, _STRETCH_PERCENTILES)
            if hi <= lo:  # a flat frame stretches to nothing — avoid 0-division
                hi = lo + 1.0
            arr = np.clip((arr - lo) / (hi - lo) * 255.0, 0.0, 255.0)
            im = Image.fromarray(arr.astype("uint8"), "L")
        return _encode_webp(im)


def _encode_webp(im) -> bytes:
    """What a WebP rendition is: L or RGB, one quality."""
    if im.mode not in ("L", "RGB"):
        # palette / RGBA / CMYK and friends — WebP wants L or RGB(A).
        im = im.convert("RGB")
    out = BytesIO()
    im.save(out, "WEBP", quality=_WEBP_QUALITY)
    return out.getvalue()


# Half-width of the band erased around each crosshair line, in px of the
# decoded image. The tool draws a ~1 px core plus JPEG halo; 2 covers both
# without smearing texture (docs/align-crosshair, dilate=1 was optimal there).
_CLEAN_HALF_BAND = 2


def _erase_lines(arr, cx: int, cy: int, half: int = _CLEAN_HALF_BAND):
    """Overwrite the column band at ``cx`` and the row band at ``cy`` with a
    linear blend of the pixels just outside the band, in place. ``arr`` is a
    writable uint8 (H, W[, C]) array.

    ponytail: linear interpolation across a 5 px band, not inpainting. Fine
    for a hairline on a micrograph; switch to cv2.inpaint if a real image
    shows a visible seam.
    """
    import numpy as np

    for axis, centre in ((1, cx), (0, cy)):
        lo, hi = centre - half, centre + half  # inclusive band
        left, right = lo - 1, hi + 1           # the pixels blended between
        if left < 0 or right >= arr.shape[axis]:
            continue  # band touches the border: nothing to blend from
        a = np.take(arr, left, axis=axis).astype("float64")
        b = np.take(arr, right, axis=axis).astype("float64")
        ramp = np.linspace(a, b, right - left + 1, axis=axis)  # endpoints included
        inner = [slice(None)] * arr.ndim
        inner[axis] = slice(1, -1)
        band = [slice(None)] * arr.ndim
        band[axis] = slice(lo, hi + 1)
        arr[tuple(band)] = np.rint(ramp[tuple(inner)]).astype("uint8")
    return arr


def _clean_crosshair(data: bytes, cond: str) -> bytes | None:
    """``data`` with the cond-declared crosshair erased, or None when there is
    no crosshair to erase (or the bytes are not a raster Pillow can open)."""
    marks = cursor_info_from_cond(cond)
    if marks is None or marks["crosshair"] is None:
        return None
    from PIL import Image  # lazy — see module docstring

    import numpy as np

    with Image.open(BytesIO(data)) as im:
        im.load()
        if im.mode not in ("L", "RGB"):
            im = im.convert("RGB")
        w, h = im.size
        # Fractions of the frame, so a resized copy still lands on the line.
        fx, fy = marks["crosshair"]
        arr = _erase_lines(np.array(im), round(fx * w), round(fy * h))
        return _encode_webp(Image.fromarray(arr, im.mode))


def to_clean(fetched: FetchedImage) -> FetchedImage:
    """The rendition with the crosshair erased, when the cond sidecar locates
    one. Starts from ``to_preview`` (a no-op on already-renderable bytes) so a
    TIFF original is normalised before it is touched. Unchanged (never raises)
    when the sidecar names no crosshair, or the bytes are not a raster (the
    mock's SVG).

    Computed per request rather than cached: the source is already the cached
    rendition, and the transform is a numpy blend of ten rows and columns.
    """
    fetched = to_preview(fetched)
    if fetched.cond is None:
        return fetched
    try:
        cleaned = _clean_crosshair(fetched.data, fetched.cond)
    except Exception as exc:  # noqa: BLE001 — degrade to the original bytes
        _LOG.warning("msr_image: crosshair clean failed (%s) — serving original", exc)
        return fetched
    if cleaned is None:
        return fetched
    return FetchedImage(cleaned, "image/webp", fetched.cond)


def wants_preview(raw: str | None) -> bool:
    """Does this ``?preview`` query value ask for the rendition?

    A conservative allowlist: only ``1`` / ``true`` / ``yes`` opt in, and
    anything else — including a missing value, a typo, or a future spelling —
    serves the original bytes. Serving the original is the safe default: it is
    what every caller got before previews existed.

    The rule lives here, next to ``to_preview``, because both route modules
    that accept the flag need the SAME answer. It was written out twice
    (msr_image and recipe_search) until 2026-08-09, and a rule that is
    deliberately tightened or loosened later is exactly the kind that must not
    be tightened in one copy only.

    Takes the raw value rather than the request so this module stays free of
    Flask and testable without a request context.
    """
    return (raw or "").strip().lower() in ("1", "true", "yes")


def preview_bytes(data: bytes, content_type: str) -> tuple[bytes, str]:
    """``to_preview`` for callers that hold bytes, not a ``FetchedImage``.

    recipe_search serves raw recipe-folder files, which have no ``cond``
    sidecar; before this existed it built a ``FetchedImage(payload, ct, None)``
    just to reach the transform and then threw the third field away. Handing a
    contract type a placeholder to borrow a function is how that type stops
    meaning anything.
    """
    rendition = to_preview(FetchedImage(data, content_type, None))
    return rendition.data, rendition.content_type


def to_preview(fetched: FetchedImage) -> FetchedImage:
    """The browser-renderable rendition of ``fetched``, by content sniff.

    TIFF bytes → WebP; the mock's SVG-labeled-as-TIFF placeholder → relabeled
    SVG; anything else (already-renderable JPEG/WebP/…) → unchanged. Never
    raises: a conversion failure returns the original, logged.
    """
    if is_tiff_bytes(fetched.data):
        try:
            webp = _tiff_to_webp(fetched.data)
        except Exception as exc:  # noqa: BLE001 — degrade to the original bytes
            _LOG.warning("msr_image: TIFF preview conversion failed (%s) — serving original", exc)
            return fetched
        return FetchedImage(webp, "image/webp", fetched.cond)
    if fetched.content_type == "image/tiff" and _looks_like_svg(fetched.data):
        # Home: the mock labels its SVG placeholder image/tiff so the
        # download-fallback path stays reachable without preview. With
        # preview=1 the honest answer is what the bytes are.
        return FetchedImage(fetched.data, "image/svg+xml", fetched.cond)
    return fetched
