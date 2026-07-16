# skew — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/<tool_slug>/skew/check

- Handler: `routes.py` → `data.get_skew_check(tool_slug, fab_id,
  recipe_id)`. `tool_slug` is validated against `VALID_TOOL_SLUGS` (400 if
  not `cdsem`/`hvsem`) before the data call. `fab_id` is a required query
  param (`?fab_id=...`, 400 if missing); `recipe_id` is an optional query
  param.
- Contract: `SkewCheckPayload` (large nested tree — see `contracts.py` for
  the full `ToolRef`/`CellSkew`/`SkewMatrixBlock`/`ProductionCorroboration`/
  `FleetToday`/`TrendPoint`/`EpochMarker`/`MdcHistoryEntry` definitions) —

  ```python
  class SkewCheckPayload(TypedDict):
      tool_slug: ToolSlug
      fab_id: str
      recipe_id: str | None
      available: bool
      fetched_at: str
      summary: str
      tools: list[ToolRef]
      current_tolerance: float           # default 0.05 (nm)
      tolerance_range: ToleranceRange     # {min: 0.01, max: 0.20, step: 0.005}
      occupied_cells: list[CellSkew]
      production_corroboration: ProductionCorroboration
      fleet_today: FleetToday
      trend: list[TrendPoint]
      epoch_markers: list[EpochMarker]
      mdc_history: list[MdcHistoryEntry]
      raw: NotRequired[dict[str, object]]
  ```

- Mock behavior: serves a static, deterministic fixture file per
  `tool_slug`/`fab_id` pair from `__fixtures__/skew_{tool_slug}_{fab_id.lower()}.json`
  (only `skew_cdsem_r3.json` exists today). If the fixture file is missing,
  `get_skew_check` returns an `available: false` empty payload (`tools: []`,
  `occupied_cells: []`, all list fields empty, `current_tolerance: 0.05`,
  `production_corroboration.level: "low"`) with a Korean "no mock data for
  this fleet" summary — this is the "unknown fab" case, not an error.
  `recipe_id` from the query string always overrides whatever value is
  baked into the fixture (`payload["recipe_id"] = recipe_id or
  payload.get("recipe_id")`) — a `None` query param falls back to the
  fixture's own value rather than clearing it. The server never computes
  N배화 (maximal-clique) grouping; it only serves raw per-cell pairwise skew
  matrices and lets the client derive groupings.
- Office data source: <!-- OFFICE: real pairwise skew statistics per cell (beam_condition × axis × cd_band × mdc_epoch), tolerance config, production overlap corroboration, fleet-today consensus, trend history, MDC change epochs -->
- Notes: `fetched_at` is volatile (stamp-at-request-time) and should be
  scrubbed by any parity harness rather than compared exactly. `direct_skew_matrix`/
  `predicted_skew_matrix` in each `CellSkew` are independently nullable —
  a cell with no data for a given tier is `None`, not an empty matrix.
  `SkewMatrixBlock.values` is symmetric with a zero diagonal; a `null` cell
  means that tool pair is not TTTM-able (no shared data), not zero skew.

## Verify

    SKEWNONO_SKEW_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/skew
