# hardware — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, `normalizers.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
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
      docs: NotRequired[list[dict]]        # bsm / reso-center / fdc / sharpness
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
  builds both a settings snapshot (as-of `end`) and a `docs` history list;
  `sce` builds only a settings snapshot (no `docs`). `mdc`/`sce` settings
  compare the selected `eqp_id` against in-fab siblings as of `end`.
- Office data source: <!-- OFFICE: per-service OpenSearch indices — beam_shape, reso_center_log, network_fdc_cdsem, network_sharpness_cdsem, MDC/SCE settings collections, BM/PM work-order table -->
- Notes: `fetched_at` is stamped at request/build time and is volatile — a
  parity harness should scrub it rather than compare byte-for-byte. The
  `docs` vs. `settings` split is a discriminated-by-service convention (not
  enforced by the TypedDict): `bsm`/`reso-center`/`fdc`/`sharpness`/`mdc`
  populate `docs`; `mdc`/`sce` populate `settings`; `bm-pm` populates neither
  and relies on `cards`/`tables` only. Office implementations must preserve
  which optional keys are present per service, since the frontend branches
  on their presence.

## Verify

    SKEWNONO_HARDWARE_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/hardware
