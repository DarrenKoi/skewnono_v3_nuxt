import os
import time

from back_dev_home._scheduler.tasks.image_cache import purge_image_cache
from back_dev_home.msr_image.cache import DiskImageCache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator


def test_purge_image_cache_removes_expired(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    cfg = load_config({"IMAGE_CACHE_DIR": str(tmp_path), "IMAGE_CACHE_TTL_HOURS": "72"})
    cache = DiskImageCache(str(tmp_path))
    loc = ImageLocator("10.0.0.1", "ADI", "MSR_1", "a.jpeg")
    cache.put(loc, FetchedImage(b"x", "image/jpeg", None))
    aged = tmp_path / "10.0.0.1" / "ADI" / "MSR_1" / "a.jpeg"
    old = time.time() - 100 * 3600
    os.utime(aged, (old, old))

    assert purge_image_cache(cfg) == 1
    assert cache.get(loc) is None


def test_purge_image_cache_keeps_fresh_objects(tmp_path, monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    cfg = load_config({"IMAGE_CACHE_DIR": str(tmp_path), "IMAGE_CACHE_TTL_HOURS": "72"})
    cache = DiskImageCache(str(tmp_path))
    loc = ImageLocator("10.0.0.1", "ADI", "MSR_1", "fresh.jpeg")
    cache.put(loc, FetchedImage(b"x", "image/jpeg", None))

    assert purge_image_cache(cfg) == 0
    assert cache.get(loc) is not None
