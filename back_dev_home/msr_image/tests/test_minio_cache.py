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


class _NoSuchKey(Exception):
    """Shaped like minio's S3Error: what MinioImageCache.get sniffs is ``.code``.

    Duck-typed rather than the real S3Error because ``minio`` is an office-only
    dependency and these tests run at home.
    """

    code = "NoSuchKey"


class FakeMinio:
    """In-memory stand-in for minio_handler.MinioObject (only what we use)."""

    def __init__(self):
        self.store = {}  # key -> (bytes, metadata, last_modified)
        self.calls = []  # every round trip, in order — proves the call count

    def put(self, key, data, *, content_type="application/octet-stream", metadata=None, **kw):
        self.calls.append(("put", key))
        self.store[key] = (bytes(data), dict(metadata or {}), datetime.now(timezone.utc))

    def exists(self, key, **kw):
        self.calls.append(("exists", key))
        return key in self.store

    def get(self, key, **kw):
        self.calls.append(("get", key))
        if key not in self.store:
            raise _NoSuchKey(key)
        return self.store[key][0]

    def stat(self, key, **kw):
        self.calls.append(("stat", key))
        if key not in self.store:
            raise _NoSuchKey(key)
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


def test_hit_costs_two_round_trips_not_three():
    """get() used to stat (via exists), then GET, then stat again. The gallery
    fans these out, so the redundant existence probe was pure added latency."""
    cache, fake = _cache()
    cache.put(LOC, IMG)
    fake.calls.clear()
    assert cache.get(LOC) is not None
    assert [c[0] for c in fake.calls] == ["get", "stat"]


def test_miss_does_not_500_when_the_object_vanishes_mid_read():
    """A purge between the old exists() and get() turned a miss into a raise.
    Sniffing the not-found code off the GET itself removes the window."""
    cache, fake = _cache()
    fake.calls.clear()
    assert cache.get(LOC) is None
    assert [c[0] for c in fake.calls] == ["get"]


def test_a_non_missing_error_still_propagates():
    """Only "not found" means miss. A permissions or transport failure must not
    be swallowed into a silent cache miss that then refetches from the tool."""
    cache, fake = _cache()

    class _Denied(Exception):
        code = "AccessDenied"

    def boom(key, **kw):
        raise _Denied(key)

    fake.get = boom
    try:
        cache.get(LOC)
    except _Denied:
        pass
    else:
        raise AssertionError("AccessDenied was swallowed as a cache miss")


def test_preview_rendition_is_a_separate_object():
    cache, fake = _cache()
    webp = FetchedImage(b"RIFF\x00\x00\x00\x00WEBP", "image/webp", "mag=50000")
    cache.put(LOC, IMG)
    cache.put(LOC, webp, preview=True)
    assert sorted(fake.store) == [
        "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg",
        "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg.preview.webp",
    ]
    assert cache.get(LOC).content_type == "image/jpeg"
    got = cache.get(LOC, preview=True)
    assert got.content_type == "image/webp"
    assert got.data == webp.data
    assert got.cond == "mag=50000"


def test_purge_sweeps_renditions_with_the_same_prefix_pass():
    """Renditions live under the same cache prefix, so the nightly last_modified
    sweep must reach them without any extra rule."""
    cache, fake = _cache()
    cache.put(LOC, FetchedImage(b"RIFF", "image/webp", None), preview=True)
    key = "image_cache/10.0.0.1/ADI/MSR_1/shot01.jpeg.preview.webp"
    data, meta, _ = fake.store[key]
    fake.store[key] = (data, meta, datetime.now(timezone.utc) - timedelta(hours=100))
    assert cache.purge(ttl_hours=72) == 1
    assert fake.store == {}


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
        if self._resolve(key) not in self.store:
            raise _NoSuchKey(key)
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
