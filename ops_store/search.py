"""Search-oriented wrappers for OpenSearch queries."""

from collections.abc import Sequence
from functools import lru_cache
from typing import Any

from opensearchpy.exceptions import NotFoundError

from .base import OSBase


@lru_cache(maxsize=1)
def _pandas_module() -> Any | None:
    try:
        import pandas as pd
    except ImportError:
        return None
    return pd


def _hit_to_record(hit: dict[str, Any], *, include_meta: bool) -> dict[str, Any]:
    source = hit.get("_source")
    if isinstance(source, dict):
        record = dict(source)
    else:
        fields = hit.get("fields")
        record = dict(fields) if isinstance(fields, dict) else {}

    if include_meta:
        for key in ("_id", "_index", "_score"):
            if key in hit:
                record[key] = hit[key]

    return record


def _hits_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    hits = result.get("hits")
    raw_hits = hits.get("hits") if isinstance(hits, dict) else []
    return [hit for hit in raw_hits if isinstance(hit, dict)]


def _records_from_hits(
    hits: Sequence[dict[str, Any]],
    *,
    include_meta: bool,
) -> list[dict[str, Any]]:
    return [_hit_to_record(hit, include_meta=include_meta) for hit in hits]


def _require_pandas() -> Any:
    pandas = _pandas_module()
    if pandas is None:
        raise ImportError(
            "pandas is required for OSSearch DataFrame helpers. "
            "Install pandas to use these helpers."
        )
    return pandas


def _records_to_dataframe(records: list[dict[str, Any]]) -> Any:
    pandas = _require_pandas()
    return pandas.DataFrame(records)


_DATE_TYPES = frozenset({"date", "date_nanos"})


def _lookup_mapped_field(
    properties: dict[str, Any], dotted_path: str
) -> dict[str, Any] | None:
    parts = dotted_path.split(".")
    current: Any = properties
    for depth, part in enumerate(parts):
        if not isinstance(current, dict):
            return None
        field_def = current.get(part)
        if not isinstance(field_def, dict):
            return None
        if depth == len(parts) - 1:
            return field_def
        current = field_def.get("properties")
    return None


class OSSearch(OSBase):
    """Class-based query helper for lexical, vector, and raw searches."""

    def search_raw(
        self,
        body: dict[str, Any],
        *,
        index: str | None = None,
    ) -> dict[str, Any]:
        name = self._resolve_index(index)
        return self.client.search(index=name, body=body)

    def to_dataframe(
        self,
        result: dict[str, Any],
        *,
        include_meta: bool = False,
    ) -> Any:
        records = _records_from_hits(
            _hits_from_result(result),
            include_meta=include_meta,
        )
        return _records_to_dataframe(records)

    def _search_all_hits(
        self,
        body: dict[str, Any],
        *,
        index: str | None = None,
        batch_size: int = 1000,
        scroll: str = "2m",
    ) -> list[dict[str, Any]]:
        name = self._resolve_index(index)
        request_body = dict(body)
        request_body["size"] = batch_size

        response = self.client.search(index=name, body=request_body, scroll=scroll)
        scroll_id = response.get("_scroll_id")
        page_hits = _hits_from_result(response)
        all_hits = list(page_hits)

        try:
            while page_hits and scroll_id is not None:
                response = self.client.scroll(scroll_id=scroll_id, scroll=scroll)
                next_scroll_id = response.get("_scroll_id")
                if next_scroll_id is not None:
                    scroll_id = next_scroll_id
                page_hits = _hits_from_result(response)
                all_hits.extend(page_hits)
        finally:
            if scroll_id is not None:
                self.client.clear_scroll(scroll_id=scroll_id)

        return all_hits

    def search_dataframe(
        self,
        body: dict[str, Any],
        *,
        index: str | None = None,
        include_meta: bool = False,
    ) -> Any:
        result = self.search_raw(body, index=index)
        return self.to_dataframe(result, include_meta=include_meta)

    def search_dataframe_all(
        self,
        body: dict[str, Any],
        *,
        index: str | None = None,
        batch_size: int = 1000,
        scroll: str = "2m",
        include_meta: bool = False,
    ) -> Any:
        _require_pandas()
        all_hits = self._search_all_hits(
            body,
            index=index,
            batch_size=batch_size,
            scroll=scroll,
        )
        return _records_to_dataframe(
            _records_from_hits(all_hits, include_meta=include_meta)
        )

    def count(
        self,
        query: dict[str, Any] | None = None,
        *,
        index: str | None = None,
    ) -> dict[str, Any]:
        body = {"query": query} if query else {}
        name = self._resolve_index(index)
        return self.client.count(index=name, body=body)

    def match(
        self,
        field: str,
        query: str,
        *,
        index: str | None = None,
        size: int = 10,
    ) -> dict[str, Any]:
        body = {"query": {"match": {field: query}}, "size": size}
        return self.search_raw(body, index=index)

    def match_dataframe(
        self,
        field: str,
        query: str,
        *,
        index: str | None = None,
        size: int = 10,
        include_meta: bool = False,
    ) -> Any:
        result = self.match(field, query, index=index, size=size)
        return self.to_dataframe(result, include_meta=include_meta)

    def match_dataframe_all(
        self,
        field: str,
        query: str,
        *,
        index: str | None = None,
        batch_size: int = 1000,
        scroll: str = "2m",
        include_meta: bool = False,
    ) -> Any:
        body = {"query": {"match": {field: query}}}
        return self.search_dataframe_all(
            body,
            index=index,
            batch_size=batch_size,
            scroll=scroll,
            include_meta=include_meta,
        )

    def term(
        self,
        field: str,
        value: Any,
        *,
        index: str | None = None,
        size: int = 10,
    ) -> dict[str, Any]:
        body = {"query": {"term": {field: value}}, "size": size}
        return self.search_raw(body, index=index)

    def bool(
        self,
        *,
        must: list[dict[str, Any]] | None = None,
        should: list[dict[str, Any]] | None = None,
        filter: list[dict[str, Any]] | None = None,
        must_not: list[dict[str, Any]] | None = None,
        index: str | None = None,
        size: int = 10,
    ) -> dict[str, Any]:
        bool_clause: dict[str, Any] = {}
        if must:
            bool_clause["must"] = must
        if should:
            bool_clause["should"] = should
        if filter:
            bool_clause["filter"] = filter
        if must_not:
            bool_clause["must_not"] = must_not

        body = {"query": {"bool": bool_clause}, "size": size}
        return self.search_raw(body, index=index)

    def filter_terms(
        self,
        filters: dict[str, Sequence[Any]],
        *,
        minimum_should_match: int | str | None = None,
        query: dict[str, Any] | None = None,
        index: str | None = None,
        size: int = 10,
    ) -> dict[str, Any]:
        term_clauses = [
            {"terms": {field: list(values)}}
            for field, values in filters.items()
            if values
        ]

        if term_clauses and minimum_should_match is not None:
            filter_clauses = [
                {
                    "bool": {
                        "should": term_clauses,
                        "minimum_should_match": minimum_should_match,
                    }
                }
            ]
        else:
            filter_clauses = term_clauses

        return self.bool(
            must=[query] if query is not None else None,
            filter=filter_clauses or None,
            index=index,
            size=size,
        )

    def multi_match(
        self,
        query: str,
        fields: Sequence[str],
        *,
        index: str | None = None,
        size: int = 10,
        match_type: str = "best_fields",
    ) -> dict[str, Any]:
        body = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": list(fields),
                    "type": match_type,
                }
            },
            "size": size,
        }
        return self.search_raw(body, index=index)

    def knn(
        self,
        field: str,
        vector: Sequence[float],
        *,
        index: str | None = None,
        k: int = 5,
        size: int = 10,
        filters: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        filter_list = list(filters or [])
        knn_query = {"knn": {field: {"vector": list(vector), "k": k}}}
        if filter_list:
            body = {
                "query": {
                    "bool": {
                        "must": [knn_query],
                        "filter": filter_list,
                    }
                },
                "size": size,
            }
        else:
            body = {"query": knn_query, "size": size}

        return self.search_raw(body, index=index)

    def hybrid(
        self,
        query: str,
        *,
        text_field: str,
        vector_field: str,
        vector: Sequence[float],
        index: str | None = None,
        k: int = 5,
        size: int = 10,
        filters: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        bool_clause: dict[str, Any] = {
            "should": [
                {"match": {text_field: query}},
                {"knn": {vector_field: {"vector": list(vector), "k": k}}},
            ],
            "minimum_should_match": 1,
        }

        filter_list = list(filters or [])
        if filter_list:
            bool_clause["filter"] = filter_list

        body = {"query": {"bool": bool_clause}, "size": size}
        return self.search_raw(body, index=index)

    def _require_date_field(self, index: str, time_field: str) -> None:
        mapping = self.client.indices.get_mapping(index=index)
        for backing_index, index_data in mapping.items():
            properties = index_data.get("mappings", {}).get("properties", {})
            field_def = _lookup_mapped_field(properties, time_field)
            if field_def is None:
                raise ValueError(
                    f"Field {time_field!r} not found in mapping for "
                    f"index {backing_index!r}."
                )
            field_type = field_def.get("type")
            if field_type not in _DATE_TYPES:
                raise ValueError(
                    f"Field {time_field!r} in index {backing_index!r} has "
                    f"type {field_type!r}; expected 'date' or 'date_nanos'."
                )

    def latest(
        self,
        time_field: str,
        *,
        index: str | None = None,
        size: int = 1,
        query: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        resolved_index = self._resolve_index(index)
        try:
            self._require_date_field(resolved_index, time_field)
        except NotFoundError:
            return None
        body: dict[str, Any] = {
            "sort": [{time_field: {"order": "desc"}}],
            "size": size,
        }
        if query is not None:
            body["query"] = query
        try:
            return self.search_raw(body, index=resolved_index)
        except NotFoundError:
            return None

    def sample(
        self,
        *,
        index: str | None = None,
        size: int = 10,
        query: dict[str, Any] | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        random_score: dict[str, Any] = {}
        if seed is not None:
            random_score = {"seed": seed, "field": "_seq_no"}

        base_query = query if query is not None else {"match_all": {}}
        body = {
            "size": size,
            "query": {
                "function_score": {
                    "query": base_query,
                    "random_score": random_score,
                }
            },
        }
        return self.search_raw(body, index=index)

    def unique_values(
        self,
        field: str,
        *,
        index: str | None = None,
        size: int = 10000,
        query: dict[str, Any] | None = None,
    ) -> list[Any]:
        result = self.aggregate(
            {"unique_values": {"terms": {"field": field, "size": size}}},
            query=query,
            index=index,
        )
        buckets = result.get("aggregations", {}).get("unique_values", {}).get("buckets", [])
        return [bucket["key"] for bucket in buckets]

    def aggregate(
        self,
        aggregations: dict[str, Any],
        *,
        query: dict[str, Any] | None = None,
        index: str | None = None,
        size: int = 0,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"aggs": aggregations, "size": size}
        if query is not None:
            body["query"] = query
        return self.search_raw(body, index=index)
