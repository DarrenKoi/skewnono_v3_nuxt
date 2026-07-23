"""ImageCache interface + disk backend. MinIO backend is added in Task 11.

Cache key mirrors the semantic locator so on-disk paths are inspectable:
``{eqp_ip}/{class_name}/{msr}/{name}``. The image body lives at that path; its
content-type and cond travel as tiny sidecars (``<file>.type`` / ``<file>.cond``)
so a bytes-only medium needs no metadata channel.
"""

import os
import time
from pathlib import Path
from typing import Protocol

from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator


def cache_key(locator: ImageLocator) -> str:
    return f"{locator.eqp_ip}/{locator.class_name}/{locator.msr}/{locator.name}"


class ImageCache(Protocol):
    def get(self, locator: ImageLocator) -> FetchedImage | None: ...
    def put(self, locator: ImageLocator, fetched: FetchedImage) -> None: ...
    def purge(self, ttl_hours: int) -> int: ...


class DiskImageCache:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path(self, locator: ImageLocator) -> Path:
        return self.root / cache_key(locator)

    def get(self, locator: ImageLocator) -> FetchedImage | None:
        path = self._path(locator)
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

    def put(self, locator: ImageLocator, fetched: FetchedImage) -> None:
        path = self._path(locator)
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
        from back_dev_home.msr_image.minio_cache import MinioImageCache
        return MinioImageCache(
            bucket=cfg.cache_bucket, prefix=cfg.cache_prefix
        )
    return DiskImageCache(cfg.cache_dir)
