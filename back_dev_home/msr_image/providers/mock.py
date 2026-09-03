"""Offline byte source: deterministic SVG placeholders + synthetic listing/cond.

Seeded from the locator so the same MSR always yields the same gallery. Lets the
whole flow (list → serve → cond → download-all → cache → purge) run with no tool,
no OpenSearch, no MinIO.

Office counterpart — schema of record: `docs/datatables/hitachi/msr_image_ftp.txt`.
Measurement images are NOT in any database: they live only on the TOOL'S OWN FTP
server, and the backend opens a session to it per request.

    dir   /HITACHI/DEVICE/HD/{class_name}/images/{msr}
    image {dir}/{name}
    cond  {dir}/.{name}/cond.txt      ← hidden per-image sidecar, a DOT-PREFIXED
                                        FOLDER containing cond.txt, not a file

`class_name` and `msr` come from the parent meas_hist doc. Extensions are
.jpeg/.jpg/.tif/.tiff — tools serve JPEG previews alongside TIFF originals and
the pickle's mp_image_name columns reference BOTH, so a jpeg-only filter makes
every TIFF invisible (13 of 39 "missing" on the first office run). `list_images`
below keeps that split alive at home for the same reason.

Transport is chosen at import time by platform: the office Windows PC cannot
open FTP to tools directly and routes through an HTTP proxy, while the Linux
cloud deploy downloads directly. Both expose the same surface, so only the
import line differs.

SECURITY, and the reason `paths.validate_*` exists: the backend connects to
whatever IP the client sends, making the eqp_ip check an SSRF guard, and
class_name/msr/name are interpolated into both an FTP path and a filesystem
cache key — so a `/` or `..` escapes both. That validation is phase-independent
and runs at home too.
"""

import hashlib
from collections.abc import Callable

from back_dev_home._core.image_naming import HV_SEM_STEM_SUFFIXES
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

OnFile = Callable[[str, FetchedImage | None, str | None], None]


def _seed(*parts: str) -> int:
    return int(hashlib.md5("|".join(parts).encode()).hexdigest(), 16)


# Tools shoot one targeting point as several files, e.g.
# S04_M0004-01MP-U.jpeg / -T / -M / -L. The set is a protocol fact shared with
# msr_file and recipe_search — see _core/image_naming.py.
_STEM_SUFFIXES = HV_SEM_STEM_SUFFIXES


def list_images(eqp_ip: str, class_name: str, msr: str) -> list[str]:
    count = 3 + _seed(eqp_ip, class_name, msr) % 6  # 3..8 shots
    # Office tools serve JPEG previews alongside TIFF originals (confirmed
    # 2026-07-24) — every 4th shot is a .tif so the frontend's no-preview
    # fallback stays exercised at home. Every 3rd shot expands to an HV-SEM
    # suffixed pair (2026-08-08) so suffixed names exist in the home listing;
    # the request path treats names as opaque either way.
    #
    # Deliberately absent: the hidden `.{name}` cond sidecar DIRECTORIES that a
    # real tool's listing carries (office 확인 2026-08-10). This function stands
    # in for the whole provider, so it returns POST-filter names — what
    # list_images promises its caller — and the office adapter is the only place
    # that ever sees a raw listing. The filter those entries defeat is pinned
    # instead by tests/test_office_template.py, whose fake listing does carry
    # them; it has to, because they end in `.jpeg` and an extension-only filter
    # hands them back as images that then 550 on RETR.
    names: list[str] = []
    for i in range(1, count + 1):
        ext = "tif" if i % 4 == 0 else "jpeg"
        if i % 3 == 0:
            names += [f"{msr}_shot{i:02d}-{s}.{ext}" for s in _STEM_SUFFIXES[:2]]
            # One sub-position under BOTH renditions, uppercase .TIF spelling —
            # a jpeg-suffixed shot also lists its TIFF original (user-confirmed
            # 2026-08-24 via the pickle's 4-image U/U/L/L row; presence in the
            # FTP listing follows, since the pickle references what the tool
            # serves). Keeps the frontend's extension-disambiguated variant
            # labels exercised at home.
            if ext == "jpeg":
                names.append(f"{msr}_shot{i:02d}-{_STEM_SUFFIXES[0]}.TIF")
        else:
            names.append(f"{msr}_shot{i:02d}.{ext}")
    return names


def _svg(locator: ImageLocator) -> bytes:
    hue = _seed(locator.name) % 360
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240">'
        f'<rect width="240" height="240" fill="hsl({hue},60%,45%)"/>'
        f'<text x="12" y="128" fill="white" font-size="14">{locator.msr}</text>'
        f'<text x="12" y="150" fill="white" font-size="12">{locator.name}</text>'
        f"</svg>"
    ).encode()


def _cond(locator: ImageLocator) -> str:
    """A cond.txt body. The first three lines are placeholders; the last two
    are the REAL keys the crosshair cleaner reads (user-confirmed 2026-09-03,
    _core/cond_cursor.py): ``Pixel`` and a ``!Cursor_info`` whose [4],[5] put
    the crosshair near the frame centre, in a Pixel x 10 frame. OFFICE-VERIFY
    that measurement sidecars carry the line as the align ones do. The bytes
    are an SVG, so ``?clean=1`` is a no-op at home — the parse path runs, the
    erase does not."""
    s = _seed(locator.name)
    cx, cy = 2560 + s % 400 - 200, 2560 + (s // 7) % 400 - 200
    return (
        f"mag={30000 + s % 40000}\nvac={0.5 + (s % 5) / 10:.1f}\npixel={2 + s % 6}nm\n"
        f"Pixel\t512,512\n!Cursor_info\t0,0,0,0,{cx},{cy},-1,-1,-1,-1"
    )


def fetch_image(locator: ImageLocator) -> FetchedImage:
    # Bytes are always the SVG placeholder, but .tif names carry image/tiff so
    # the frontend's TIFF download-fallback path is reachable offline.
    if locator.name.lower().endswith((".tif", ".tiff")):
        return FetchedImage(_svg(locator), "image/tiff", _cond(locator))
    return FetchedImage(_svg(locator), "image/svg+xml", _cond(locator))


def download_all(
    eqp_ip: str,
    class_name: str,
    msr: str,
    names: list[str],
    on_file: OnFile,
    concurrency: int = 6,
) -> None:
    # Mock is CPU-only; no need for a pool. Match the office callback contract.
    for name in names:
        loc = ImageLocator(eqp_ip, class_name, msr, name)
        on_file(name, fetch_image(loc), None)
