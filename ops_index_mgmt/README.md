# ops_index_mgmt

Operational OpenSearch index setup scripts.

## SEM MSR info indices

`hitachi_sem_msr_info.py` creates:

- shared ISM policy `sem_meas_hist_retention_policy`
- index template `meas_hist_cdsem_template`
- index template `meas_hist_hvsem_template`
- first backing index `meas_hist_cdsem-000001`
- first backing index `meas_hist_hvsem-000001`
- write/search alias `meas_hist_cdsem`
- write/search alias `meas_hist_hvsem`

Settings:

- primary shards: `3`
- replicas: `1`
- rollover: backing index age reaches `60d`
- retention: delete backing indices after `365d`

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

The aliases `meas_hist_cdsem` and `meas_hist_hvsem` should be used by ingest and
query code. OpenSearch writes to the current backing index through each alias
and rolls them to `meas_hist_cdsem-000002`, `meas_hist_hvsem-000002`, and so on.

Rollover and retention are index-age based. The policy rolls each backing index
after 60 days and removes whole backing indices after 365 days, so exact
document-level expiry depends on how much time each backing index spans.

After the aliases exist, pandas DataFrames can be inserted through
`ops_store.OSDoc.bulk_index_dataframe()`:

```python
from ops_store import OSDoc

doc_service = OSDoc(client=client)

doc_service.bulk_index_dataframe(
    cdsem_df,
    index="meas_hist_cdsem",
    id_field="doc_id",
    op_type="create",
)
doc_service.bulk_index_dataframe(
    hvsem_df,
    index="meas_hist_hvsem",
    id_field="doc_id",
    op_type="create",
)
```

## fab_inform_notes index

`fab_inform_notes.py` creates:

- ISM policy `fab_inform_notes_retention_policy`
- index template `fab_inform_notes_template`
- first backing index `fab_inform_notes-000001`
- write/search alias `fab_inform_notes`

Settings:

- primary shards: `2`
- replicas: `1`
- rollover: write index reaches `1000000` docs
- retention: delete backing indices after `1095d` (3 years)

Field mapping highlights:

- ISO timestamp columns (`down_dt`, `equp_dt`, `up_dt`, `hub_load_tm`) →
  `date` (default `strict_date_optional_time||epoch_millis` format)
- Worker note columns (`note_comment`, `zzproblem`, `hltext`) → `text`
  analyzed with `nori` plus a `.keyword` subfield with `ignore_above:
  8192` for exact-match / sort / dedup
- `dynamic` stays at the default (`true`) — other columns auto-map

```bash
python -m ops_index_mgmt.fab_inform_notes --dry-run
python -m ops_index_mgmt.fab_inform_notes
```

Ingest dataframes through the `fab_inform_notes` alias:

```python
from ops_store import OSDoc

doc_service = OSDoc(client=client)
doc_service.bulk_index_dataframe(
    notes_df,
    index="fab_inform_notes",
    id_field="doc_id",
    op_type="create",
)
```

## tool_maintenance_plan index

`tool_maintenance_plan.py` is the second-of-a-kind setup script — same
rollover/retention shape as `fab_inform_notes`, different columns:

- date columns: `tool_start_tm`, `tool_end_tm`, `ll_dt`, `limit_dt`,
  `org_dt`, `chg_tm`
- engineer note column: `work_item_nm` (nori + `.keyword` subfield with
  `ignore_above: 8192`)

Same settings (`2` shards, `1` replica, `1000000`-doc rollover, `1095d`
retention) but its own ISM policy `tool_maintenance_plan_retention_policy`
and template `tool_maintenance_plan_template`.

```bash
python -m ops_index_mgmt.tool_maintenance_plan --dry-run
python -m ops_index_mgmt.tool_maintenance_plan
```

## ebeam_tas_lot_hist index

`ebeam_tas_lot_hist.py` sets up a 1-year retention rollover family with
dual-condition rollover (size OR age):

- primary shards: `2`, replicas: `2`
- rollover: write index reaches `1000000` docs **or** `90d` age (whichever
  comes first)
- retention: delete backing indices after `365d`

No explicit per-field mappings. Two `dynamic_templates` auto-type any
incoming column ending in `_tm` or `_dt` as `date` so ISO-8601 timestamps
land as proper dates (OpenSearch's built-in dynamic date detection only
catches `yyyy/MM/dd` style strings). Everything else falls through to
default dynamic mapping.

```bash
python -m ops_index_mgmt.ebeam_tas_lot_hist --dry-run
python -m ops_index_mgmt.ebeam_tas_lot_hist
```

## hitachi_idp_ver indices (cdsem + hvsem)

`hitachi_idp_ver.py` creates two rollover families that share one ISM
policy — same shape as `hitachi_sem_msr_info.py` but with a doc-count
rollover and 3-year retention:

- shared ISM policy `hitachi_idp_ver_retention_policy`
- index template `cdsem_idp_ver_template`
- index template `hvsem_idp_ver_template`
- first backing index `cdsem_idp_ver-000001`
- first backing index `hvsem_idp_ver-000001`
- write/search alias `cdsem_idp_ver`
- write/search alias `hvsem_idp_ver`

Settings:

- primary shards: `2`
- replicas: `1`
- rollover: write index reaches `1000000` docs
- retention: delete backing indices after `1095d` (3 years)

Field mapping:

- `modified` → `date` (explicit, since ISO-8601 strings would otherwise
  be auto-mapped as `text`)
- any `*_tm` / `*_dt` columns → `date` via `dynamic_templates`
- everything else falls through to default dynamic mapping

```bash
python -m ops_index_mgmt.hitachi_idp_ver --dry-run
python -m ops_index_mgmt.hitachi_idp_ver
```

Ingest dataframes through each alias separately:

```python
from ops_store import OSDoc

doc_service = OSDoc(client=client)
doc_service.bulk_index_dataframe(
    cdsem_df, index="cdsem_idp_ver", id_field="doc_id", op_type="create",
)
doc_service.bulk_index_dataframe(
    hvsem_df, index="hvsem_idp_ver", id_field="doc_id", op_type="create",
)
```

## beam_shape_cdsem + reso_center_cdsem indices

`beam_reso_cdsem.py` creates two low-volume CD-SEM measurement families
that **share one ISM policy** — same shape as `hitachi_idp_ver.py`, but
with per-alias mappings:

- shared ISM policy `beam_reso_cdsem_retention_policy`
- index template `beam_shape_cdsem_template`
- index template `reso_center_cdsem_template`
- first backing index `beam_shape_cdsem-000001`
- first backing index `reso_center_cdsem-000001`
- write/search alias `beam_shape_cdsem`
- write/search alias `reso_center_cdsem`

Settings (both families):

- primary shards: `2`
- replicas: `1`
- rollover: write index reaches `500000` docs (safety net only — the data
  is low-volume, so each family normally stays a single backing index)
- retention: delete backing indices after `1095d` (3 years)

The one policy's `ism_template` lists both `beam_shape_cdsem-*` and
`reso_center_cdsem-*`, so rolled-over backing indices in either family
auto-attach to the same policy.

Field mapping:

- `os_inserted` → `date` (explicit; KST write-time stamp, doesn't end in
  `_tm`/`_dt` so the dynamic templates miss it) — both families
- any `*_tm` / `*_dt` columns → `date` via `dynamic_templates` — both
- **`reso_center_cdsem` only**: `Resolution_Range`,
  `Resolution_Range_Raw`, `Resolution_Range_Smooth` are dicts whose
  sub-keys hold lists of floats — fetched whole to plot, never
  filtered/aggregated → `object` with `enabled: false`. The entire dict
  (lists and all) is stored verbatim in `_source` and returned on fetch,
  but never parsed, so its sub-keys are never mapped and cost nothing
  against `index.mapping.total_fields.limit` (default 1000) no matter how
  many or which keys appear. To query one sub-key later, promote it to a
  real top-level field and reindex.
- everything else falls through to default dynamic mapping

```bash
python -m ops_index_mgmt.beam_reso_cdsem --dry-run
python -m ops_index_mgmt.beam_reso_cdsem
```

Ingest a list of dicts with a composite `_id` built from `eqp_ip`,
`timestamp`, `beam_condition`. `iter_bulk_actions` builds the id, stamps
`os_inserted` (KST), and **skips any doc missing an id field**
(`has_id_fields`: key absent, `None`, or blank string — but `0` is kept).
A composite id needs the raw-action `OSDoc.bulk`; `bulk_index` only copies
a single field into `_id`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from ops_store import OSDoc, create_client
from ops_index_mgmt.beam_reso_cdsem import has_id_fields, iter_bulk_actions

doc_service = OSDoc(client=create_client(...))

skipped = sum(1 for doc in docs if not has_id_fields(doc))
if skipped:
    print(f"skipping {skipped} docs missing an id field")

os_inserted_kst = (
    datetime.now(tz=ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat()
)
actions = iter_bulk_actions(
    docs,
    index="beam_shape_cdsem",   # or "reso_center_cdsem"
    os_inserted=os_inserted_kst,
    op_type="create",           # "index" to overwrite-by-id
)
success_count, errors = doc_service.bulk(actions, refresh=False)
```

The full annotated version lives in the reference block at the bottom of
`beam_reso_cdsem.py`.

## network_fdc_cdsem index

`network_fdc_cdsem.py` sets up a single 1-year retention rollover family —
same shape as `fab_inform_notes.py` but with `dynamic_templates` instead of
enumerated columns and a one-year retention:

- ISM policy `network_fdc_cdsem_retention_policy`
- index template `network_fdc_cdsem_template`
- first backing index `network_fdc_cdsem-000001`
- write/search alias `network_fdc_cdsem`

Settings:

- primary shards: `2`
- replicas: `1`
- rollover: write index reaches `1000000` docs
- retention: delete backing indices after `365d` (1 year)

Field mapping:

- `os_inserted` → `date` (explicit; KST write-time stamp, doesn't end in
  `_tm`/`_dt` so the dynamic templates miss it)
- any `*_tm` / `*_dt` columns → `date` via `dynamic_templates`
- everything else falls through to default dynamic mapping

```bash
python -m ops_index_mgmt.network_fdc_cdsem --dry-run
python -m ops_index_mgmt.network_fdc_cdsem
```

Ingest dataframes through the `network_fdc_cdsem` alias:

```python
from ops_store import OSDoc

doc_service = OSDoc(client=client)
doc_service.bulk_index_dataframe(
    fdc_df,
    index="network_fdc_cdsem",
    id_field="doc_id",
    op_type="create",
)
```

The full annotated ingest example lives in the reference block at the bottom
of `network_fdc_cdsem.py`.

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
