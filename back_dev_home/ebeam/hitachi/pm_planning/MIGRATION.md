# pm_planning — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/&lt;tool_slug&gt;/pm-planning/fleet

- This route is slug-parameterized: `routes.py` registers a single
  Blueprint (`ebeam_pm_planning`) with the route path
  `/<tool_slug>/pm-planning/fleet`, auto-discovered and mounted under
  `/api` by `back_dev_home/__init__.py`'s `routes.py`-rglob loop (there is
  no per-slug blueprint registration — one blueprint handles every slug at
  request time). `tool_slug` must be one of the two registered slugs in
  `back_dev_home/ebeam/hitachi/_tool_specs.py`'s `VALID_TOOL_SLUGS`
  (`"cdsem"`, `"hvsem"`); anything else is a `400` (`tool_slug must be
  'cdsem' or 'hvsem'"`) before `data.py` is ever called.
- **CD-SEM only.** Even though `hvsem` is a valid slug elsewhere in this
  codebase, `routes.py` explicitly rejects it here with a second `400`
  (`"pm-planning is available for CD-SEM only"`) before checking `fab_id`.
  `get_pm_planning_fleet` is therefore only ever called with a CD-SEM
  fleet in mind — office does not need an HV-SEM code path for this
  endpoint.
- Handler: `routes.py` → `pm_planning_fleet(tool_slug)`. Reads `fab_id`
  from the query string (`?fab_id=...`, stripped; a missing/blank value is
  a `400` — `"fab_id query parameter is required"` — raised by the route
  itself, before `data.get_pm_planning_fleet` is called). On success,
  calls `data.get_pm_planning_fleet(fab_id)` and returns the payload
  directly via `jsonify(...)`.
- Contract: `FleetPayload` (see `contracts.py` for the full definitions of
  `GateBlock`, `CellSkew`, `EpochPoint`, `ToolBlock`, `ConsensusCell`, and
  `FleetDefaults` referenced below) —

  ```python
  BeamCondition = Literal["500V", "800V"]
  ScanAxis = Literal["X", "Y"]
  GateVerdict = Literal["up", "hold"]


  class GateBlock(TypedDict):
      cd_monitoring_value: float
      cd_spec_lower: float
      cd_spec_upper: float
      cd_in_spec: bool
      bsm_in_spec: bool
      bsm_sharpness_avg: float
      bsm_noise_avg: float
      post_pm_at: str | None
      prev_post_delta: float | None
      mdc_changed: bool
      verdict: GateVerdict


  class CellSkew(TypedDict):
      beam: BeamCondition
      axis: ScanAxis
      skew: float
      current_value: float
      median: float
      gap: float


  class EpochPoint(TypedDict):
      epoch_start: str
      mdc: float
      bsm_sharpness_avg: float


  class ToolBlock(TypedDict):
      eqp_id: str
      gate: GateBlock
      cells: list[CellSkew]
      epoch_history: list[EpochPoint]


  class ConsensusCell(TypedDict):
      beam: BeamCondition
      axis: ScanAxis
      consensus: float


  class FleetDefaults(TypedDict):
      focus_n: int
      advisory_threshold: dict[str, float]


  class FleetPayload(TypedDict):
      tool_type: str
      fab_id: str
      fetched_at: str
      anchor_date: str
      beam_conditions: list[BeamCondition]
      axes: list[ScanAxis]
      defaults: FleetDefaults
      consensus: list[ConsensusCell]
      tools: list[ToolBlock]
  ```

- Mock behavior: `providers/mock.py` builds a deterministic **8-tool**
  CD-SEM fleet for the given `fab_id`, seeded per-value via `_seed_for`
  (an md5-digest-derived RNG seed keyed on strings like
  `f"fleet::{fab.upper()}"`, `f"cells::{eqp_id}"`, `f"gate::{eqp_id}"`,
  `f"epoch::{eqp_id}"`) — same `fab_id` always yields byte-identical
  output within a process (see the module's own `__main__` determinism
  assertion). `NOW`/`FETCHED_AT` are frozen constants
  (`2026-05-24T09:00:00Z`), not wall-clock time, so `fetched_at` and
  `anchor_date` never drift between calls or across mock/parity runs.
  Per tool:
  - **`gate`** (`_build_gate`): draws a CD-monitoring value from
    `hardware/providers/spec_range_mock.get_cd_monitoring_spec(eqp_id)`'s
    target ± gaussian noise, checks it against that spec's
    `lower`/`upper`; separately reads the latest **daily** BSM
    sharpness/noise averages via
    `hardware/providers/bsm_mock.build_bsm_data(eqp_id)` and validates
    them with `spec_range_mock.bsm_in_spec`; `post_pm_at` comes from the
    most recent `"PM"`-category row in
    `hardware/providers/bm_pm_mock.build_bm_pm_data(eqp_id, NOW)`'s
    `past` list. `verdict` is `"up"` only when both the CD value and the
    BSM readings are in spec, else `"hold"`.
  - **`cells`** (`_tool_cells`): one row per `(beam, axis)` pair (2 beam
    conditions × 2 axes = 4 rows), each carrying a signed `skew` around a
    per-beam consensus base of `16.0`. ~34% of tools get one deliberately
    displaced cell (`skew` blown out to ±0.45–0.75) at a per-tool random
    `(beam, axis)` — this is the fleet's designed outlier-tool signal.
    `median`/`gap` here are provisional (self-referential placeholders)
    and get overwritten by `_apply_fleet_median` below.
  - **`epoch_history`**: 3 past MDC epoch points, each 60+ days apart
    (with jitter), MDC random-walking by ±0.004 per epoch from a random
    start in `[0.990, 1.010]`.
  - **`consensus`** (fleet-level, computed by `_apply_fleet_median` after
    all tools are built): per `(beam, axis)`, the **median of that cell's
    `current_value` across all 8 tools in the fleet** — not a fixed
    constant — then every tool's `cells[i]["median"]`/`["gap"]` is
    rewritten in place against that just-computed fleet median (`gap =
    current_value - median`). This is why `cells` cannot be validated
    tool-by-tool in isolation: the final `median`/`gap` values depend on
    the whole fleet having been generated first.
- Office data source: <!-- OFFICE: per-fab CD-SEM tool roster; per-tool
  CD-monitoring measurement + spec range; per-tool daily BSM
  sharpness/noise averages; per-tool PM job history (most recent
  completed PM's job_end); per-tool MDC epoch history -->
- Notes:
  - **No huge-payload concern** — a fleet snapshot is capped at 8 tools ×
    4 cells regardless of `fab_id`, unlike device_statistics's
    lot-fan-out endpoints.
  - Ranking, threshold filtering, and bottom-N tool selection are
    explicitly **client-side** concerns (per this feature's own contract
    docstring) — the backend ships raw per-cell values plus `defaults`
    (`focus_n`, `advisory_threshold`) instead of pre-ranked results.
    Office must keep shipping the same raw shape; do not pre-rank or
    pre-filter tools/cells before returning.
  - `fab_id` in the response is the request's `fab_id` upper-cased
    (`fab_id.upper()`), not validated against a known-fabs list by this
    endpoint — any string is accepted and echoed back upper-cased.
  - No external importer: nothing outside this feature folder imports
    from `pm_planning.data` or `pm_planning.providers.mock` (unlike
    device_statistics, which recipe_tat's mock provider reaches into
    directly). `hardware/providers/bm_pm_mock.py`/`bsm_mock.py`/
    `spec_range_mock.py` are consumed **by** this mock, not consumers of
    it, so nothing needs cross-feature care here.
  - The parity harness pins both `/api/cdsem/pm-planning/fleet` (`200`,
    `?fab_id=D8` appended by `_parity_snapshot/capture.py`'s
    endpoint-specific handling) and `/api/hvsem/pm-planning/fleet` (`400`,
    the CD-SEM-only rejection) — the `400` case is still valid parity
    (identical status+body before/after the seam cut), not a bug to fix.

## Verify

    SKEWNONO_PM_PLANNING_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/pm_planning
