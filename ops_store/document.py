"""Document CRUD and bulk operations."""

import math
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from functools import lru_cache
from typing import Any, Literal

from .base import OSBase


def _bulk_helper() -> Any:
    from opensearchpy import helpers

    return helpers.bulk


@lru_cache(maxsize=1)
def _pandas_module() -> Any | None:
    try:
        import pandas as pd
    except ImportError:
        return None
    return pd


@lru_cache(maxsize=1)
def _numpy_module() -> Any | None:
    try:
        import numpy as np
    except ImportError:
        return None
    return np


def _is_missing_scalar(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, float):
        return math.isnan(value)

    if isinstance(value, (str, bytes, bytearray, Mapping, list, tuple, set, frozenset)):
        return False

    pandas = _pandas_module()
    if pandas is None:
        return False

    try:
        result = pandas.isna(value)
    except Exception:
        return False

    if isinstance(result, bool):
        return result

    numpy = _numpy_module()
    if numpy is not None and isinstance(result, numpy.bool_):
        return bool(result)

    return False


def _normalize_value(value: Any) -> Any:
    if _is_missing_scalar(value):
        return None

    numpy = _numpy_module()
    if numpy is not None:
        if isinstance(value, numpy.generic):
            return _normalize_value(value.item())
        if isinstance(value, numpy.ndarray):
            if value.ndim == 0:
                return _normalize_value(value.item())
            return [_normalize_value(item) for item in value.tolist()]

    if isinstance(value, Mapping):
        return {str(key): _normalize_value(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]

    if isinstance(value, (set, frozenset)):
        return [_normalize_value(item) for item in value]

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, time):
        return value.isoformat()

    if isinstance(value, timedelta):
        return value.total_seconds()

    if isinstance(value, Decimal):
        if value.is_nan():
            return None
        return float(value)

    return value


def normalize_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a document into a JSON-safe structure for bulk indexing."""

    return {str(key): _normalize_value(value) for key, value in document.items()}


@dataclass(slots=True, frozen=True)
class BulkCreateResult:
    """Outcome of a :meth:`OSDoc.bulk_create` call.

    ``created`` counts documents written, ``skipped`` counts ids that already
    existed (HTTP 409 conflicts, treated as a no-op), and ``errors`` holds any
    remaining bulk-item failures that are *not* id collisions.
    """

    created: int
    skipped: int
    errors: list[Any] = field(default_factory=list)


class OSDoc(OSBase):
    """Class-based wrapper for single-document and bulk document operations."""

    def _run_bulk(
        self,
        actions: Iterable[dict[str, Any]],
        *,
        chunk_size: int,
        refresh: bool,
        raise_on_error: bool,
    ) -> tuple[int, list[Any]]:
        return _bulk_helper()(
            self.client,
            actions,
            chunk_size=chunk_size,
            refresh=refresh,
            raise_on_error=raise_on_error,
        )

    def index(
        self,
        document: Mapping[str, Any],
        *,
        doc_id: str | None = None,
        index: str | None = None,
        normalize: bool = False,
        refresh: str | None = None,
    ) -> dict[str, Any]:
        """Index a single document.

        Set ``normalize=True`` to coerce non-JSON values (datetimes, Decimals,
        NaN, numpy scalars) via :func:`normalize_document` before sending.
        """

        name = self._resolve_index(index)
        kwargs: dict[str, Any] = {
            "index": name,
            "body": normalize_document(document) if normalize else dict(document),
        }
        if doc_id is not None:
            kwargs["id"] = doc_id
        if refresh is not None:
            kwargs["refresh"] = refresh
        return self.client.index(**kwargs)

    def get(self, doc_id: str, *, index: str | None = None) -> dict[str, Any]:
        name = self._resolve_index(index)
        return self.client.get(index=name, id=doc_id)

    def exists_many(
        self,
        doc_ids: Sequence[str],
        *,
        index: str | None = None,
    ) -> dict[str, bool]:
        """Return document existence by id using a single multi-get request."""

        name = self._resolve_index(index)
        ids = list(doc_ids)
        if not ids:
            return {}

        result = {doc_id: False for doc_id in ids}
        response = self.client.mget(
            index=name,
            body={
                "docs": [
                    {
                        "_id": doc_id,
                        "_source": False,
                    }
                    for doc_id in ids
                ]
            },
        )

        for document in response.get("docs", []):
            doc_id = document.get("_id")
            if doc_id in result:
                result[doc_id] = bool(document.get("found"))

        return result

    def get_many(
        self,
        doc_ids: Sequence[str],
        *,
        index: str | None = None,
    ) -> dict[str, dict[str, Any] | None]:
        """Return documents by id using a single multi-get request.

        The returned dict is keyed by the requested id; the value is the
        document's ``_source`` if found, otherwise ``None``.
        """

        name = self._resolve_index(index)
        ids = list(doc_ids)
        if not ids:
            return {}

        result: dict[str, dict[str, Any] | None] = {doc_id: None for doc_id in ids}
        response = self.client.mget(
            index=name,
            body={"docs": [{"_id": doc_id} for doc_id in ids]},
        )

        for document in response.get("docs", []):
            doc_id = document.get("_id")
            if doc_id in result and document.get("found"):
                result[doc_id] = document.get("_source")

        return result

    def update(
        self,
        doc_id: str,
        document: Mapping[str, Any],
        *,
        index: str | None = None,
        normalize: bool = False,
        refresh: str | None = None,
    ) -> dict[str, Any]:
        """Partially update a document.

        Set ``normalize=True`` to coerce non-JSON values (datetimes, Decimals,
        NaN, numpy scalars) via :func:`normalize_document` before sending.
        """

        name = self._resolve_index(index)
        source = normalize_document(document) if normalize else dict(document)
        kwargs: dict[str, Any] = {
            "index": name,
            "id": doc_id,
            "body": {"doc": source},
        }
        if refresh is not None:
            kwargs["refresh"] = refresh
        return self.client.update(**kwargs)

    def upsert(
        self,
        doc_id: str,
        document: Mapping[str, Any],
        *,
        index: str | None = None,
        normalize: bool = False,
        refresh: str | None = None,
    ) -> dict[str, Any]:
        """Update a document, inserting it when the id does not exist yet.

        Set ``normalize=True`` to coerce non-JSON values (datetimes, Decimals,
        NaN, numpy scalars) via :func:`normalize_document` before sending.
        """

        name = self._resolve_index(index)
        source = normalize_document(document) if normalize else dict(document)
        kwargs: dict[str, Any] = {
            "index": name,
            "id": doc_id,
            "body": {"doc": source, "doc_as_upsert": True},
        }
        if refresh is not None:
            kwargs["refresh"] = refresh
        return self.client.update(**kwargs)

    def delete(
        self,
        doc_id: str,
        *,
        index: str | None = None,
        refresh: str | None = None,
    ) -> dict[str, Any]:
        name = self._resolve_index(index)
        kwargs: dict[str, Any] = {
            "index": name,
            "id": doc_id,
        }
        if refresh is not None:
            kwargs["refresh"] = refresh
        return self.client.delete(**kwargs)

    def bulk(
        self,
        actions: Iterable[dict[str, Any]],
        *,
        chunk_size: int | None = None,
        refresh: bool = False,
        raise_on_error: bool = False,
    ) -> tuple[int, list[Any]]:
        actual_chunk_size = chunk_size or (
            self.config.bulk_chunk if self.config is not None else 500
        )
        return self._run_bulk(
            actions,
            chunk_size=actual_chunk_size,
            refresh=refresh,
            raise_on_error=raise_on_error,
        )

    def bulk_index(
        self,
        documents: Sequence[Mapping[str, Any]],
        *,
        index: str | None = None,
        id_field: str | None = None,
        normalize: bool = False,
        chunk_size: int | None = None,
        refresh: bool = False,
        raise_on_error: bool = False,
    ) -> tuple[int, list[Any]]:
        name = self._resolve_index(index)
        actual_chunk_size = chunk_size or (
            self.config.bulk_chunk if self.config is not None else 500
        )

        def iter_actions() -> Iterator[dict[str, Any]]:
            for document in documents:
                source = (
                    normalize_document(document) if normalize else dict(document)
                )
                action: dict[str, Any] = {"_index": name, "_source": source}
                if id_field and id_field in source and source[id_field] is not None:
                    action["_id"] = source[id_field]
                yield action

        return self._run_bulk(
            iter_actions(),
            chunk_size=actual_chunk_size,
            refresh=refresh,
            raise_on_error=raise_on_error,
        )

    def bulk_create(
        self,
        documents: Iterable[Mapping[str, Any]],
        *,
        id_field: str = "_id",
        index: str | None = None,
        normalize: bool = False,
        chunk_size: int | None = None,
        refresh: bool = False,
    ) -> BulkCreateResult:
        """Insert documents under caller-supplied ids, skipping ids already present.

        Each document carries its id under ``id_field`` (default ``"_id"``); that
        key is lifted out to become the document ``_id`` and is **not** stored in
        ``_source``. Uses the bulk ``create`` op type, so a document whose id
        already exists is skipped (HTTP 409) instead of overwriting the existing
        one — making the call safe to re-run. Set ``normalize=True`` to coerce
        non-JSON values (datetimes, Decimals, NaN, numpy scalars) before sending.

        Returns a :class:`BulkCreateResult` separating ``created`` from ``skipped``
        (already-existing) ids, with any non-conflict failures in ``errors``.
        """

        name = self._resolve_index(index)
        actual_chunk_size = chunk_size or (
            self.config.bulk_chunk if self.config is not None else 500
        )

        def iter_actions() -> Iterator[dict[str, Any]]:
            for document in documents:
                source = (
                    normalize_document(document) if normalize else dict(document)
                )
                doc_id = source.pop(id_field, None)
                action: dict[str, Any] = {
                    "_op_type": "create",
                    "_index": name,
                    "_id": str(doc_id),
                    "_source": source,
                }
                yield action

        created, raw_errors = self._run_bulk(
            iter_actions(),
            chunk_size=actual_chunk_size,
            refresh=refresh,
            raise_on_error=False,
        )

        skipped = 0
        errors: list[Any] = []
        for item in raw_errors:
            status = item.get("create", {}).get("status") if isinstance(item, Mapping) else None
            if status == 409:
                skipped += 1
            else:
                errors.append(item)

        return BulkCreateResult(created=created, skipped=skipped, errors=errors)

    def bulk_index_dataframe(
        self,
        dataframe: Any,
        *,
        index: str | None = None,
        id_field: str | None = None,
        op_type: Literal["index", "create"] | None = None,
        chunk_size: int | None = None,
        refresh: bool = False,
        raise_on_error: bool = False,
    ) -> tuple[int, list[Any]]:
        name = self._resolve_index(index)
        actual_chunk_size = chunk_size or (
            self.config.bulk_chunk if self.config is not None else 500
        )
        columns = list(dataframe.columns)

        def iter_actions() -> Iterator[dict[str, Any]]:
            for row in dataframe.itertuples(index=False, name=None):
                source = normalize_document(dict(zip(columns, row)))
                action: dict[str, Any] = {"_index": name, "_source": source}

                if op_type is not None:
                    action["_op_type"] = op_type

                if id_field and id_field in source and source[id_field] is not None:
                    action["_id"] = str(source[id_field])

                yield action

        return self._run_bulk(
            iter_actions(),
            chunk_size=actual_chunk_size,
            refresh=refresh,
            raise_on_error=raise_on_error,
        )
