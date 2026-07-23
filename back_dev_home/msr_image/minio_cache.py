"""Shared MinIO cache for office. Any worker/user reads what any other wrote.

cond + content-type ride as MinIO user metadata (small; cond.txt is a few
lines). Expiry is a last_modified sweep over the cache prefix — minio_handler's
delete_older_than is date-folder based and would fight a content-addressed key,
so we list + delete_many instead.
"""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, unquote

from back_dev_home.msr_image.cache import cache_key
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator

_COND_META = "x-msr-cond"
_TYPE_META = "x-msr-content-type"


def _default_client(bucket):
    # Lazy: office-only dependency, keeps home boot free of minio_handler.
    from minio_handler import MinioObject

    client = MinioObject()
    if bucket:
        client = client.use_bucket(bucket)
    # Passthrough: MinioImageCache._key() is the SOLE prefix source. If the
    # client also carried a default_prefix, MinioBase._resolve_key() would
    # prepend it a second time on every put/get/exists/stat, and list()
    # would hand purge() already-doubled object_names that delete_many()
    # would then re-resolve a third time -- silently deleting nothing (S3
    # delete of a missing key doesn't error). Keep this cleared.
    return client.use_prefix(None)


class MinioImageCache:
    def __init__(self, bucket, prefix="image_cache/", client_factory: Callable[[], object] | None = None):
        self.bucket = bucket
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"
        self._factory = client_factory or (lambda: _default_client(bucket))
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = self._factory()
        return self._client

    def _key(self, locator: ImageLocator) -> str:
        # Objects live at {self.prefix}{cache_key}; the client is a passthrough
        # (use_prefix(None) in _default_client), so this is the sole prefix
        # source. If office MinIO requires objects under a configured user
        # namespace (e.g. "user/2067928/"), set SKEWNONO_IMAGE_CACHE_PREFIX to
        # the FULL prefix (e.g. "user/2067928/image_cache/") -- this method
        # applies it and the client adds nothing on top.
        return f"{self.prefix}{cache_key(locator)}"

    def get(self, locator: ImageLocator) -> FetchedImage | None:
        key = self._key(locator)
        if not self.client.exists(key):
            return None
        data = self.client.get(key)
        stat = self.client.stat(key)
        meta = _user_metadata(stat)
        cond_raw = meta.get(_COND_META)
        content_type = meta.get(_TYPE_META, "application/octet-stream")
        return FetchedImage(data, content_type, unquote(cond_raw) if cond_raw is not None else None)

    def put(self, locator: ImageLocator, fetched: FetchedImage) -> None:
        metadata = {_TYPE_META: fetched.content_type}
        if fetched.cond is not None:
            metadata[_COND_META] = quote(fetched.cond)
        self.client.put(
            self._key(locator),
            fetched.data,
            content_type=fetched.content_type,
            metadata=metadata,
        )

    def purge(self, ttl_hours: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        stale = [
            obj.object_name
            for obj in self.client.list(prefix=self.prefix, recursive=True)
            if _as_utc(obj.last_modified) < cutoff
        ]
        if not stale:
            return 0
        self.client.delete_many(stale)
        return len(stale)


def _user_metadata(stat) -> dict[str, str]:
    """Strip the ``x-amz-meta-`` prefix MinIO adds to user metadata keys."""
    raw = getattr(stat, "metadata", {}) or {}
    out = {}
    for key, value in raw.items():
        lk = key.lower()
        out[lk[len("x-amz-meta-"):] if lk.startswith("x-amz-meta-") else lk] = value
    return out


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
