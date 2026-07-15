"""Create the member_info directory index and its mappings.

Unlike the measurement-history indices in this package, member_info is a
*lookup table*, not append-only time-series: a few-thousand-row employee
roster that is refreshed in place. So there is no rollover family and no ISM
retention policy -- a single concrete index, upserted by EMP_NO (use EMP_NO as
the document _id so re-ingesting the roster overwrites instead of duplicating).

Search design:
  - Exact-identity fields (USER_ID, EMP_NO, EMAIL, RESV014) are `keyword`:
    term-looked-up in filter context, cached, near-instant.
  - Human-readable org/name fields are `keyword` AND copied into `search_all`
    so a single search box can match them.
  - RESP_CONT -- the freely written job description -- is `text` analyzed with
    `nori` (Korean morphological analysis strips particles/조사 and splits
    compounds, so "검사" matches "검사를"/"장비 검사"). It is also copied into
    `search_all`.
  - `search_all` is the combined nori field that powers one-box search across
    name + department + part + job + job-description. (No leading underscore:
    OpenSearch reserves `_`-prefixed names for metadata fields.)

Querying:
  - Search the analyzed fields with `match` / `multi_match` (e.g. on
    `search_all` or `RESP_CONT`). RESP_CONT is free text people write in their
    own way -- newlines, "-", "*", quotes, slashes, parens, emoji. Storage is
    unaffected (JSON escapes every character; `_source` round-trips byte-for-
    byte), and a `match` query runs the user's input through nori too, so that
    punctuation is just tokenized away -- never an operator, never a parse error.
  - Do NOT feed raw user input to `query_string` / `simple_query_string`: those
    reserve `+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \\ /`, so a stray "-" or
    "*" becomes an operator (or throws). Keep the search box on `match`.
  - `RESP_CONT.keyword` holds the whole description as one term (capped at
    `ignore_above`); it is for aggregation/sorting, not free-text search -- the
    real search goes through the analyzed `text` / `search_all` path.

This module only *builds the index*. Roster ingest, prune, and the scheduled
refresh live in `member_info_ingest.py`, which imports INDEX_NAME / ID_FIELD
from here so the index definition stays the single source of truth.
"""

import argparse
import json
from typing import Any

from ops_store import OSIndex, create_client

OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""

INDEX_NAME = "member_info"

SHARDS = 1
REPLICAS = 1

# EMP_NO is the natural key; ingest passes it as the document _id so a roster
# refresh upserts each person instead of appending duplicates. Lives here (with
# the index definition) and is imported by member_info_ingest.
ID_FIELD = "EMP_NO"

# Combined field that one search box queries; the fields below copy into it.
SEARCH_ALL_FIELD = "search_all"

# Exact-identity fields: term lookups / filters only, never full-text.
KEYWORD_FIELDS = ("USER_ID", "EMP_NO", "EMAIL", "RESV014")

# Human-readable fields: exact filter + faceting via keyword, AND fed into the
# combined search box via copy_to.
SEARCHABLE_KEYWORD_FIELDS = (
    "NAME_KOR",
    "DEPT_NAME_KOR",
    "PART_NAME_KO",
    "JOB_NAME_KOR",
    "DEPT_PATH_KOR",
)

# Free-written Korean text: the one true full-text field.
NORI_TEXT_FIELDS = ("RESP_CONT",)

# 8192 chars * 3 bytes (Korean UTF-8) stays under Lucene's 32766-byte term cap.
TEXT_KEYWORD_IGNORE_ABOVE = 8192


def build_mappings() -> dict[str, Any]:
    """Return the explicit mapping for the declared member fields.

    Columns not enumerated here fall through to the dynamic templates:
    `*_tm`/`*_dt` become dates, everything else stays a keyword (member rows
    are mostly codes and short labels, so keyword is the right default).
    """

    properties: dict[str, Any] = {
        SEARCH_ALL_FIELD: {"type": "text", "analyzer": "nori"},
        # KST timestamp refreshed on every upsert; "last refreshed in OS", not
        # "first landed". Does not end in `_tm`/`_dt`, so mapped explicitly.
        "os_inserted": {"type": "date"},
    }

    for field in KEYWORD_FIELDS:
        properties[field] = {"type": "keyword"}

    for field in SEARCHABLE_KEYWORD_FIELDS:
        properties[field] = {
            "type": "keyword",
            "copy_to": SEARCH_ALL_FIELD,
        }

    for field in NORI_TEXT_FIELDS:
        properties[field] = {
            "type": "text",
            "analyzer": "nori",
            "copy_to": SEARCH_ALL_FIELD,
            "fields": {
                "keyword": {
                    "type": "keyword",
                    "ignore_above": TEXT_KEYWORD_IGNORE_ABOVE,
                }
            },
        }

    return {
        "properties": properties,
        "dynamic_templates": [
            {
                "tm_suffix_as_date": {
                    "match_mapping_type": "string",
                    "match": "*_tm",
                    "mapping": {"type": "date"},
                }
            },
            {
                "dt_suffix_as_date": {
                    "match_mapping_type": "string",
                    "match": "*_dt",
                    "mapping": {"type": "date"},
                }
            },
            {
                "strings_as_keyword": {
                    "match_mapping_type": "string",
                    "mapping": {"type": "keyword"},
                }
            },
        ],
    }


def build_index_settings() -> dict[str, Any]:
    """Return the settings for the single member_info index."""

    return {
        "number_of_shards": SHARDS,
        "number_of_replicas": REPLICAS,
    }


def build_index_body() -> dict[str, Any]:
    """Return the create-index body (settings + mappings)."""

    return {
        "settings": build_index_settings(),
        "mappings": build_mappings(),
    }


def create_skewnono_client() -> Any:
    """Create a client for the skewnono OpenSearch cluster."""

    if not OPENSEARCH_PASSWORD:
        raise RuntimeError(
            "Set OPENSEARCH_PASSWORD at the top of "
            "ops_index_mgmt/member_info.py before running this script."
        )

    return create_client(
        host=OPENSEARCH_HOST,
        user=OPENSEARCH_USER,
        password=OPENSEARCH_PASSWORD,
    )


def ensure_member_info_index(client: Any) -> dict[str, Any]:
    """Create the member_info index if it does not already exist."""

    index_service = OSIndex(client=client, index=INDEX_NAME)
    if index_service.exists(INDEX_NAME, include_aliases=False):
        return {"created": False, "index": INDEX_NAME}

    response = index_service.create(
        index=INDEX_NAME,
        settings=build_index_settings(),
        mappings=build_mappings(),
        shards=SHARDS,
        replicas=REPLICAS,
    )
    return {"created": True, "index": INDEX_NAME, "response": response}


def build_dry_run_plan() -> dict[str, Any]:
    """Return the request this script will send without connecting."""

    return {
        "cluster": {
            "host": OPENSEARCH_HOST,
            "user": OPENSEARCH_USER,
            "password_set": bool(OPENSEARCH_PASSWORD),
        },
        "id_field": ID_FIELD,
        "index_request": {
            "method": "PUT",
            "path": f"/{INDEX_NAME}",
            "body": build_index_body(),
        },
    }


def setup_member_info(client: Any | None = None) -> dict[str, Any]:
    """Create the member_info index if it is missing."""

    actual_client = client or create_skewnono_client()
    return {"index": ensure_member_info_index(actual_client)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create the member_info directory index with nori full-text on "
            "RESP_CONT and a search_all combined search field."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the OpenSearch request without connecting to the cluster.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run:
        result = build_dry_run_plan()
    else:
        result = setup_member_info()

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
