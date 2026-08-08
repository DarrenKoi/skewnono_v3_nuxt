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
# S3/MinIO caps total user metadata around 2KB; keep cond well under that so an
# oversized sidecar can't get the image PUT rejected. cond.txt is a few lines.
_COND_META_MAX_BYTES = 1536


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

    def _key(self, locator: ImageLocator, preview: bool = False) -> str:
        # Objects live at {self.prefix}{cache_key}; the client is a passthrough
        # (use_prefix(None) in _default_client), so this is the sole prefix
        # source. If office MinIO requires objects under a configured user
        # namespace (e.g. "user/2067928/"), set SKEWNONO_IMAGE_CACHE_PREFIX to
        # the FULL prefix (e.g. "user/2067928/image_cache/") -- this method
        # applies it and the client adds nothing on top.
        return f"{self.prefix}{cache_key(locator, preview=preview)}"

    def has(self, locator: ImageLocator, *, preview: bool = False) -> bool:
        """Existence only (one stat round-trip) — get() would download the
        object body, which is exactly what the scoped warm job must avoid
        when deciding whether a file still needs fetching."""
        return bool(self.client.exists(self._key(locator, preview)))

    def get(self, locator: ImageLocator, *, preview: bool = False) -> FetchedImage | None:
        """Two round trips on a hit (GET, then stat for the sidecar metadata),
        one on a miss.

        It was three: an ``exists()`` probe -- itself a stat -- ran before the
        GET. Besides the wasted latency on a path the gallery fans out, the
        probe opened a window: an object purged between exists() and get()
        raised out of a method whose whole contract is to answer None for
        "not cached". Reading the not-found off the GET closes it.

        One round trip would need a minio_handler call that returns body and
        stat together; it has none, and that package is vendored (a change
        there has to land in flask_modules too).
        """
        key = self._key(locator, preview)
        try:
            data = self.client.get(key)
        except Exception as exc:  # noqa: BLE001 — re-raised unless it means "absent"
            if _is_not_found(exc):
                return None
            raise
        meta = _user_metadata(self.client.stat(key))
        cond_raw = meta.get(_COND_META)
        content_type = meta.get(_TYPE_META, "application/octet-stream")
        return FetchedImage(data, content_type, unquote(cond_raw) if cond_raw is not None else None)

    def put(
        self, locator: ImageLocator, fetched: FetchedImage, *, preview: bool = False
    ) -> None:
        metadata = {_TYPE_META: fetched.content_type}
        if fetched.cond is not None:
            encoded = quote(fetched.cond)
            # cond rides as MinIO user metadata, which S3/MinIO caps (~2KB total
            # user-metadata). cond.txt is normally a few short lines; if an
            # oversized one would get the whole PUT rejected, drop the cond
            # rather than fail the image (image-first, cond best-effort — spec §6.2).
            if len(encoded.encode("utf-8")) <= _COND_META_MAX_BYTES:
                metadata[_COND_META] = encoded
        self.client.put(
            self._key(locator, preview),
            fetched.data,
            content_type=fetched.content_type,
            metadata=metadata,
        )

    def purge(self, ttl_hours: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        stale = [
            obj.object_name
            for obj in self.client.list(prefix=self.prefix, recursive=True)
            # An S3 "directory" entry (CommonPrefixes) carries last_modified=None.
            # recursive=True means MinIO returns none of them today, so this is
            # belt-and-braces -- but an ageless entry must be skipped, never
            # deleted: without the guard _as_utc(None) raises and the whole
            # nightly sweep dies before deleting anything.
            if obj.last_modified is not None and _as_utc(obj.last_modified) < cutoff
        ]
        if not stale:
            return 0
        # delete_many returns per-object error entries; don't count those as
        # removed, so a fully-failed sweep can't log as a success.
        errors = self.client.delete_many(stale) or []
        return len(stale) - len(errors)


# minio raises S3Error with one of these in ``.code`` when the object is gone;
# the same set minio_handler's own exists() treats as absent. Matched by duck
# type rather than ``isinstance(exc, S3Error)`` because ``minio`` is an
# office-only dependency -- importing it here would drag it into home boot and
# into every test run.
_NOT_FOUND_CODES = frozenset({"NoSuchKey", "NoSuchObject", "NotFound"})


def _is_not_found(exc: Exception) -> bool:
    return getattr(exc, "code", None) in _NOT_FOUND_CODES


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
