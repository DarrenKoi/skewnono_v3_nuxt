from datetime import datetime, timedelta, timezone
from urllib.parse import quote

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


def test_has_is_a_stat_not_a_download():
    cache, _ = _cache()
    assert not cache.has(LOC)
    cache.put(LOC, IMG)
    assert cache.has(LOC)


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


def test_purge_skips_entries_without_last_modified():
    """S3 "directory" entries (CommonPrefixes) carry last_modified=None.

    purge() passes recursive=True so MinIO returns none of them today, but the
    comprehension must not crash -- or delete a prefix marker -- if a listing
    ever yields one.
    """
    cache, fake = _cache()
    cache.put(LOC, IMG)
    key = "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg"
    data, meta, _ = fake.store[key]
    fake.store[key] = (data, meta, datetime.now(timezone.utc) - timedelta(hours=100))
    real_list = fake.list
    fake.list = lambda *a, **kw: (
        obj for obj in [_Obj("image_cache/10.0.0.1/", None), *real_list(*a, **kw)]
    )

    assert cache.purge(ttl_hours=72) == 1
    assert "image_cache/10.0.0.1/" not in fake.store


class PrefixFake:
    """Models MinioBase's real prefix composition (use_prefix/_resolve_key),
    unlike FakeMinio above which stores by raw key. Used to prove
    _default_client's use_prefix(None) passthrough actually prevents the
    double/triple-prefixing bug end to end.
    """

    def __init__(self):
        self.store = {}
        self.default_prefix = None
        self.default_bucket = None

    def use_bucket(self, bucket):
        self.default_bucket = bucket
        return self

    def use_prefix(self, prefix):
        self.default_prefix = prefix.strip("/") if prefix else None
        return self

    def _resolve(self, key):
        cleaned = key.lstrip("/")
        if not self.default_prefix:
            return cleaned
        return f"{self.default_prefix}/{cleaned}"

    def put(self, key, data, *, content_type="application/octet-stream", metadata=None, **kw):
        self.store[self._resolve(key)] = (bytes(data), dict(metadata or {}), datetime.now(timezone.utc))

    def exists(self, key, **kw):
        return self._resolve(key) in self.store

    def get(self, key, **kw):
        return self.store[self._resolve(key)][0]

    def stat(self, key, **kw):
        _, metadata, lm = self.store[self._resolve(key)]
        prefixed = {f"x-amz-meta-{k}": v for k, v in metadata.items()}
        return _Stat(prefixed, lm)

    def list(self, prefix=None, *, recursive=True, **kw):
        scoped = self._resolve(prefix) if prefix else (self.default_prefix or "")
        for key, (_, _, lm) in list(self.store.items()):
            if key.startswith(scoped):
                yield _Obj(key, lm)

    def delete_many(self, keys, **kw):
        for k in keys:
            self.store.pop(self._resolve(k), None)
        return []


def test_default_client_path_single_prefix_and_purge_deletes(monkeypatch):
    """Drives the REAL _default_client factory (not client_factory=), with a
    fake that mimics MinioBase's own use_prefix/_resolve_key composition.
    Guards against double/triple-prefixing regressions: with the fix,
    _default_client clears the client prefix (use_prefix(None)), so
    MinioImageCache._key() is the sole prefix source and purge's
    list -> delete_many round trip actually removes the object.
    """
    fake = PrefixFake()
    monkeypatch.setattr("minio_handler.MinioObject", lambda *a, **kw: fake, raising=False)

    from back_dev_home.msr_image.minio_cache import MinioImageCache

    cache = MinioImageCache(bucket="b", prefix="image_cache/")  # default client_factory -> _default_client

    cache.put(LOC, IMG)
    key = "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg"
    assert list(fake.store.keys()) == [key]  # single image_cache/ segment, not doubled/tripled
    assert cache.get(LOC).data == IMG.data

    # Age it past the TTL, then purge.
    data, meta, _ = fake.store[key]
    fake.store[key] = (data, meta, datetime.now(timezone.utc) - timedelta(hours=100))
    assert cache.purge(ttl_hours=72) == 1
    assert cache.get(LOC) is None  # actually deleted, not silently no-op'd
