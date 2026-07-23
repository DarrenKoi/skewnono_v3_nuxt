import os
import time

from back_dev_home.msr_image.cache import DiskImageCache, cache_key
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

LOC = ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg")
IMG = FetchedImage(b"\xff\xd8jpegbytes", "image/jpeg", "mag=50000\nvac=0.8")


def test_key_is_deterministic():
    assert cache_key(LOC) == "10.0.0.1/ADI/MSR_1/shot01.jpeg"


def test_miss_returns_none(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    assert cache.get(LOC) is None


def test_put_then_get_roundtrips_bytes_type_and_cond(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    cache.put(LOC, IMG)
    got = cache.get(LOC)
    assert got == IMG


def test_put_without_cond_roundtrips(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    no_cond = FetchedImage(b"abc", "image/jpeg", None)
    cache.put(LOC, no_cond)
    assert cache.get(LOC) == no_cond


def test_purge_deletes_old_keeps_fresh(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    cache.put(LOC, IMG)
    # Age the image file 100h into the past.
    key_file = tmp_path / "10.0.0.1" / "ADI" / "MSR_1" / "shot01.jpeg"
    old = time.time() - 100 * 3600
    os.utime(key_file, (old, old))
    assert cache.purge(ttl_hours=72) == 1
    assert cache.get(LOC) is None
