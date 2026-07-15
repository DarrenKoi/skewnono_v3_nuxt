"""Object-level CRUD operations against a MinIO / S3-compatible bucket."""

import io
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO
from zoneinfo import ZoneInfo

from .base import MinioBase

_KST = ZoneInfo("Asia/Seoul")


def _delete_object_class() -> type[Any]:
    from minio.deleteobjects import DeleteObject

    return DeleteObject


def _today_kst() -> date:
    """Today's date in KST. Split out as a seam so tests can pin 'today'."""

    return datetime.now(_KST).date()


def _parse_segment(folder_path: str, width: int) -> int | None:
    """Parse the leaf segment of a folder path as a ``width``-digit integer.

    ``folder_path`` ends in ``/``; the leaf must be exactly ``width`` digits
    (zero-padded) to parse. Returns ``None`` for any non-conforming segment so
    the date walk can skip it.
    """

    leaf = folder_path.rstrip("/").rsplit("/", 1)[-1]
    if len(leaf) != width or not leaf.isdigit():
        return None
    return int(leaf)


@dataclass(slots=True)
class DateFolder:
    """A discovered ``YYYY/MM/DD`` folder under a retention anchor.

    ``path`` is the full stored key prefix (default prefix included) ending in
    ``/`` — e.g. ``"hitachi_sem/cdsem/one/2026/06/11/"`` — so it feeds straight
    back into ``list`` / ``remove_objects``.
    """

    date: date
    path: str


@dataclass(slots=True)
class DeleteOlderResult:
    """Outcome of ``delete_older_than``, identical in shape for both modes.

    ``folders`` is the selected set (what would be / was deleted). ``errors``
    holds any ``remove_objects`` error entries — always empty on a dry run.
    """

    folders: list[DateFolder]
    errors: list[Any]


@dataclass(slots=True)
class GetManyResult:
    """Outcome of a batch ``get_many``.

    ``objects`` maps each key that loaded to its value, in the order the keys
    were requested — raw bytes, or whatever ``decode`` returned. ``errors``
    maps each key that failed to the exception raised, so a skipped key is
    never silently lost.
    """

    objects: dict[str, Any]
    errors: dict[str, Exception]


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

        ``data`` must already be bytes or a binary stream. For a live Python
        value (list, dict, ...) use ``put_json`` / ``put_pickle`` instead —
        they serialize first and set the right ``content_type``; passing the
        value here routes it through the stream branch and fails downstream.

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

    def get_many(
        self,
        keys: Iterable[str],
        *,
        bucket: str | None = None,
        decode: Callable[[bytes], Any] | None = None,
    ) -> GetManyResult:
        """Fetch many objects in sequence; skip (don't raise on) failures.

        Keys are fetched one at a time. A key that fails is recorded in
        ``GetManyResult.errors`` and the rest still load; both result maps keep
        the order the keys were requested. The whole batch stays resident in
        ``objects`` at once, so call this for bounded key lists — for sweeping a
        large prefix, loop and process each object instead.

        ``decode`` turns each body into a value (e.g. ``pickle.loads`` or
        ``lambda b: pd.read_parquet(io.BytesIO(b))``); it runs inside the
        per-key guard, so a body that fails to decode lands in ``errors`` just
        like a failed download. Omit it to keep raw bytes. A single ``decode``
        assumes every key in the batch is the same type.
        """

        objects: dict[str, Any] = {}
        errors: dict[str, Exception] = {}
        for key in keys:
            try:
                body = self.get(key, bucket=bucket)
                objects[key] = decode(body) if decode is not None else body
            except Exception as exc:
                errors[key] = exc
        return GetManyResult(objects=objects, errors=errors)

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

    def delete_matching(
        self,
        predicate: Callable[[str], bool],
        *,
        prefix: str | None = None,
        bucket: str | None = None,
    ) -> list[Any]:
        """Delete every object whose key satisfies ``predicate``. Returns error entries.

        Use this when the part you match on isn't a leading path segment — a
        date embedded mid-key, a varying format, an extension, etc. For a clean
        leading prefix (``runs/2026/06/11/...``) prefer ``delete_prefix``: it
        lets MinIO do the narrowing server-side instead of scanning.

        ``predicate`` receives each object's full key (``object_name``,
        ``default_prefix`` included) exactly as stored, and returns ``True`` to
        delete. ``prefix`` narrows the listing the same way ``list``/
        ``delete_prefix`` do (composed with ``default_prefix``); pass it
        whenever you can to avoid walking the whole bucket just to filter in
        Python. Matches are batched into a single ``remove_objects`` call.

        Deleting a day's worth of objects whose date sits inside the filename::

            store.delete_matching(lambda k: "2026-06-11" in k, prefix="sem")
        """

        bucket_name = self._resolve_bucket(bucket)
        delete_object = _delete_object_class()
        targets = [
            delete_object(obj.object_name)
            for obj in self.list(prefix, bucket=bucket, recursive=True)
            if predicate(obj.object_name)
        ]
        if not targets:
            return []
        return list(self.client.remove_objects(bucket_name, targets))

    def _child_folders(self, bucket_name: str, full_prefix: str) -> list[str]:
        """Immediate child folders of ``full_prefix`` (common prefixes only).

        A non-recursive listing returns one entry per child; folders come back
        as common prefixes ending in ``/``. Leaf files (no trailing ``/``) are
        ignored — the walk only descends folders.
        """

        listing = self.client.list_objects(
            bucket_name=bucket_name,
            prefix=full_prefix.rstrip("/") + "/",
            recursive=False,
        )
        return [obj.object_name for obj in listing if obj.object_name.endswith("/")]

    def list_date_folders(
        self,
        base: str,
        *,
        bucket: str | None = None,
    ) -> list[DateFolder]:
        """Discover ``YYYY/MM/DD`` folders directly under the ``base`` anchor.

        ``base`` composes onto ``default_prefix`` like any other key and anchors
        where the date folders begin; the three levels immediately under it are
        treated as year / month / day. Discovery is a three-level *non-recursive*
        walk over common prefixes only — no payload object is listed — so it is
        cheap even when each day holds millions of objects.

        Folder names that don't parse as a zero-padded year (4 digits), month,
        and day (2 digits each) forming a valid calendar date are skipped, so a
        stray ``latest/`` next to the date folders never crashes discovery.
        Returns the folders sorted ascending by date.
        """

        bucket_name = self._resolve_bucket(bucket)
        anchor = self._resolve_key(base)

        folders: list[DateFolder] = []
        for year_path in self._child_folders(bucket_name, anchor):
            year = _parse_segment(year_path, 4)
            if year is None:
                continue
            for month_path in self._child_folders(bucket_name, year_path):
                month = _parse_segment(month_path, 2)
                if month is None:
                    continue
                for day_path in self._child_folders(bucket_name, month_path):
                    day = _parse_segment(day_path, 2)
                    if day is None:
                        continue
                    try:
                        parsed = date(year, month, day)
                    except ValueError:
                        continue
                    folders.append(DateFolder(date=parsed, path=day_path))

        folders.sort(key=lambda f: f.date)
        return folders

    def delete_older_than(
        self,
        days: int,
        base: str,
        *,
        bucket: str | None = None,
        dry_run: bool = False,
    ) -> DeleteOlderResult:
        """Delete date folders under ``base`` older than ``days`` days.

        The cutoff is ``today_KST - days``: a folder dated strictly before the
        cutoff is removed, so the last ``days`` days **including today** are
        kept. Run on 2026-06-17 with ``days=30`` keeps ``2026-05-18`` onward and
        deletes ``2026-05-17`` and earlier.

        ``dry_run=True`` returns the selection (in ``folders``) and an empty
        ``errors`` list without issuing any delete. Otherwise each selected
        day-subtree is listed recursively — server-side narrowed to
        ``anchor/YYYY/MM/DD/`` — and its objects are batched into a single
        ``remove_objects`` call; ``errors`` carries any returned error entries.
        """

        cutoff = _today_kst() - timedelta(days=days)
        selected = [
            f
            for f in self.list_date_folders(base, bucket=bucket)
            if f.date < cutoff
        ]
        if dry_run or not selected:
            return DeleteOlderResult(folders=selected, errors=[])

        bucket_name = self._resolve_bucket(bucket)
        delete_object = _delete_object_class()
        targets = [
            delete_object(obj.object_name)
            for folder in selected
            for obj in self.client.list_objects(
                bucket_name=bucket_name,
                prefix=folder.path,
                recursive=True,
            )
        ]
        errors = (
            list(self.client.remove_objects(bucket_name, targets))
            if targets
            else []
        )
        return DeleteOlderResult(folders=selected, errors=errors)

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

