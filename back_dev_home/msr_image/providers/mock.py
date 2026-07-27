"""Offline byte source: deterministic SVG placeholders + synthetic listing/cond.

Seeded from the locator so the same MSR always yields the same gallery. Lets the
whole flow (list → serve → cond → download-all → cache → purge) run with no tool,
no OpenSearch, no MinIO.

Office counterpart — schema of record: `docs/datatables/msr_image_ftp.txt`.
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

from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

OnFile = Callable[[str, FetchedImage | None, str | None], None]


def _seed(*parts: str) -> int:
    return int(hashlib.md5("|".join(parts).encode()).hexdigest(), 16)


def list_images(eqp_ip: str, class_name: str, msr: str) -> list[str]:
    count = 3 + _seed(eqp_ip, class_name, msr) % 6  # 3..8 images
    # Office tools serve JPEG previews alongside TIFF originals (confirmed
    # 2026-07-24) — every 4th shot is a .tif so the frontend's no-preview
    # fallback stays exercised at home.
    return [
        f"{msr}_shot{i:02d}.{'tif' if i % 4 == 0 else 'jpeg'}"
        for i in range(1, count + 1)
    ]


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
    s = _seed(locator.name)
    return f"mag={30000 + s % 40000}\nvac={0.5 + (s % 5) / 10:.1f}\npixel={2 + s % 6}nm"


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
