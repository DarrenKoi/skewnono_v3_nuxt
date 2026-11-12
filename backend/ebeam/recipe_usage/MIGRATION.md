# recipe_usage — office migration

VeritySEM / Provision 전용입니다. `cdsem` · `hvsem` 슬러그는 400 으로 거절합니다.
스키마 원본은 `docs/datatables/veritysem/recipe_usage.txt` 입니다.

## Rules

- Author the adapter in the tracked `providers/office_example.py`; at the
  office `cp office_example.py office.py` (office.py is gitignored) and run.
  Never touch `routes.py`, `data.py`, `providers/mock.py`, `providers/_shape.py`,
  `contracts.py`, or `tests/`.
- **The swap surface is three raw loaders, not the endpoints.** Both providers
  expose `load_list_rows(tool_type)`, `load_usage_rows(tool_type)` and
  `load_resident(tool_type)`, returning rows in the Redis keys' own column
  shape. `data.py` joins them with the `sem_list` roster and
  `providers/_shape.py` builds every response. The office adapter therefore
  only reads and normalizes types: no filtering, no summing, no fab logic.
- Key names live in one table, `FAMILY_KEYS` in `providers/_shape.py`. A wrong
  name is fixed there, not in the adapter.
- **This adapter cannot run against a mock `sem_list`.** A key row survives
  only when its `eqp_id` is in the roster, so a mock roster drops every row and
  shows the fabricated tools at zero. `_OFFICE_DEPENDENCIES` declares the pair
  and `validate_env()` refuses to boot on it — `cp` sem_list's adapter too.
- The adapter has **never run at the office**. `OFFICE-VERIFY` items are
  listed at the bottom.

## Raw loaders

| Loader | Office source | Row shape |
| --- | --- | --- |
| `load_list_rows` | DataFrame `v3_df_verity_recipes` / `v3_df_provision_recipes` | `ListRow` — grain `(eqp_id, recipe_id, fab_id)`; Provision adds `product_id` / `layer_id` / `recipe_name` |
| `load_usage_rows` | DataFrame `v3_df_verity_recipe_usage` / `v3_df_provision_recipe_usage` | `UsageRow` — grain `(dt, eqp_id, recipe_id)` |
| `load_resident` | hash `v3_verity_unique_rcp_list` / `v3_provision_unique_rcp_list` (`OFFICE-VERIFY` name) | `{eqp_id: [recipe_id, ...]}` |

`v3_{verity,provision}_tools_in_rcp_{fab}` is documented and **not read**: it is
the resident hash inverted.

Failure convention (same as `storage`): a missing DataFrame key or a missing
column raises bare `LookupError` → JSON 502; unset `REDIS_HOST` raises bare
`RuntimeError` → 503. A missing or empty resident hash is **not** an error —
its refresh is not guaranteed — and yields `{}`.

Mock behaviour for all three: deterministic per family, tools taken from the
`sem_list` mock, a few hundred recipes (the office has ~10k). It reproduces
the office properties the shaping rules exist for — the same `(eqp_id,
recipe_id)` under two `fab_id`s, `fab_id` values `C2` / `X1`, VeritySEM ids
that are not four parts, `fac_id=R3` with `fab_name=R4`, a sparse first two
weeks, `fail_runs == runs` rows at 0 minutes, resident-only and MES-only
recipes, and one roster tool with no usage. The latest `dt` is yesterday at
module load. See the docstring of `providers/mock.py` for what is guessed.

## Endpoint: GET /api/<tool_slug>/recipe-usage/recipes

- Handler: `routes.py` → `data.get_catalog(tool_type, fab_names)`.
  `?fab_name=` is a comma list, upper-cased; empty means every fab.
- Contract: `CatalogResponse` — one `CatalogRow` per `(recipe_id, fab_name)`.
- Built from: `load_list_rows` ∪ `load_resident`, roster tools only.
  `fab_name` is the ROSTER's; `n_uses` is summed and `first_used` /
  `last_used` are min / max across tools and `fab_id`. `source` is `mes`
  (list key only), `tool` (resident only; `n_uses` 0, dates `None`) or `both`.
  Provision's `product_id` / `layer_id` / `recipe_name` are the key's own
  columns; VeritySEM answers `""` and a resident-only Provision recipe does
  too, because `recipe_id` is never split.

## Endpoint: GET /api/<tool_slug>/recipe-usage/recipe?recipe_id=

- Handler: `routes.py` → `data.get_recipe_detail(tool_type, recipe_id, fab_names)`.
  `recipe_id` is a query param because it contains `/`; missing → 400.
- Contract: `RecipeDetailResponse`.
- Built from: all three loaders. `tools` has one row per roster tool that has
  the recipe in the list key or on the tool (`on_tool`). `daily` is every
  loaded `dt` of the recipe, summed over tools, days without a run omitted.
  An unknown recipe answers 200 with both lists empty.

## Endpoint: GET /api/<tool_slug>/recipe-usage/status?start_date=&end_date=

- Handler: `routes.py` → `data.get_status(tool_type, fab_names, start, end)`.
  Dates are `YYYY-MM-DD`; a malformed date, a reversed window or one longer
  than 366 days → 400.
- Contract: `StatusResponse`.
- Built from: `load_usage_rows` and the roster. Default window: 14 days ending
  at `anchor_date`. `anchor_date` / `data_start` are the latest / earliest `dt`
  among this family's roster tools **regardless of the fab filter** — they
  describe what is loaded, so the date picker's limits do not move when the
  fab changes. With no rows at all, the window ends yesterday (KST).
  `daily` is zero-filled over the requested window. `equipments` has one row
  per roster tool in scope, zeros when it did not run (user-confirmed
  2026-11-12). `avg_meas_min = meas_min / runs` and reads low where
  `fail_runs` is high, because a run without JobEnd counts 0 minutes.

## Office steps

1. `cp backend/ebeam/recipe_usage/providers/office_example.py
   backend/ebeam/recipe_usage/providers/office.py` (and make sure `sem_list`'s
   `office.py` exists).
2. Smoke run, which prints row counts, the slash-count distribution of
   `recipe_id`, one sample row per key and the resident hash size per family:

   ```bash
   python -m backend.ebeam.recipe_usage.providers.office
   ```

3. Verify:

   ```bash
   curl -s -b LASTUSER=<사번> "http://localhost:5000/api/veritysem/recipe-usage/status" | head -c 600
   curl -s -b LASTUSER=<사번> "http://localhost:5000/api/provision/recipe-usage/recipes?fab_name=R4" | head -c 600
   ```

   `anchor_date` must be yesterday and `summary.tool_count` the family's
   roster size.

## OFFICE-VERIFY

- The Provision hash names `v3_provision_unique_rcp_list` /
  `v3_provision_tools_in_rcp_{fab}`. If the smoke run prints 0 tools for the
  hash, correct `FAMILY_KEYS`.
- The DataFrame keys are parquet (JSON and pickle are read too).
- Time columns are text shaped `YYYY-MM-DD HH:MM:SS`.
- A row's `fab_id` usually equals the tool's `fab_name` (mock assumption only;
  no code depends on it).
- VeritySEM tools without Veridity are absent from the resident hash (mock
  assumption only).
