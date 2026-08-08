import os
import time

from back_dev_home.msr_image.cache import DiskImageCache, cache_key
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

LOC = ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg")
IMG = FetchedImage(b"\xff\xd8jpegbytes", "image/jpeg", "mag=50000\nvac=0.8")


WEBP = FetchedImage(b"RIFF\x00\x00\x00\x00WEBP", "image/webp", "mag=50000\nvac=0.8")


def test_key_is_deterministic():
    assert cache_key(LOC) == "10.0.0.1/ADI/MSR_1/shot01.jpeg"


def test_preview_key_suffixes_the_original_key():
    assert cache_key(LOC, preview=True) == "10.0.0.1/ADI/MSR_1/shot01.jpeg.preview.webp"


def test_preview_and_original_are_separate_entries(tmp_path):
    """The rendition must not evict or shadow the original: the 원본 다운로드
    link reads the same locator with no preview flag."""
    cache = DiskImageCache(str(tmp_path))
    cache.put(LOC, IMG)
    cache.put(LOC, WEBP, preview=True)
    assert cache.get(LOC) == IMG
    assert cache.get(LOC, preview=True) == WEBP


def test_preview_miss_is_independent_of_the_original(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    cache.put(LOC, IMG)
    assert cache.get(LOC, preview=True) is None
    assert not cache.has(LOC, preview=True)


def test_purge_removes_a_rendition_and_its_sidecar(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    cache.put(LOC, WEBP, preview=True)
    folder = tmp_path / "10.0.0.1" / "ADI" / "MSR_1"
    old = time.time() - 100 * 3600
    os.utime(folder / "shot01.jpeg.preview.webp", (old, old))
    assert cache.purge(ttl_hours=72) == 1
    assert cache.get(LOC, preview=True) is None
    # The .type/.cond sidecars go with it — an orphaned sidecar would make the
    # next put/get pair read a stale content type.
    assert list(folder.glob("*")) == []


def test_has_reports_presence_without_reading_the_body(tmp_path):
    cache = DiskImageCache(str(tmp_path))
    assert not cache.has(LOC)
    cache.put(LOC, IMG)
    assert cache.has(LOC)


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
