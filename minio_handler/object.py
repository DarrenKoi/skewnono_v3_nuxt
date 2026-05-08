"""Object-level CRUD operations against a MinIO / S3-compatible bucket."""

import io
from collections.abc import Iterable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any, BinaryIO

from .base import MinioBase


def _delete_object_class() -> type[Any]:
    from minio.deleteobjects import DeleteObject

    return DeleteObject


class MinioObject(MinioBase):
    """File-style CRUD wrapper for MinIO objects.

    S3/MinIO has no in-place update — ``put`` and ``upload`` overwrite when
    the key already exists, which serves as both create and update.
    """

    def put(
        self,
        key: str,
        data: bytes | bytearray | memoryview | BinaryIO,
        *,
        bucket: str | None = None,
        length: int | None = None,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        part_size: int = 0,
    ) -> Any:
        """Write raw bytes or a binary stream to ``key``.

        For streams without a known size, pass ``length=-1`` and a non-zero
        ``part_size`` (e.g. 10 * 1024 * 1024).
        """

        bucket_name = self._resolve_bucket(bucket)
        full_key = self._resolve_key(key)

        if isinstance(data, (bytes, bytearray, memoryview)):
            buffer = bytes(data)
            stream: BinaryIO = io.BytesIO(buffer)
            data_length = len(buffer)
        else:
            stream = data
            data_length = -1 if length is None else length
            if data_length == -1 and part_size <= 0:
                raise ValueError(
                    "part_size is required when stream length is unknown."
                )

        return self.client.put_object(
            bucket_name,
            full_key,
            stream,
            data_length,
            content_type=content_type,
            metadata=metadata,
            part_size=part_size,
        )

    def upload(
        self,
        key: str,
        file_path: str | Path,
        *,
        bucket: str | None = None,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
        part_size: int = 0,
    ) -> Any:
        """Upload a local file to ``key``."""

        bucket_name = self._resolve_bucket(bucket)
        full_key = self._resolve_key(key)
        source = Path(file_path)

        return self.client.fput_object(
            bucket_name,
            full_key,
            str(source),
            content_type=content_type,
            metadata=metadata,
            part_size=part_size,
        )

    def get(
        self,
        key: str,
        *,
        bucket: str | None = None,
        offset: int = 0,
        length: int = 0,
    ) -> bytes:
        """Read object body and return raw bytes."""

        bucket_name = self._resolve_bucket(bucket)
        full_key = self._resolve_key(key)

        response = self.client.get_object(
            bucket_name,
            full_key,
            offset=offset,
            length=length,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def put_json(
        self,
        key: str,
        obj: Any,
        *,
        bucket: str | None = None,
        metadata: dict[str, str] | None = None,
        indent: int | None = None,
        ensure_ascii: bool = False,
        default: Any = None,
    ) -> Any:
        """Serialize ``obj`` to JSON (UTF-8) and upload.

        Use this when ``obj`` is a live Python value (dict, list, ...).
        If you already have JSON bytes or a ``.json`` file on disk, call
        ``put`` / ``upload`` directly with
        ``content_type="application/json; charset=utf-8"`` — otherwise
        ``put_json`` would re-encode and double-quote your payload.

        ``default`` is forwarded to ``json.dumps`` so non-native types
        (datetime, Decimal, ...) can be handled by the caller.
        """

        import json

        payload = json.dumps(
            obj,
            indent=indent,
            ensure_ascii=ensure_ascii,
            default=default,
        ).encode("utf-8")
        return self.put(
            key,
            payload,
            bucket=bucket,
            content_type="application/json; charset=utf-8",
            metadata=metadata,
        )

    def get_json(self, key: str, *, bucket: str | None = None) -> Any:
        """Download a JSON object and return the parsed value."""

        import json

        return json.loads(self.get(key, bucket=bucket).decode("utf-8"))

    def put_pickle(
        self,
        key: str,
        obj: Any,
        *,
        bucket: str | None = None,
        metadata: dict[str, str] | None = None,
        protocol: int | None = None,
    ) -> Any:
        """Pickle a Python object and upload it.

        Use this when ``obj`` is a live Python value. If you already have
        pickled bytes in memory, call ``put`` directly; if you already have
        a ``.pkl`` file on disk, call ``upload``. Passing pre-pickled bytes
        here would pickle them a second time and you'd have to unpickle
        twice on the way out.

        Only safe for objects produced by trusted code — ``get_pickle`` will
        execute whatever's in the payload.
        """

        import pickle

        payload = pickle.dumps(obj, protocol=protocol)
        return self.put(
            key,
            payload,
            bucket=bucket,
            content_type="application/octet-stream",
            metadata=metadata,
        )

    def get_pickle(self, key: str, *, bucket: str | None = None) -> Any:
        """Download a pickled object and return the unpickled value."""

        import pickle

        return pickle.loads(self.get(key, bucket=bucket))

    def put_dataframe(
        self,
        key: str,
        df: Any,
        *,
        bucket: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Any:
        """Serialize a pandas DataFrame to parquet (pyarrow) and upload.

        Use this when ``df`` is a live ``pd.DataFrame``. If you already
        have a ``.parquet`` file on disk, call ``upload`` (it streams via
        ``fput_object`` and avoids loading the whole frame into RAM); if
        you already have parquet bytes in memory, call ``put``. In both
        cases pass ``content_type="application/vnd.apache.parquet"`` so
        downstream MIME-sniffing tools recognize it.
        """

        buf = io.BytesIO()
        df.to_parquet(buf, engine="pyarrow")
        return self.put(
            key,
            buf.getvalue(),
            bucket=bucket,
            content_type="application/vnd.apache.parquet",
            metadata=metadata,
        )

    def get_dataframe(self, key: str, *, bucket: str | None = None) -> Any:
        """Download a parquet object and return it as a pandas DataFrame."""

        import pandas as pd

        return pd.read_parquet(
            io.BytesIO(self.get(key, bucket=bucket)),
            engine="pyarrow",
        )

    def download(
        self,
        key: str,
        file_path: str | Path,
        *,
        bucket: str | None = None,
    ) -> Path:
        """Download ``key`` to a local file path. Returns the destination path."""

        bucket_name = self._resolve_bucket(bucket)
        full_key = self._resolve_key(key)
        destination = Path(file_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        self.client.fget_object(bucket_name, full_key, str(destination))
        return destination

    def stat(self, key: str, *, bucket: str | None = None) -> Any:
        """Return object metadata (size, etag, content_type, last_modified, ...)."""

        bucket_name = self._resolve_bucket(bucket)
        full_key = self._resolve_key(key)
        return self.client.stat_object(bucket_name, full_key)

    def exists(self, key: str, *, bucket: str | None = None) -> bool:
        """Return ``True`` if the object exists, ``False`` otherwise."""

        from minio.error import S3Error

        try:
            self.stat(key, bucket=bucket)
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
                return False
            raise
        return True

    def delete(self, key: str, *, bucket: str | None = None) -> None:
        """Delete a single object."""

        bucket_name = self._resolve_bucket(bucket)
        full_key = self._resolve_key(key)
        self.client.remove_object(bucket_name, full_key)

    def delete_many(
        self,
        keys: Iterable[str],
        *,
        bucket: str | None = None,
    ) -> list[Any]:
        """Delete multiple objects in one request. Returns any error entries."""

        bucket_name = self._resolve_bucket(bucket)
        delete_object = _delete_object_class()
        targets = [delete_object(self._resolve_key(k)) for k in keys]
        if not targets:
            return []
        return list(self.client.remove_objects(bucket_name, targets))

    def delete_prefix(
        self,
        prefix: str,
        *,
        bucket: str | None = None,
    ) -> list[Any]:
        """Delete every object under ``prefix`` recursively. Returns error entries.

        ``prefix`` is composed with ``default_prefix`` the same way object keys
        are: ``delete_prefix("runs/")`` on a service with ``prefix="kpo"``
        wipes everything under ``kpo/runs/``.
        """

        scoped_prefix = self._resolve_key(prefix) if prefix else self.default_prefix
        if not scoped_prefix:
            raise ValueError(
                "delete_prefix requires a non-empty prefix or a configured "
                "default prefix."
            )

        bucket_name = self._resolve_bucket(bucket)
        delete_object = _delete_object_class()
        targets = [
            delete_object(obj.object_name)
            for obj in self.list(prefix, bucket=bucket, recursive=True)
        ]
        if not targets:
            return []
        return list(self.client.remove_objects(bucket_name, targets))

    def presigned_get_url(
        self,
        key: str,
        *,
        bucket: str | None = None,
        expires: timedelta = timedelta(days=7),
        response_headers: dict[str, str] | None = None,
        version_id: str | None = None,
    ) -> str:
        """Return a temporary URL anyone can ``GET`` to download the object.

        ``response_headers`` overrides headers MinIO returns on the download
        (e.g. ``{"response-content-disposition": "attachment; filename=x.csv"}``
        to force a browser save dialog).
        """

        bucket_name = self._resolve_bucket(bucket)
        full_key = self._resolve_key(key)
        return self.client.presigned_get_object(
            bucket_name,
            full_key,
            expires=expires,
            response_headers=response_headers,
            version_id=version_id,
        )

    def presigned_put_url(
        self,
        key: str,
        *,
        bucket: str | None = None,
        expires: timedelta = timedelta(minutes=20),
    ) -> str:
        """Return a temporary URL a client can ``PUT`` raw bytes to.

        Hand this to a browser or another service so it uploads straight to
        MinIO without seeing the access/secret keys.
        """

        bucket_name = self._resolve_bucket(bucket)
        full_key = self._resolve_key(key)
        return self.client.presigned_put_object(
            bucket_name,
            full_key,
            expires=expires,
        )

    def list(
        self,
        prefix: str | None = None,
        *,
        bucket: str | None = None,
        recursive: bool = True,
        start_after: str | None = None,
    ) -> Iterator[Any]:
        """Yield objects under ``prefix`` (combined with the default prefix)."""

        bucket_name = self._resolve_bucket(bucket)
        scoped_prefix = self._resolve_key(prefix) if prefix else self.default_prefix

        kwargs: dict[str, Any] = {
            "bucket_name": bucket_name,
            "recursive": recursive,
        }
        if scoped_prefix:
            kwargs["prefix"] = scoped_prefix.rstrip("/") + "/"
        if start_after is not None:
            kwargs["start_after"] = start_after

        return self.client.list_objects(**kwargs)

