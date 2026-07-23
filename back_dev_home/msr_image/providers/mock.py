"""Offline byte source: deterministic SVG placeholders + synthetic listing/cond.

Seeded from the locator so the same MSR always yields the same gallery. Lets the
whole flow (list → serve → cond → download-all → cache → purge) run with no tool,
no OpenSearch, no MinIO.
"""

import hashlib
from collections.abc import Callable

from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

OnFile = Callable[[str, FetchedImage | None, str | None], None]


def _seed(*parts: str) -> int:
    return int(hashlib.md5("|".join(parts).encode()).hexdigest(), 16)


def list_images(eqp_ip: str, class_name: str, msr: str) -> list[str]:
    count = 3 + _seed(eqp_ip, class_name, msr) % 6  # 3..8 images
    return [f"{msr}_shot{i:02d}.jpeg" for i in range(1, count + 1)]


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
