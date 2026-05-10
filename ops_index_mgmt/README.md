# ops_index_mgmt

Operational OpenSearch index setup scripts.

## SEM MSR info indices

`hitachi_sem_msr_info.py` creates:

- shared ISM policy `sem_msr_info_retention_policy`
- index template `cdsem_msr_info_template`
- index template `hvsem_msr_info_template`
- first backing index `cdsem_msr_info-000001`
- first backing index `hvsem_msr_info-000001`
- write/search alias `cdsem_msr_info`
- write/search alias `hvsem_msr_info`

Settings:

- primary shards: `3`
- replicas: `1`
- rollover: `15gb` total primary shard storage
- retention: delete backing indices after `50d`

Connection values are declared near the top of
`ops_index_mgmt/hitachi_sem_msr_info.py`:

```python
OPENSEARCH_HOST = "skewnono-db1-os.osp01.skhynix.com"
OPENSEARCH_USER = "skewnono001"
OPENSEARCH_PASSWORD = ""
```

Set `OPENSEARCH_PASSWORD` before running the script.

```bash
python -m ops_index_mgmt.hitachi_sem_msr_info --dry-run
python -m ops_index_mgmt.hitachi_sem_msr_info
```

The aliases `cdsem_msr_info` and `hvsem_msr_info` should be used by ingest and
query code. OpenSearch writes to the current backing index through each alias
and rolls them to `cdsem_msr_info-000002`, `hvsem_msr_info-000002`, and so on.

Retention is index-age based. It removes whole backing indices after 50 days,
so exact document-level expiry depends on how much time each backing index spans.

## Application logging index

`skewnono_logging.py` creates the production logging index family:

- shared ISM policy `skewnono_logging_retention_policy`
- index template `skewnono_logging_template` (with mappings for log fields)
- first backing index `skewnono_logging-000001`
- write/search alias `skewnono_logging`

Settings:

- primary shards: `2`
- replicas: `1` (one shard copy per node across the 4-node cluster)
- rollover: `20gb` total primary shard storage **or** `7d` index age
- retention: delete backing indices after `30d`

The Flask backend writes to the `skewnono_logging` alias when running in
production mode (`is_cloud()` is true) via
`back_dev_home._logging.opensearch_handler.OpenSearchBulkHandler`. Connection
values come from environment variables (`OPENSEARCH_HOST`,
`OPENSEARCH_USER`, `OPENSEARCH_PASSWORD`, optionally `OPENSEARCH_PORT`,
`OPENSEARCH_USE_SSL`, `OPENSEARCH_VERIFY_CERTS`) — see `ops_store/base.py`
`OSConfig.from_env`.

Set `OPENSEARCH_PASSWORD` near the top of the script before running it:

```bash
python -m ops_index_mgmt.skewnono_logging --dry-run
python -m ops_index_mgmt.skewnono_logging
```

Run the script once per cluster the application talks to. ISM policies and
index templates are cluster-scoped, so each of the 3 OpenSearch clusters
needs its own setup invocation.

## Elasticsearch → OpenSearch reindex

`es_to_os_reindex.py` copies one ES index into one OpenSearch index using the
ES scroll API on the read side and `ops_store.OSDoc.bulk` on the write side.
Document ids are preserved, so re-runs overwrite rather than duplicate.

Set both clusters' connection consts at the top of the file (`ES_*` and
`OPENSEARCH_*`), then:

```bash
# Inspect what would happen — no cluster contact.
python -m ops_index_mgmt.es_to_os_reindex --dry-run \
    --source-index my_es_index --dest-index my_os_index

# Run the migration.
python -m ops_index_mgmt.es_to_os_reindex \
    --source-index my_es_index --dest-index my_os_index

# Filter with an ES query DSL fragment.
python -m ops_index_mgmt.es_to_os_reindex \
    --source-index my_es_index --dest-index my_os_index \
    --query '{"range":{"@timestamp":{"gte":"2026-01-01"}}}'
```

The destination index must already exist with the desired mapping/settings —
this script copies documents, not index metadata. Create the destination
index (or its template + write alias) ahead of time.

Requires the `elasticsearch` Python package on the source side in addition to
`opensearch-py` on the destination side. The source cluster is Elasticsearch
7.x, so pin the client to the matching major to avoid the 8.x product-check:

```bash
pip install "elasticsearch>=7,<8"
```
