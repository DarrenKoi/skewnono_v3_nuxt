# tttm — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/<tool_slug>/tttm/check

- Handler: `routes.py` → `data.get_tttm_check(tool_slug, fab_name,
  recipe_id)`. `tool_slug` is validated against `SEM_TOOL_SLUGS` (400 if
  not `cdsem`/`hvsem`) before the data call. `fab_name` is a required query
  param (`?fab_name=...`, 400 if missing); `recipe_id` is an optional query
  param.
- Contract: `TttmCheckPayload` (large nested tree — see `contracts.py` for
  the full `ToolRef`/`CellSkew`/`SkewMatrixBlock`/`ProductionCorroboration`/
  `FleetToday`/`TrendPoint`/`EpochMarker`/`MdcHistoryEntry` definitions) —

  ```python
  class TttmCheckPayload(TypedDict):
      tool_slug: ToolSlug
      fab_name: str
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
  `tool_slug`/`fab_name` pair from `__fixtures__/tttm_{tool_slug}_{fab_name.lower()}.json`
  (only `tttm_cdsem_r3.json` exists today). If the fixture file is missing,
  `get_tttm_check` returns an `available: false` empty payload (`tools: []`,
  `occupied_cells: []`, all list fields empty, `current_tolerance: 0.05`,
  `production_corroboration.level: "low"`) with a Korean "no mock data for
  this fleet" summary — this is the "unknown fab" case, not an error.
  `recipe_id` from the query string always overrides whatever value is
  baked into the fixture (`payload["recipe_id"] = recipe_id or
  payload.get("recipe_id")`) — a `None` query param falls back to the
  fixture's own value rather than clearing it. The server never computes
  N배화 (maximal-clique) grouping; it only serves raw per-cell pairwise skew
  matrices and lets the client derive groupings.
- Office data source: <!-- OFFICE: real pairwise skew statistics per cell (beam_condition × axis × cd_band × mdc_epoch), median measured CD per cell and for today's fleet, tolerance config, production overlap corroboration, fleet-today consensus, trend history, MDC change epochs -->
- Notes: `fetched_at` is volatile (stamp-at-request-time) and should be
  scrubbed by any parity harness rather than compared exactly. `direct_skew_matrix`/
  `predicted_skew_matrix` in each `CellSkew` are independently nullable —
  a cell with no data for a given tier is `None`, not an empty matrix.
  `SkewMatrixBlock.values` is symmetric with a zero diagonal; a `null` cell
  means that tool pair is not TTTM-able (no shared data), not zero skew.

## `median_cd_nm` — what the office adapter owes

`CellSkew.median_cd_nm` and `FleetToday.median_cd_nm` carry the median measured
CD (nm) of the MSR rows behind those numbers. Both are nullable: return `None`
when no CD came back, and the client falls back to the 15 nm monitor wafer while
saying on screen that it assumed it.

세 가지 규칙을 지켜야 합니다.

| 규칙 | 이유 |
| --- | --- |
| skew 통계와 **같은 row 집합**에서 median 을 계산합니다 | median 이 자기 `cd_band` 를 벗어나면 `test_median_cd_agrees_with_the_band_it_is_filed_under` 가 실패합니다. band 는 이 frame, CD 는 저 frame 에서 가져오면 그렇게 됩니다 |
| 평균이 아니라 **median** 입니다 | `consensus` 가 median 인 이유와 같습니다. CD outlier 하나가 그 셀 전체 장비의 action limit 을 옮깁니다 |
| 모르면 `0.0` 이 아니라 `None` 입니다 | 클라이언트는 이 값의 1% 로 나눕니다. `0.0` 은 무한대 limit 이 되어 모든 장비를 조용히 통과시킵니다 |

화면이 그리는 action limit 은 `0.01 × median_cd_nm` 입니다. 이 비율은 **한 대의
장비를 consensus 와 비교하는** 공장 정책입니다 (user-confirmed 2026-08-16: 15 nm
모니터 wafer 에서 ±0.15 nm). OFFICE-VERIFY: 같은 비율을 *장비쌍* skew 에 적용하는
것은 우리 쪽 확장이며 공장이 말한 바가 아닙니다. 그래서 프론트엔드는 그 값을
limit 이 아니라 지수(index)로 표기합니다.

## Verify

    SKEWNONO_TTTM_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/tttm
