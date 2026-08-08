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
        elif im.mode not in ("L", "RGB"):
            # palette / RGBA / CMYK and friends — WebP wants L or RGB(A).
            im = im.convert("RGB")
        out = BytesIO()
        im.save(out, "WEBP", quality=_WEBP_QUALITY)
        return out.getvalue()


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
