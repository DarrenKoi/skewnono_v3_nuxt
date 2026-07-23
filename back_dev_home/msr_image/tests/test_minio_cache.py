from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote

from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator
from back_dev_home.msr_image.minio_cache import MinioImageCache

LOC = ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg")
IMG = FetchedImage(b"\xff\xd8jpeg", "image/jpeg", "mag=50000")


class _Stat:
    def __init__(self, metadata, last_modified):
        self.metadata = metadata
        self.last_modified = last_modified


class _Obj:
    def __init__(self, object_name, last_modified):
        self.object_name = object_name
        self.last_modified = last_modified


class FakeMinio:
    """In-memory stand-in for minio_handler.MinioObject (only what we use)."""

    def __init__(self):
        self.store = {}  # key -> (bytes, metadata, last_modified)

    def put(self, key, data, *, content_type="application/octet-stream", metadata=None, **kw):
        self.store[key] = (bytes(data), dict(metadata or {}), datetime.now(timezone.utc))

    def exists(self, key, **kw):
        return key in self.store

    def get(self, key, **kw):
        return self.store[key][0]

    def stat(self, key, **kw):
        _, metadata, lm = self.store[key]
        # minio returns user metadata with an x-amz-meta- prefix; emulate it.
        prefixed = {f"x-amz-meta-{k}": v for k, v in metadata.items()}
        return _Stat(prefixed, lm)

    def list(self, prefix=None, *, recursive=True, **kw):
        for key, (_, _, lm) in list(self.store.items()):
            yield _Obj(key, lm)

    def delete_many(self, keys, **kw):
        for k in keys:
            self.store.pop(k, None)
        return []


def _cache():
    fake = FakeMinio()
    return MinioImageCache(bucket="b", prefix="image_cache/", client_factory=lambda: fake), fake


def test_miss_returns_none():
    cache, _ = _cache()
    assert cache.get(LOC) is None


def test_put_then_get_roundtrips_with_metadata():
    cache, fake = _cache()
    cache.put(LOC, IMG)
    key = "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg"
    assert key in fake.store
    assert fake.store[key][1]["x-msr-cond"] == quote("mag=50000")
    got = cache.get(LOC)
    assert got.data == IMG.data
    assert got.content_type == "image/jpeg"
    assert got.cond == "mag=50000"


def test_shared_hit_across_instances():
    cache_a, fake = _cache()
    cache_a.put(LOC, IMG)
    cache_b = MinioImageCache(bucket="b", prefix="image_cache/", client_factory=lambda: fake)
    assert cache_b.get(LOC).data == IMG.data


def test_purge_deletes_expired_by_last_modified():
    cache, fake = _cache()
    cache.put(LOC, IMG)
    key = "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg"
    data, meta, _ = fake.store[key]
    fake.store[key] = (data, meta, datetime.now(timezone.utc) - timedelta(hours=100))
    assert cache.purge(ttl_hours=72) == 1
    assert cache.get(LOC) is None
