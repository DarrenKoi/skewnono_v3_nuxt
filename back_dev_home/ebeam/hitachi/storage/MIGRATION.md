# storage — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/<tool_slug>/storage

- Handler: `routes.py` → `data.get_storage(tool_slug, fac_ids)`. `tool_slug`
  is validated against `VALID_TOOL_SLUGS` (400 if invalid) before the data
  call. `fac_ids` comes from a comma-separated `?fac_id=` query param, split
  and trimmed into a list (`[]` when absent).
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
  below 1024 GB, else `"N.NT"`. `fac_ids` (when given) filters rows by exact
  `fac_id` match (case-insensitive, trimmed); an empty/absent filter returns
  the full fleet for that tool type.
- Office data source: <!-- OFFICE: per-tool storage capacity + recipe-count collection agent output -->
- Notes: an empty result (`[]`) is valid — a tool type with no matching
  sem_list entries returns no rows, not an error.

## Endpoint: GET /api/<tool_slug>/ppid-unavailable

- Handler: `routes.py` → `data.get_ppid_unavailable(tool_slug, fac_ids)`.
  Same `tool_slug` validation and `fac_id` query-param parsing as `/storage`.
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
  sorted by `(-missing_days_streak, eqp_ip)`. `fac_ids` filtering drops
  orphan rows outright, since they have no `fac_id` to match against.
- Office data source: <!-- OFFICE: Redis hash 'v3_hitachi_sem_ppid_not_avail', keyed by YYYYMMDD, 30-day retention -->
- Notes: `latest_date` is the max key of the snapshot dict (compact
  `YYYYMMDD` strings sort chronologically as plain strings) rendered as an
  ISO date, not necessarily "today" — office should preserve returning
  whatever the most recent populated day in the retention window actually
  is, rather than always stamping the current date.

## Verify

    SKEWNONO_STORAGE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/storage
