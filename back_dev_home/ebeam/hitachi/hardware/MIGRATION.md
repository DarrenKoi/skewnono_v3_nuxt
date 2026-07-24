# hardware — office migration

## Layout: one subfolder per tab

`providers/` has one subfolder per hardware tab, each with its own
mock/office adapter pair, so the office wiring lands one tab at a time. The
feature switch (`SKEWNONO_HARDWARE_PROVIDER`) is set once; a tab without an
`office.py` serves its own mock until you connect it:

| Tab folder | Builder(s) | Office source | Template |
| --- | --- | --- | --- |
| `fdc/` | `build_fdc_docs` | OpenSearch `network_fdc_cdsem` | written — `cp` + verify |
| `sharpness/` | `build_network_sharpness_docs` | OpenSearch `sharpness_monitor_cdsem` | written — `cp` + verify |
| `bm_pm/` | `build_bm_pm_data` | OpenSearch `fab_inform_notes` + `tool_maintenance_plan` | written — `cp` + verify |
| `bsm/` | `build_beam_shape_docs` | OpenSearch `beam_shape_cdsem` (type:total) | written — `cp` + verify |
| `reso_center/` | `build_reso_center_docs` | OpenSearch `reso_center_log` | stub |
| `mdc/` | `build_mdc_settings` + `build_mdc_history` | MDC settings collection | stub |
| `sce/` | `build_sce_settings` + `build_sce_history` | Redis `sce_info` hash + MinIO `hitachi_sem/cdsem/sce_info/` | written — `cp` + verify |

`fdc/office_example.py` is implemented, not a stub: its body is written
against the `network_fdc_cdsem` layout in
`docs/datatables/network_fdc_cdsem.txt`, so the office step is `cp` plus the
two OFFICE-VERIFY checks in its docstring (offset-less `timestamp`, and
`eqp_id` carrying a `.keyword` subfield). FDC is CD-SEM only — an HV-SEM tool
matches no documents and renders an empty chart, which is the intended
result until HV-SEM FDC is ingested.

`bm_pm/office_example.py` is implemented too, over two indices: `fab_inform_notes`
for the past-work table (`down_dt`/`equp_dt` plus the three engineer notes)
and `tool_maintenance_plan` for the planned-work table. Run its `__main__` before
`cp`-ing it — the diagnostic prints the raw stored timestamps, which is the one
thing about these indices that is still unverified (see the module docstring).
Schema: `docs/datatables/fab_inform_notes.txt`, `docs/datatables/tool_maintenance_plan.txt`.

`sharpness/office_example.py` is likewise implemented, against
`docs/datatables/sharpness_monitor_cdsem.txt`. It is the one adapter here that
cannot query by `eqp_id`: `sharpness_monitor_cdsem` carries **`ip` only** as
tool identity, so the adapter resolves `eqp_id → eqp_ip` through
`sem_list.data.get_sem_list()` (the same roster `storage` and `lateral_recipe`
use) and term-queries `ip`. Two consequences worth knowing before verifying:

- **sem_list must also be on the office provider.** With sem_list on mock the
  roster hands back fabricated IPs, which match zero documents and look exactly
  like "no data". The adapter raises a named error rather than letting that
  happen silently.
- **An empty pull is unambiguous.** `sharpness` is in
  `normalizers.CDSEM_ONLY_SERVICES`, so HV-SEM tools are turned away upstream
  and never reach the adapter.

Its OFFICE-VERIFY list adds one item beyond FDC's: confirm the stored `ip` is
spelled the same as sem_list's `eqp_ip` (bare dotted quad, no port). Run the
`__main__` smoke block — it prints the resolved IP separately from the query
result, so a roster problem is distinguishable from an empty window.

`bsm/office_example.py` is implemented against `docs/datatables/beam_shape.txt`.
It queries the `beam_shape_cdsem` alias for the `type:"total"` /
`fdc_category:"bsi_beam_shape"` documents and normalizes each doc's SHAPE (not
its field names) to match `bsm/mock.py`, because two source shapes would
otherwise drop metrics silently: `Reso EB Focus` arrives doubly-nested
(`[[...16...]]`) and is flattened to a length-16 array, and `Reso EB Focus
Range` arrives as a one-element list (`['8.0000']`) and is unwrapped to a
scalar float so the panel surfaces it as a trend/KPI metric (the mock emits the
same float). Per-degree arrays and scalars are coerced to floats (the source
mixes floats and numeric strings within one array); anything that will not form
a clean length-16 numeric array is dropped. Its OFFICE-VERIFY list: the alias
is `beam_shape_cdsem`; `type`/`fdc_category`/`eqp_id`/`fab_name` match through
`.keyword` sub-fields; `fab_name` is uppercased for the term. Run its `__main__`
smoke block after `cp`. The pure normalizers are unit-tested at home in
`tests/test_bsm_office.py`.

`sce/office_example.py` is implemented against
`docs/datatables/sce_setting.txt`, and is the one hardware adapter that reads
neither OpenSearch nor one source: the LATEST snapshot comes from the Redis
hash `sce_info` (one field per `fab_name` — `M15A`, `M14B`, ... — each value
the fab's `{eqp_id: {FileInfo, SemCond, ImgCond, SCEParam, Coefficients}}`
dict, JSON with a pickle fallback), and the bidaily TREND comes from MinIO:
one `{fab_name}.json` per collection date under
`hitachi_sem/cdsem/sce_info/YYYY/MM/DD/` (default bucket/prefix from
`minio_handler/minio_config.py`). Collection dates are discovered via
`list_date_folders` — the cadence is bidaily-ish, not strictly regular — so
the adapter never computes expected dates. Coverage caveat baked into the
adapter: R3/R4 don't run SCE and M10 has no data yet, so an absent hash field
or archive file returns `{}`/`[]` (the page's graceful empty state), never a
502; only a missing `sce_info` key altogether raises. The pure
parse/normalize helpers are unit-tested at home in `tests/test_sce.py`. Run
its `__main__` smoke block (`... .providers.sce.office <eqp_id> <fab_name>`)
after `cp`.

The shared helper `_siblings.py` stays at the `providers/` root (mock-only:
stable seeds, sibling tool sets, and the metadata tail every faithful doc
carries). `pm_gate_bsm_mock.py` / `spec_range_mock.py` also stay there — they
belong to pm_planning's BM/PM Up-gate, not to a hardware tab. The `pm_gate_`
prefix marks that owner split: `bsm/mock.py` feeds the hardware BSM tab,
`pm_gate_bsm_mock.py` feeds pm_planning.

## Rules

- At the office, first `cp providers/office_example.py providers/office.py`
  (the dispatcher — usually needs no edits), then per tab
  `cp providers/<tab>/office_example.py providers/<tab>/office.py` and
  implement the builder(s).
- **Copy the dispatcher once, then wire tabs one at a time.** The
  dispatcher's own `office.py` is what puts hardware on office; no env var is
  involved. A tab with no `office.py` falls back to its own `mock.py`, so the
  page stays usable while you verify a single tab, and each tab switches to
  real data the moment its `office.py` lands. Nothing else needs flipping.
- The fallback is silent in the response — a mock tab is NOT marked in the
  payload. `ls providers/*/office.py` is the ledger of which tabs are real,
  and the dispatcher logs one INFO line per tab that fell back. Read a chart
  as 사내 data only after checking one of the two.
- A tab whose `office.py` exists but FAILS TO IMPORT (missing dependency,
  bad import line) does NOT fall back — it raises. Only the file's absence is
  treated as "not wired yet"; a broken wired adapter must never quietly serve
  fabricated data under an office switch.
- Edit ONLY the `office.py` copies. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `providers/<tab>/mock.py`, `contracts.py`,
  `normalizers.py`, or `tests/`.
- Each tab builder returns RAW data (docs list / settings dict / bm-pm rows)
  matching its `<tab>/mock.py` counterpart's shape; the dispatcher normalizes
  to `contracts.py` shapes via `normalizers.py`.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/<tool_slug>/hardware/<eqp_id>/<service>

- Handler: `routes.py` → `data.get_hardware_service(tool_slug, service,
  eqp_id, fab_name, start, end)`. `tool_slug` is validated against
  `VALID_TOOL_SLUGS` and `service` against `VALID_SERVICES` before the data
  call; both 400 early on invalid input, so the provider never sees an
  invalid `tool_slug`/`service`. `eqp_id` is `None` when the route segment is
  empty or the literal placeholder `"_"`. `start`/`end` default to a 30-day
  window ending `2026-05-24T09:00:00` when the `start`/`end` query params are
  absent or unparsable.
- Contract: `HardwarePayload` (7 `ServiceKey` values: `bsm`, `reso-center`,
  `fdc`, `mdc`, `sce`, `bm-pm`, `sharpness`) —

  ```python
  class HardwarePayload(TypedDict):
      tool_slug: str
      service: ServiceKey
      eqp_id: str | None
      fab_name: str | None
      available: bool
      fetched_at: str
      summary: str
      cards: list[HardwareMetricCard]
      tables: list[HardwareTableSection]
      docs: NotRequired[list[dict]]        # bsm / reso-center / fdc / sharpness / mdc / sce
      settings: NotRequired[dict[str, dict]]  # mdc / sce
      raw: NotRequired[dict]
  ```

- Mock behavior: `bsm`, `reso-center`, `sce`, `sharpness` are CD-SEM-only —
  requesting them for `hvsem` short-circuits to an `available: false`
  payload with a Korean unavailability message (`unavailable_payload`) before
  any data lookup. When `eqp_id` is `None` (no tool selected yet), every
  service instead returns an `available: true` but empty payload
  (`cards: []`, `tables: []`) carrying a per-service Korean hint string, so
  the frontend can distinguish "not applicable to this tool type" from "pick
  a tool first". Otherwise dispatch is per-service: `bm-pm` builds
  past/future work-order rows + summary cards
  (`bm_pm_history_payload`); `bsm`/`reso-center`/`fdc`/`sharpness` build a
  time-ordered `docs` list scoped to `[start, end]` (`docs_payload`); `mdc`
  and `sce` build both a settings snapshot (as-of `end` for mdc; latest for
  sce) and a `docs` history list. `mdc`/`sce` settings compare the selected
  `eqp_id` against in-fab siblings.
- Office data source: <!-- OFFICE: per-service OpenSearch indices — beam_shape, reso_center_log, network_fdc_cdsem, sharpness_monitor_cdsem, MDC settings collection, fab_inform_notes + tool_maintenance_plan; SCE: Redis sce_info hash (latest) + MinIO hitachi_sem/cdsem/sce_info/YYYY/MM/DD/{fab}.json (bidaily trend) -->
- Notes: `fetched_at` is stamped at request/build time and is volatile — a
  parity harness should scrub it rather than compare byte-for-byte. The
  `docs` vs. `settings` split is a discriminated-by-service convention (not
  enforced by the TypedDict): `bsm`/`reso-center`/`fdc`/`sharpness`/`mdc`/`sce`
  populate `docs`; `mdc`/`sce` populate `settings`; `bm-pm` populates neither
  and relies on `cards`/`tables` only. Office implementations must preserve
  which optional keys are present per service, since the frontend branches
  on their presence.

## Verify

    SKEWNONO_HARDWARE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/hardware
