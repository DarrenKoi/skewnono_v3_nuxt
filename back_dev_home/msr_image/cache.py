"""ImageCache interface + disk backend. MinIO backend is added in Task 11.

Cache key mirrors the semantic locator so on-disk paths are inspectable:
``{eqp_ip}/{class_name}/{msr}/{name}``. The image body lives at that path; its
content-type and cond travel as tiny sidecars (``<file>.type`` / ``<file>.cond``)
so a bytes-only medium needs no metadata channel.

Each locator has room for TWO entries: the tool's original bytes, and the
browser-renderable WebP rendition of them under the same key plus
``PREVIEW_SUFFIX``. They are separate because they serve separate callers --
``?preview=1`` feeds an ``<img>``, the 원본 다운로드 link wants the TIFF -- and
one key could only ever satisfy one of them.
"""

import time
from pathlib import Path
from typing import Protocol

from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator


# Suffixed rather than kept in a separate prefix tree: a rendition then sorts
# next to its original in any listing, and the nightly sweep reaches both
# without a second rule. Only real TIFF->WebP conversions are stored under it
# (see routes.serve_image_route), so the ``.webp`` in the name is never a lie.
# It cannot collide with a tool file either -- office listings admit only
# .jpeg/.jpg/.tif/.tiff, so no locator name ever ends in ".preview.webp".
PREVIEW_SUFFIX = ".preview.webp"


def cache_key(locator: ImageLocator, *, preview: bool = False) -> str:
    key = f"{locator.eqp_ip}/{locator.class_name}/{locator.msr}/{locator.name}"
    return key + PREVIEW_SUFFIX if preview else key


class ImageCache(Protocol):
    def get(self, locator: ImageLocator, *, preview: bool = False) -> FetchedImage | None: ...
    def has(self, locator: ImageLocator, *, preview: bool = False) -> bool: ...
    def put(
        self, locator: ImageLocator, fetched: FetchedImage, *, preview: bool = False
    ) -> None: ...
    def purge(self, ttl_hours: int) -> int: ...


class DiskImageCache:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path(self, locator: ImageLocator, preview: bool = False) -> Path:
        return self.root / cache_key(locator, preview=preview)

    def has(self, locator: ImageLocator, *, preview: bool = False) -> bool:
        """Existence only — no body read. The scoped warm job uses this to
        skip files already cached without paying a full get()."""
        return self._path(locator, preview).is_file()

    def get(self, locator: ImageLocator, *, preview: bool = False) -> FetchedImage | None:
        path = self._path(locator, preview)
        if not path.is_file():
            return None
        data = path.read_bytes()
        type_file = path.with_name(path.name + ".type")
        cond_file = path.with_name(path.name + ".cond")
        content_type = (
            type_file.read_text(encoding="utf-8") if type_file.is_file() else "application/octet-stream"
        )
        cond = cond_file.read_text(encoding="utf-8") if cond_file.is_file() else None
        return FetchedImage(data, content_type, cond)

    def put(
        self, locator: ImageLocator, fetched: FetchedImage, *, preview: bool = False
    ) -> None:
        path = self._path(locator, preview)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fetched.data)
        path.with_name(path.name + ".type").write_text(fetched.content_type, encoding="utf-8")
        cond_file = path.with_name(path.name + ".cond")
        if fetched.cond is not None:
            cond_file.write_text(fetched.cond, encoding="utf-8")
        elif cond_file.exists():
            cond_file.unlink()

    def purge(self, ttl_hours: int) -> int:
        cutoff = time.time() - ttl_hours * 3600
        removed = 0
        if not self.root.exists():
            return 0
        for path in self.root.rglob("*"):
            if not path.is_file() or path.name.endswith((".type", ".cond")):
                continue
            if path.stat().st_mtime < cutoff:
                for sidecar in (path, path.with_name(path.name + ".type"), path.with_name(path.name + ".cond")):
                    if sidecar.exists():
                        sidecar.unlink()
                removed += 1
        return removed


def make_cache(cfg, provider: str):
    """Pick the cache backend that matches the byte source.

    ``cfg`` is an ImageConfig (typed loosely to avoid a config import cycle).
    """
    if provider == "office":
        # Fail loud (spec §7: 필수 환경 변수 누락 → 500) rather than silently
        # falling back to minio_handler's default bucket — the office cache must
        # write to an explicitly-configured bucket, kept separate from the
        # measurement-data buckets (see MIGRATION.md).
        if not cfg.cache_bucket:
            from back_dev_home.msr_image.errors import ConfigError
            raise ConfigError("SKEWNONO_IMAGE_CACHE_BUCKET is required in office mode")
        # A root/empty prefix would make purge's list(prefix) enumerate the WHOLE
        # bucket and delete_many wipe unrelated (measurement) data. Refuse it.
        if (cfg.cache_prefix or "").strip("/ ") == "":
            from back_dev_home.msr_image.errors import ConfigError
            raise ConfigError(
                "SKEWNONO_IMAGE_CACHE_PREFIX must be a non-root path (e.g. image_cache/)"
            )
        from back_dev_home.msr_image.minio_cache import MinioImageCache
        return MinioImageCache(
            bucket=cfg.cache_bucket, prefix=cfg.cache_prefix
        )
    return DiskImageCache(cfg.cache_dir)
