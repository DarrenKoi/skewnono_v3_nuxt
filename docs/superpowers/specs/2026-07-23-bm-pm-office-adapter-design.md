# Hardware BM/PM Office Adapter — Design

- **Date:** 2026-07-23
- **Feature:** `back_dev_home/ebeam/hitachi/hardware` (tab `bm_pm`)
- **Status:** Approved design, pending implementation plan

## Goal

Connect the Hardware page's BM/PM tab to two office OpenSearch indices —
`fab_inform_notes` (maintenance that happened, with engineer notes) and
`tool_maintenance_plan` (maintenance that is scheduled) — and widen the row
shape so the fields engineers actually read reach the table.

The tab already exists: `providers/bm_pm/mock.py` fabricates past/future work,
and `providers/bm_pm/office_example.py` is a stub that raises
`NotImplementedError`. This design replaces that stub and brings the mock up to
the same widened shape.

## Scope

In scope:

- `providers/bm_pm/office_example.py` — the real two-index implementation plus
  an office-side `__main__` diagnostic.
- `providers/bm_pm/mock.py` — widened to emit the identical row shape.
- `normalizers.bm_pm_history_payload` — widened `columns` lists.
- `hardware/MIGRATION.md` — bm_pm status and source indices.
- Unit tests for the adapter's pure helpers.

Out of scope:

- ~~Any frontend change.~~ Correction: no Vue edit was needed for the new
  columns — `BmPmTables.vue` renders whatever `columns` the payload declares —
  but the widened row shape introduced `""` as a possible `category` value,
  which required guarding the BM/PM chip in `BmPmTables.vue` so an
  unclassified row does not render as a false BM.
- `pm_planning`, the separate fleet-level PM Up-gate feature. Its office
  adapter stays stubbed.
- The other hardware tabs.
- Creating `providers/bm_pm/office.py`. The tracked template is copied to that
  gitignored name at the office, which is also what switches the tab on.

## Data Sources

Schema reference: `docs/datatables/hardware_bm_pm.txt`.

`past` rows come from `fab_inform_notes`:

| Row key | Index field | Note |
| --- | --- | --- |
| `eqp_id` | `eqp_id` | Existing column; confirms the selected tool |
| `job_starts` | `down_dt` | Tool down — also the range-filter field |
| `job_end` | `equp_dt` | Actual up; blank means still down |
| `category` | derived | See Category Derivation |
| `pm_type` | `pm_type` | Raw, may be empty |
| `eq_event` | `eq_event` | Raw, shown because `pm_type` is often empty |
| `lot_id` | `lot_id` | |
| `last_recipe_id` | `last_recipe_id` | |
| `note_comment` | `note_comment` | Free-form, expandable |
| `zzproblem` | `zzproblem` | Free-form, expandable |
| `hltext` | `hltext` | Free-form, expandable |
| `timestamp` | `hub_load_tm` | System load time, not event time |
| `engr_note` | derived | Merged notes, carried but not a column |

`up_dt`, `fac_id`, `aufnr`, `doc_id`, and `interval_a`/`noti_no`/`oper` are not
read. `up_dt` in particular is deliberately ignored — see the datatable doc.

`future` rows come from `tool_maintenance_plan`:

| Row key | Index field | Note |
| --- | --- | --- |
| `eqp_id` | `eqp_id` | |
| `category` | derived | From `event_name`, then `work_item_nm` |
| `event_name` | `event_name` | Plan-side counterpart of `eq_event` |
| `job_starts` | `tool_start_tm` | Planned start — the range-filter field |
| `job_end` | `tool_end_tm` | Planned end |
| `work_item_nm` | `work_item_nm` | Free-form, expandable |
| `work_user_cd` | `work_user_cd` | |
| `timestamp` | `chg_tm` | The index's main timestamp |

`maker_cd` and `eqp_model_cd` are dropped: they are tool attributes that repeat
identically on every row of a single-tool table and offer no check on the
result. `eqp_id` repeats too but is kept, in both sections as today, because it
is the one column that shows the table is displaying the selected tool. `ll_dt`, `limit_dt`, and
`org_dt` are normally empty and are not read. `det_fac_id`/`fac_id` are not
filtered on.

## Row Contract

`build_bm_pm_data(eqp_id, anchor)` keeps its current signature and returns the
same three keys, with widened rows:

```python
{
  "past": [ {...12 keys + engr_note...} ],   # down_dt desc
  "future": [ {...8 keys...} ],              # tool_start_tm asc
  "cards": {"last_bm", "next_pm", "planned_count", "recent_count"},
}
```

`cards` keeps its existing four keys and derivation: `last_bm` is the most
recent past BM's `job_end`, `next_pm` the soonest future PM's `job_starts`,
and the two counts are row counts. Missing values stay `"—"`. When the most
recent BM has no `job_end` because the tool is still down, `last_bm` falls back
to that row's `job_starts` rather than showing a blank card.

Ordering changes from the mock's current `timestamp` desc to `down_dt` desc for
past and `tool_start_tm` asc for future — newest work first, soonest plan
first. The mock changes to match, so both providers order identically.

The extra `engr_note` key exists because `front-dev-home/app/utils/bmPmMarkers.ts`
reads `row.engr_note` for its overlay tooltip. Keeping it on the row, without
declaring it as a column, preserves the overlay with no frontend edit.

## Category Derivation

`bmPmMarkers.ts` draws a marker only when `category` is exactly `BM` or `PM`,
and `BmPmTables.vue` renders the BM/PM chip on the same values. Real
`pm_type`/`eq_event` values are not clean `BM`/`PM` strings — they carry other
characters — so classification is defensive:

1. Walk the candidates in priority order — `pm_type` then `eq_event` for past
   rows, `event_name` then `work_item_nm` for future rows.
2. Uppercase each. The first candidate containing `PM` yields `PM`; the first
   containing `BM` yields `BM`.
3. If no candidate matches, the category is `""`.

The walk continues past a candidate that is present but unrecognisable, rather
than stopping at the first non-empty one: a `pm_type` of `기타` next to an
`eq_event` of `PM_WEEKLY` should classify as `PM`, not fail.

A row that fails to classify still appears in the table with its raw `pm_type`
and `eq_event` visible. It only drops out of the chart overlay, which already
skips non-`BM`/`PM` values. Nothing is hidden, and nothing is guessed.

`PM` is tested before `BM` because a string containing both is far more likely
to be a PM record qualified by other text than the reverse. This is a judgment
call to revisit once real values are seen at the office.

## OpenSearch Queries

Both indices store `eqp_id` as dynamic-mapped `text` with a `.keyword`
subfield, so exact match uses `eqp_id.keyword`. Neither query filters on fab:
`eqp_id` is already the lookup identity, and adding a fab clause lets a stale
fab label silently empty the table. This mirrors the fdc adapter.

The dispatcher passes only `anchor` (the request's `end`), so the adapter picks
its own windows:

| Side | Index | Range field | Window | Sort |
| --- | --- | --- | --- | --- |
| past | `fab_inform_notes` | `down_dt` | `anchor−180d … anchor` | `down_dt` desc |
| future | `tool_maintenance_plan` | `tool_start_tm` | `anchor … anchor+90d` | `tool_start_tm` asc |

Each query fetches an explicit `_source` field list, so a new ingestion column
cannot ride along into the payload.

## Timestamp Formatting

Every date reaching a row is reformatted to `%Y-%m-%d %H:%M`, the format the
mock already emits. This is load-bearing: the chart overlay matches
`job_starts` against the chart's own x-axis values, so a different format
places markers nowhere rather than failing loudly.

Window bounds are sent as naive `isoformat()`, matching the fdc adapter's
confirmed KST-wall-clock contract. Whether these two indices store offset-less
KST like `network_fdc_cdsem` is unverified and must be checked at the office —
a stored `Z` suffix would slide every window by nine hours. The `__main__`
diagnostic prints raw stored values so this is visible immediately.

## Error Handling

| Condition | Behavior |
| --- | --- |
| Hit's `eqp_id` differs from the requested one | `ValueError` naming both |
| Row with an empty range field (`down_dt` / `tool_start_tm`) | `ValueError` — it cannot be ordered or placed on the timeline |
| Row count hits the 1000 cap | `LookupError` — a truncated history must not read as complete |
| Missing index or alias | `LookupError` from `_office_search` |
| Empty result for a valid tool | Valid: empty rows, zero counts, `"—"` cards |

Blank `equp_dt` is expected, not an error: it means the tool is still down. The
table renders it as `-`.

Fail-loud on malformed rows matches the fdc adapter. These are system-written
fields, not engineer-typed ones, so a malformed value indicates schema drift
worth surfacing rather than a data-entry slip worth tolerating.

## Testing

`office_example.py` imports at home without a cluster (the OpenSearch client is
lazily created), so the pure helpers are unit-tested against fabricated hit
dicts:

- Category derivation: clean values, mixed-character values, empty `pm_type`
  falling through to `eq_event`, unclassifiable values yielding `""`.
- Row mapping: field renames, blank `equp_dt`, merged `engr_note`.
- Date formatting: OpenSearch date strings to `%Y-%m-%d %H:%M`.
- Cap and validation: full-cap raises, `eqp_id` mismatch raises.

The existing `test_contract.py` gate keeps passing unchanged: `bm_pm` has no
`office.py`, so it still falls back to mock, and the widened mock must still
satisfy `HardwarePayload`.

## Verification

At home: `.venv/bin/pytest back_dev_home/ebeam/hitachi/hardware` and the BM/PM
tab rendering the widened mock columns.

At the office: fill `OPENSEARCH_*` in `back_dev_home/.env`, run the module's
`__main__` diagnostic against a real `eqp_id` to confirm the indices, mappings,
stored timestamp format, and per-clause hit counts, then
`cp providers/bm_pm/office_example.py providers/bm_pm/office.py` and set
`SKEWNONO_HARDWARE_PROVIDER=office`.
