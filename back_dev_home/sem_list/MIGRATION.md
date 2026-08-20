# sem_list — office migration

## Rules

- FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/sem-list

- Handler: `routes.py` → `data.get_sem_list()`
- Contract: `SemListRow` —

  ```python
  class SemListRow(TypedDict):
      fac_id: str
      eqp_id: str
      eqp_model_cd: str
      eqp_grp_id: str
      vendor_nm: Literal["HITACHI", "AMAT"]
      eqp_ip: str
      fab_name: str
      updt_dt: str
      available: Literal["On", "Off"]
      version: str  # digits+letters, e.g. "1A"; "" when unknown
  ```

- Mock behavior: generates a deterministic 300-row fleet (`random.Random(42)`)
  spanning six `fac_id` values (`M11, M12, M14, M15, M16, R3`). `R3`-class
  facilities only ever produce `fab_name` of `R3` or `R4` (no letter suffix);
  every other `fac_id` gets a single `A`/`B`/`C` suffix appended
  (`fab_name = f"{fac_id}{suffix}"`). `vendor_nm` is a coin flip between
  `HITACHI` and `AMAT`, and `eqp_model_cd`/`eqp_id` prefixes are drawn from
  vendor-specific pools so the model code and equipment id prefix always
  agree with `vendor_nm`. `updt_dt` is an ISO-8601 UTC timestamp with a
  literal `Z` suffix, anchored at `2026-04-19T00:00:00Z` minus a random
  0–2555 day offset — it is the tool's FIRST ARRIVAL time at the fab, not a
  roster-update time (user-confirmed 2026-07-30), so the span covers years
  rather than a recent window. `available` is `"On"` 90% of the time.
- Office data source: **three** Redis keys, each a `pandas.DataFrame`
  serialized as **parquet** (`df.to_parquet()`, read via the pyarrow engine
  — `pyarrow` is in `requirements.txt`). Connection via `REDIS_HOST` /
  `REDIS_PORT` / `REDIS_PASSWORD` in `back_dev_home/.env`.
  - `v3_df_sem_avail` — the fleet, **without** a `version` column.
  - `v3_df_sem_version` — columns `[eqp_ip, version]`; `version` is a
    free-form string.
  - `v3_df_sem_list` — the full company roster; not read by this endpoint,
    only by `GET /api/sem-list/pending` below.

  The adapter LEFT-merges `version` onto the fleet by `eqp_ip`
  (`fleet.merge(right, on="eqp_ip", how="left")`), so every fleet row
  survives exactly once; the version table is de-duplicated on `eqp_ip`
  first so a repeated ip can't multiply fleet rows. A fleet row with no
  matching version becomes `version=""`. Format is auto-detected by magic
  bytes (`PAR1` → parquet, with JSON/pickle fallbacks) and all text is
  decoded UTF-8. Confirm the column names match the contract; trim unused
  fallback branches if you like.
- Notes: the full list is unfiltered and unpaginated — the route returns
  every row every call. There is no empty-result case in the mock (always
  300 rows); the office adapter should still return `[]` gracefully if the
  fleet table is empty rather than erroring, since the contract test only
  requires "not empty" as a mock-mode sanity check, not a hard invariant of
  the contract itself.

## Endpoint: GET /api/sem-list/pending

- Handler: `routes.py` → `data.get_pending_tools()`
- Contract: `PendingToolRow` — the eight identity columns, no `available`
  and no `version` (both live in keys a pending tool is not in yet).
- Office data source: `v3_df_sem_list` (full company roster) diffed against
  `v3_df_sem_avail` (reachable subset) on **`eqp_id`**.

  ```python
  pending = roster[~roster["eqp_id"].isin(set(connected["eqp_id"]))]
  ```

  Every tool is assigned an `eqp_ip` at fab installation and is firewalled
  from that moment, entering `v3_df_sem_avail` only once IT opens the IP. So
  this difference is the firewall-request queue, and an empty result means
  every roster tool is reachable — a valid response, not an error.
- `v3_df_sem_list` carries the same 8 identity columns as `v3_df_sem_avail`
  minus `available` — `fac_id`, `eqp_id`, `eqp_model_cd`, `eqp_grp_id`,
  `vendor_nm`, `eqp_ip`, `fab_name`, `updt_dt` (`user-confirmed 2026-07-30`).
  Not yet proven by a real run, so confirm once on the first office run and
  upgrade the marker to `office 확인 <date>`. If it turns out wrong,
  `_select_pending` raises with the missing column names rather than rendering
  an empty screen:

  ```bash
  # The key is NOT an argument: set KEY_NAME = "v3_df_sem_list" inside
  # scripts/inspect_redis_key.py first, then run it bare.
  .venv/bin/python -m scripts.inspect_redis_key
  ```

- Unlike `get_sem_list`, an unknown `vendor_nm` is **passed through**, not
  rejected. This screen exists to surface tools that have not been onboarded,
  so a new vendor must appear on it rather than 502 the request.
- Mock behavior: 14 tools in 5 fab × model clusters, one with `fab_name=""`
  so the UI's 미배정 path has data at home. One cluster arrives 400 days ago
  on purpose — `v3_df_sem_list` is a live snapshot (user-confirmed
  2026-07-30), so there is no such thing as a stale/abandoned row in it, and
  an old `updt_dt` still awaiting a firewall exception is exactly the case
  this screen exists to surface.

## Verify

Quick smoke test (prints row count + first row; loads `.env` itself):

    .venv/bin/python -m back_dev_home.sem_list.providers.office

Contract gate (`.env` is loaded by `back_dev_home/conftest.py`):

    SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/pytest back_dev_home/sem_list

Both must run from the repo root. Do NOT run the provider file by path
(`python providers/office.py`) — package imports require the `-m` form.

## Office Follow-up: 미연결 장비 실장

1. **Run this first.** `python -m scripts.sync_office_adapters sem_list`.
   `providers/office.py` is a gitignored copy and is STALE after this change —
   it lacks `get_pending_tools`, and a stale adapter fails the whole Flask app
   factory during blueprint discovery, so nothing else works until it is
   refreshed. The symptom is a boot failure that does not obviously name
   `sem_list`.
2. Confirm the roster's columns once, and upgrade the two `user-confirmed
   2026-07-30` markers (here and in `docs/datatables/sem_list.txt`) to
   `office 확인 <date>`:

   ```bash
   # In scripts/inspect_redis_key.py, set these two module constants first --
   # the script takes no arguments and refuses any:
   #   KEY_NAME = "v3_df_sem_list"
   #   UNIQUE_COLUMNS = ["fab_name", "eqp_model_cd"]
   .venv/bin/python -m scripts.inspect_redis_key
   ```

3. Check the real payload for a null `eqp_ip`. `_normalize_pending` blanks a NaN
   cell rather than raising, on the strength of the user-confirmed fact that
   every tool gets an IP at fab installation. A blank IP would still show in the
   matrix and drill-down but drop out of `IP 목록 복사`, so if any real row has
   one, add a visible marker to those rows rather than letting the copy list
   quietly come up short:

   ```bash
   curl -s localhost:5000/api/sem-list/pending \
     | python -c "import json,sys; r=json.load(sys.stdin); print(len(r),'rows;', sum(1 for x in r if not x['eqp_ip']),'without ip;', sum(1 for x in r if not x['fab_name']),'without fab')"
   ```
