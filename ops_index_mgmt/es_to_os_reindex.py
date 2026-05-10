"""Stream documents from an Elasticsearch index into an OpenSearch index.

Read with the Elasticsearch scroll API, write with `ops_store.OSDoc.bulk`.
Document ids are preserved so re-runs are idempotent (same id => overwrite).
"""

import argparse
import json
from collections.abc import Iterator
from typing import Any

from ops_store import OSDoc, create_client

# --- source: Elasticsearch (the cluster being shut down) ---
ES_HOST = "es-host.example.com"
ES_PORT = 9200
ES_USER = "elastic"
ES_PASSWORD = ""
ES_USE_SSL = True
ES_VERIFY_CERTS = False

# --- destination: OpenSearch ---
OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

# --- migration knobs ---
SOURCE_INDEX = "my_es_index"
DEST_INDEX = "my_os_index"
SCROLL_SIZE = 1000          # docs per scroll page (read side)
BULK_CHUNK = 500            # docs per bulk request (write side)
SCROLL_KEEPALIVE = "5m"
PROGRESS_EVERY = 10_000


def _elasticsearch_module() -> Any:
    import elasticsearch

    return elasticsearch


def _es_scan_helper() -> Any:
    from elasticsearch import helpers

    return helpers.scan


def create_es_client() -> Any:
    """Connect to the source Elasticsearch cluster."""

    if not ES_PASSWORD:
        raise RuntimeError(
            "Set ES_PASSWORD at the top of "
            "ops_index_mgmt/es_to_os_reindex.py before running this script."
        )

    elasticsearch = _elasticsearch_module()
    scheme = "https" if ES_USE_SSL else "http"
    return elasticsearch.Elasticsearch(
        hosts=[{"host": ES_HOST, "port": ES_PORT, "scheme": scheme}],
        http_auth=(ES_USER, ES_PASSWORD),
        verify_certs=ES_VERIFY_CERTS,
        ssl_show_warn=False,
        timeout=60,
        max_retries=3,
        retry_on_timeout=True,
    )


def create_os_client() -> Any:
    """Connect to the destination OpenSearch cluster."""

    if not OPENSEARCH_PASSWORD:
        raise RuntimeError(
            "Set OPENSEARCH_PASSWORD at the top of "
            "ops_index_mgmt/es_to_os_reindex.py before running this script."
        )

    return create_client(
        host=OPENSEARCH_HOST,
        user=OPENSEARCH_USER,
        password=OPENSEARCH_PASSWORD,
    )


def iter_source_actions(
    es_client: Any,
    *,
    source_index: str,
    dest_index: str,
    query: dict[str, Any] | None = None,
    scroll_size: int = SCROLL_SIZE,
    scroll_keepalive: str = SCROLL_KEEPALIVE,
) -> Iterator[dict[str, Any]]:
    """Yield bulk actions rewritten for the destination OpenSearch index."""

    scan = _es_scan_helper()
    body = {"query": query} if query else None
    for hit in scan(
        es_client,
        index=source_index,
        query=body,
        size=scroll_size,
        scroll=scroll_keepalive,
        preserve_order=False,
        request_timeout=120,
    ):
        action: dict[str, Any] = {
            "_index": dest_index,
            "_id": hit["_id"],
            "_source": hit["_source"],
        }
        routing = hit.get("_routing")
        if routing is not None:
            action["routing"] = routing
        yield action


def reindex_es_to_os(
    *,
    source_index: str = SOURCE_INDEX,
    dest_index: str = DEST_INDEX,
    query: dict[str, Any] | None = None,
    scroll_size: int = SCROLL_SIZE,
    bulk_chunk: int = BULK_CHUNK,
    refresh: bool = False,
    raise_on_error: bool = False,
    progress_every: int = PROGRESS_EVERY,
    es_client: Any | None = None,
    os_client: Any | None = None,
) -> dict[str, Any]:
    """Copy every document matching `query` from ES to OpenSearch."""

    actual_es = es_client or create_es_client()
    actual_os = os_client or create_os_client()

    source_total = actual_es.count(
        index=source_index,
        body={"query": query} if query else None,
    ).get("count")

    doc_service = OSDoc(client=actual_os)

    seen = 0
    failures: list[Any] = []

    def counting_actions() -> Iterator[dict[str, Any]]:
        nonlocal seen
        for action in iter_source_actions(
            actual_es,
            source_index=source_index,
            dest_index=dest_index,
            query=query,
            scroll_size=scroll_size,
        ):
            seen += 1
            if progress_every and seen % progress_every == 0:
                print(
                    f"[{source_index} -> {dest_index}] streamed {seen} docs",
                    flush=True,
                )
            yield action

    success, errors = doc_service.bulk(
        counting_actions(),
        chunk_size=bulk_chunk,
        refresh=refresh,
        raise_on_error=raise_on_error,
    )
    failures.extend(errors)

    return {
        "source_index": source_index,
        "dest_index": dest_index,
        "source_total": source_total,
        "streamed": seen,
        "indexed": success,
        "failed": len(failures),
        "errors": failures[:10],
    }


def build_dry_run_plan(
    *,
    source_index: str,
    dest_index: str,
    query: dict[str, Any] | None,
    scroll_size: int,
    bulk_chunk: int,
) -> dict[str, Any]:
    """Describe what the migration will do without contacting either cluster."""

    return {
        "source": {
            "host": ES_HOST,
            "port": ES_PORT,
            "user": ES_USER,
            "password_set": bool(ES_PASSWORD),
            "index": source_index,
            "query": query,
            "scroll_size": scroll_size,
            "scroll_keepalive": SCROLL_KEEPALIVE,
        },
        "destination": {
            "host": OPENSEARCH_HOST,
            "user": OPENSEARCH_USER,
            "password_set": bool(OPENSEARCH_PASSWORD),
            "index": dest_index,
            "bulk_chunk": bulk_chunk,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reindex documents from an Elasticsearch source index into an "
            "OpenSearch destination index using scroll + bulk."
        )
    )
    parser.add_argument("--source-index", default=SOURCE_INDEX)
    parser.add_argument("--dest-index", default=DEST_INDEX)
    parser.add_argument(
        "--query",
        default=None,
        help='Optional ES query DSL JSON, e.g. \'{"match_all":{}}\'.',
    )
    parser.add_argument("--scroll-size", type=int, default=SCROLL_SIZE)
    parser.add_argument("--bulk-chunk", type=int, default=BULK_CHUNK)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh the destination index after the run completes.",
    )
    parser.add_argument(
        "--raise-on-error",
        action="store_true",
        help="Stop and raise on the first bulk error instead of collecting them.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    query = json.loads(args.query) if args.query else None

    if args.dry_run:
        result = build_dry_run_plan(
            source_index=args.source_index,
            dest_index=args.dest_index,
            query=query,
            scroll_size=args.scroll_size,
            bulk_chunk=args.bulk_chunk,
        )
    else:
        result = reindex_es_to_os(
            source_index=args.source_index,
            dest_index=args.dest_index,
            query=query,
            scroll_size=args.scroll_size,
            bulk_chunk=args.bulk_chunk,
            refresh=args.refresh,
            raise_on_error=args.raise_on_error,
        )

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
