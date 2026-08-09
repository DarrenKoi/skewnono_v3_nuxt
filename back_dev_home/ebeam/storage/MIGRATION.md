# storage — office migration

## Rules

- Author the adapter in the tracked `providers/office_example.py`; at the
  office `cp office_example.py office.py` (office.py is gitignored) and run.
  Never touch `routes.py`, `data.py`, `providers/mock.py`, `contracts.py`,
  or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/<tool_slug>/storage

- Handler: `routes.py` → `data.get_storage(tool_slug, fab_names)`. `tool_slug`
  is validated against `SEM_TOOL_SLUGS` (400 if invalid — an AMAT slug is
  refused, not answered with fabricated rows) before the data
  call. `fab_names` comes from a comma-separated `?fab_name=` query param, split
  and trimmed into a list (`[]` when absent). The left-sidebar selection is a
  `fab_name` (e.g. `M16A`, `R3`, `R4`), so storage filters on the DataFrame's
  `fab_name` column directly — no `fac_id` collapse.
- Contract: `StorageRow` —

  ```python
  class StorageRow(TypedDict):
      eqp_id: str
      eqp_ip: str
      fac_id: str
      total: str              # "" when storage collection failed
      used: str                # "" when storage collection failed
      avail: str               # "" when storage collection failed
      percent: str             # "" when storage collection failed
      storage_mt: str | None   # None when storage collection failed
      rcp_counts: int
      rcp_counts_mt: str
      storage_mt_date: str     # "" when storage collection failed
      fab_name: str
      eqp_model_cd: str
  ```

- Mock behavior: `sem_list.data.get_sem_list()` is the single source of
  truth for the tool fleet — storage rows are derived from (not re-rolled
  independently of) sem_list, filtered to the `tool_slug`'s tool type via
  `model_to_tool_type`, so `eqp_id`/`eqp_ip`/`fac_id`/`fab_name`/
  `eqp_model_cd` always match sem_list for the same physical tool. `rcp_counts`
  is seeded across four tiers so the UI's warning (`>49,000`) and critical
  (`>49,800`) thresholds both get exercised. ~8% of rows simulate a failed
  storage collection: `storage_mt` is `None` and `total`/`used`/`avail`/
  `percent`/`storage_mt_date` are all `""`, while `rcp_counts`/
  `rcp_counts_mt` still report normally (recipe counting is a separate
  collection path from storage capacity). Capacity values render as `"NNNG"`
  below 1024 GB, else `"N.NT"`. `fab_names` (when given) filters rows by exact
  `fab_name` match (case-insensitive, trimmed); an empty/absent filter returns
  the full fleet for that tool type.
- Office data source: per-tool parquet `pandas.DataFrame` in Redis —
  `v3_df_ppid_storage_cdsem` / `v3_df_ppid_storage_hvsem` (the "ppid" in the
  key name is recipe/ppid **count** data, i.e. `rcp_counts`). Columns match
  `StorageRow`; a failed capacity collection is a row whose `storage_mt`
  (and capacity strings) are null/blank while `rcp_counts` still reports.
  The adapter reads the tool's key, coerces nulls to `""`/`None` per the
  contract, and filters by `fab_name`. Read via pyarrow; connection from
  `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD` in `back_dev_home/.env`.
  **The DF's own `fab_name`/`fac_id` columns are not trusted**: the office
  collection pipeline wrote fac-level names (`M16`), so the sidebar's
  fab_name filter (`M16A`) matched nothing and every fab except R3 rendered
  an empty 스토리지 table. Each row is re-keyed against the live sem_list by
  `eqp_ip` (the same join `get_ppid_unavailable` uses); the DF's values
  survive only for IPs the fleet doesn't know. The adapter's `__main__`
  smoke test prints the per-fab row distribution — every sidebar fab should
  appear there, not just R3.
- Notes: an empty result (`[]`) is valid — a tool type with no matching
  sem_list entries returns no rows, not an error.
- **This adapter cannot run against a mock sem_list.** The join above is what
  makes that pairing dangerous: mock IPs never match office IPs, so every row
  falls back and the table renders empty behind a 200, with nothing in the
  log. `_OFFICE_DEPENDENCIES` in `_runtime/data_provider.py` declares the pair
  and `validate_env()` now refuses to boot on it — so at the office, `cp`
  sem_list's adapter too, not just this one. See
  `docs/back-end/provider-selection.md` §7.

## Endpoint: GET /api/<tool_slug>/ppid-unavailable

- Handler: `routes.py` → `data.get_ppid_unavailable(tool_slug, fab_names)`.
  Same `tool_slug` validation and `fab_name` query-param parsing as `/storage`.
- Contract: `PpidUnavailableSnapshot` —

  ```python
  class PpidUnavailableRow(TypedDict):
      eqp_id: str
      eqp_ip: str
      fac_id: str
      fab_name: str
      eqp_model_cd: str
      missing_days_streak: int

  class PpidUnavailableSnapshot(TypedDict):
      latest_date: str
      rows: list[PpidUnavailableRow]
  ```

- Mock behavior: models a Redis-shaped 30-day rolling snapshot
  (`{"YYYYMMDD": [eqp_ip, ...]}`, keyed by IP only — office source is the
  Redis hash `v3_hitachi_sem_ppid_not_avail`, `hget(key, "%Y%m%d") ->
  not_avail_ip_list`). Each IP is joined against `sem_list` to enrich
  `eqp_id`/`fac_id`/`fab_name`/`eqp_model_cd`; IPs with no sem_list match
  (e.g. decommissioned tools still reporting) surface as orphan rows with
  those fields blank (`""`). Only IPs present in the **latest** day's bucket
  are returned as rows — `missing_days_streak` counts consecutive days
  backward from `latest_date` while the IP stays present, so a tool that
  failed earlier in the window then recovered by the latest date is
  excluded entirely (it does not appear as a stale/expired row). Rows are
  sorted by `(-missing_days_streak, eqp_ip)`. `fab_names` filtering drops
  orphan rows outright, since they have no `fab_name` to match against.
- Office data source: Redis **hash** `v3_hitachi_sem_ppid_not_avail`, field
  `%Y%m%d` → list of unavailable equipment IPs that day (CD-SEM and HV-SEM
  **combined**, 30-day retention; list value tolerates JSON / repr / CSV
  encoding). The adapter reads the whole hash, takes the latest date's IPs,
  joins each IP to the live `sem_list` (`sem_list.data.get_sem_list()`) to
  recover `eqp_id`/`fac_id`/`fab_name`/`eqp_model_cd` and the tool type, and
  keeps only IPs that resolve to the requested `tool_slug` (then narrows by
  `fab_name` when the filter is present). `missing_days_streak`
  counts consecutive days the IP stays present, back from the latest date.
  Behavior note vs. mock: an IP with **no** sem_list match can't be attributed
  to a tool, so office mode drops it (the mock, which rolls per-tool snapshots,
  surfaces synthetic orphans) — both still satisfy the contract.
- Notes: `latest_date` is the max key of the snapshot dict (compact
  `YYYYMMDD` strings sort chronologically as plain strings) rendered as an
  ISO date, not necessarily "today" — office should preserve returning
  whatever the most recent populated day in the retention window actually
  is, rather than always stamping the current date.

## Verify

First copy the tracked skeleton to the gitignored runnable adapter:

    cp back_dev_home/ebeam/storage/providers/office_example.py \
       back_dev_home/ebeam/storage/providers/office.py

Smoke test (prints row counts + a sample per tool; loads `.env` itself):

    .venv/bin/python -m back_dev_home.ebeam.storage.providers.office

Contract gate (`.env` loaded by `back_dev_home/conftest.py`):

    SKEWNONO_STORAGE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/storage
