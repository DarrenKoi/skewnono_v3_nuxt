# pm_planning — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/&lt;tool_slug&gt;/pm-planning/fleet

- This route is slug-parameterized: `routes.py` registers a single
  Blueprint (`pm_planning`) with the route path
  `/<tool_slug>/pm-planning/fleet`, auto-discovered and mounted under
  `/api` by `back_dev_home/__init__.py`'s `routes.py`-rglob loop (there is
  no per-slug blueprint registration — one blueprint handles every slug at
  request time). `tool_slug` must be in
  `back_dev_home/ebeam/_tool_specs.py`'s `SEM_TOOL_SLUGS`
  (`"cdsem"`, `"hvsem"`) — NOT `VALID_TOOL_SLUGS`, which also holds the AMAT
  families this feature has no adapter for. Anything else is a `400` from
  `_slug_routes.bad_tool_slug_response()` before `data.py` is ever called;
  the message is derived from the registry, not hard-coded.
- **`window_weeks` bounds every "current" source, and the run cap grows with
  it.** Read by `_analysis_window.resolve_window_weeks()` exactly as
  `/tttm/check` reads it — one of `1`/`2`/`3`/`4`, default `2`, anything else a
  400 — because pm-planning joins this payload with the tttm check under one
  "N주 윈도우" label. `data.get_pm_planning_fleet(fab_name, window_weeks)` is
  positional and undefaulted so a stale `office.py` raises. The adapter
  gathers monitor runs and BSM readings from `anchor - 7 * window_weeks`
  days, and asks `recent_runs` for `runs_per_tool(window_weeks)` =
  `RUNS_PER_TOOL_PER_WEEK * window_weeks` runs per tool; a tool idle for
  longer than the window drops out of the fleet, which is the window meaning
  what its label says. **PM events are NOT windowed**: `post_pm_at` comes from
  `maintenance_events` over a fixed `PM_LOOKBACK_DAYS` (30, what the old
  fixed window gave it) because "when was this tool last touched" is a fact
  about the tool, not evidence the user sized — windowed, a PM three weeks ago
  vanished at the 2-week default and moved pm-planning's default pick. MDC epochs
  likewise keep their own `EPOCH_LOOKBACK_DAYS`. Echo `window_weeks` on the payload,
  including the empty-roster one. (It used to be a fixed 30 days behind a
  fixed cap of 8 runs.)
- **CD-SEM only.** Even though `hvsem` is a valid slug elsewhere in this
  codebase, `routes.py` explicitly rejects it here with a second `400`
  (`"pm-planning is available for CD-SEM only"`) before checking `fab_name`.
  `get_pm_planning_fleet` is therefore only ever called with a CD-SEM
  fleet in mind — office does not need an HV-SEM code path for this
  endpoint.
- Handler: `routes.py` → `pm_planning_fleet(tool_slug)`. Reads `fab_name`
  from the query string (`?fab_name=...`, stripped; a missing/blank value is
  a `400` — `"fab_name query parameter is required"` — raised by the route
  itself, before `data.get_pm_planning_fleet` is called). On success,
  calls `data.get_pm_planning_fleet(fab_name)` and returns the payload
  directly via `jsonify(...)`.
- Contract: `FleetPayload` (see `contracts.py` for the full definitions of
  `GateBlock`, `CellSkew`, `EpochPoint`, `ToolBlock`, and `ConsensusCell`
  referenced below) —

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


  class FleetPayload(TypedDict):
      tool_type: str
      fab_name: str
      fetched_at: str
      anchor_date: str
      beam_conditions: list[BeamCondition]
      axes: list[ScanAxis]
      consensus: list[ConsensusCell]
      tools: list[ToolBlock]
  ```

- Mock behavior: `providers/mock.py` reads the fab's CD-SEM roster
  **from sem_list** (`sem_list/providers/mock.get_sem_list()`, filtered by
  `fab_name` + `model_to_tool_type == "cd-sem"`, deduplicated by `eqp_id`,
  sorted) — the same law tttm's mock follows, because the pm-planning page
  joins this payload with `tttm/check` by `eqp_id` and a fabricated roster
  intersects that join down to zero tools. A fab with no CD-SEM rows in
  sem_list answers an **empty** `tools` list (real fab names are
  `M14A`/`R3`-style; a bare `M14` matches nothing). Per-tool values are
  seeded via `_seed_for` (an md5-digest-derived RNG seed keyed on strings
  like `f"cells::{eqp_id}"`, `f"gate::{eqp_id}"`, `f"epoch::{eqp_id}"`) —
  same `fab_name` always yields byte-identical output within a process
  (see the module's own `__main__` determinism assertion). `NOW`/`FETCHED_AT` are frozen constants
  (`2026-05-24T09:00:00Z`), not wall-clock time, so `fetched_at` and
  `anchor_date` never drift between calls or across mock/parity runs.
  Per tool:
  - **`gate`** (`_build_gate`): draws a CD-monitoring value from
    `hardware/providers/spec_range_mock.get_cd_monitoring_spec(eqp_id)`'s
    target ± gaussian noise, checks it against that spec's
    `lower`/`upper`; separately reads the latest **daily** BSM
    sharpness/noise averages via
    `hardware/providers/pm_gate_bsm_mock.build_bsm_data(eqp_id)` and
    validates them with `spec_range_mock.bsm_in_spec`; `post_pm_at` comes
    from the most recent `"PM"`-category row in
    `hardware/providers/bm_pm/mock.build_bm_pm_data(eqp_id, NOW)`'s
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
    `current_value` across all tools in the fleet** — not a fixed
    constant — then every tool's `cells[i]["median"]`/`["gap"]` is
    rewritten in place against that just-computed fleet median (`gap =
    current_value - median`). This is why `cells` cannot be validated
    tool-by-tool in isolation: the final `median`/`gap` values depend on
    the whole fleet having been generated first.
- Office data source: **구현 완료(2026-08-18), 사무실 검증 대기.**
  `providers/office_example.py` 가 네 소스를 조인합니다 — 장비 명단은
  `sem_list`(`roster.py` 의 `fleet_rows`), `cd_monitoring_value` 와 `cells` 는
  `meas_hist_cdsem` 실행을 MinIO `dict_pkl` 로 풀어 얻은 CD 값, `bsm_*` 는
  OpenSearch `beam_shape_cdsem`, `post_pm_at` 는 `fab_inform_notes`,
  `mdc_changed` 와 `epoch_history` 는 `mdc_setting` 의 MinIO 아카이브입니다.
  공용 코드는 `ebeam/_office_msr_cd.py`, `ebeam/_office_mdc.py`,
  `ebeam/_office_bm_pm.py` 이며 **tracked** 이므로 `git pull` 로 갱신됩니다.

  ★ hardware 의 office 어댑터를 **가져다 쓰지 않습니다.** 두 가지 이유입니다 —
  그쪽은 gitignore 된 사본이라 `cp` 하지 않은 기계에서는 pm_planning 이 통째로
  깨지고, 또 장비 1대씩 답하는 모양이라 18대 fab 이면 왕복이 18번 생깁니다.
  여기서는 집계 한 번으로 장비 그룹 전체를 받습니다.
- Notes:
  - **No huge-payload concern** — a fleet snapshot is one fab's CD-SEM
    roster (≤ ~18 tools in the mock's sem_list) × 4 cells, unlike
    device_statistics's lot-fan-out endpoints.
  - Ranking, threshold filtering, and bottom-N tool selection are
    explicitly **client-side** concerns (per this feature's own contract
    docstring) — the backend ships raw per-cell values instead of
    pre-ranked results. Office must keep shipping the same raw shape; do
    not pre-rank or pre-filter tools/cells before returning.
  - `fab_name` in the response is the request's `fab_name` upper-cased
    (`fab_name.upper()`), not validated against a known-fabs list by this
    endpoint — any string is accepted and echoed back upper-cased.
  - No external importer: nothing outside this feature folder imports
    from `pm_planning.data` or `pm_planning.providers.mock` (unlike
    device_statistics, which recipe_tat's mock provider reaches into
    directly). `hardware/providers/bm_pm/mock.py`/`pm_gate_bsm_mock.py`/
    `spec_range_mock.py` are consumed **by** this mock, not consumers of
    it, so nothing needs cross-feature care here.
  - Parity checks should pin both `/api/cdsem/pm-planning/fleet` (`200`,
    with a `fab_name` that exists in sem_list, e.g. `R3`) and
    `/api/hvsem/pm-planning/fleet` (`400`, the CD-SEM-only rejection) —
    the `400` case is still valid parity (identical status+body before/
    after the seam cut), not a bug to fix.

## ★ office 의 gate 는 mock 의 gate 와 뜻이 다릅니다

`spec_range_mock` 이 공급하는 두 값은 **지어낸 값**이고 사무실 소스가 없습니다.
그래서 office 어댑터는 그것을 재사용하지 않고 대체합니다. 화면은 같아 보이지만
읽는 뜻이 달라지므로, 숫자를 보고하기 전에 이 표를 보십시오.

| 항목 | mock | office | 왜 |
| --- | --- | --- | --- |
| `cd_spec_lower/upper` | 장비별 target ±0.5 nm (지어냄) | 장비 그룹 중앙값 ±1 % | 1 % 가 팹이 밝힌 유일한 규칙입니다(user-confirmed 2026-08-16, 15 nm 모니터 wafer 의 ±0.15 nm 가 곧 이 비율) |
| `cd_in_spec` 의 뜻 | 기록된 스펙 안 | **형제 장비들과 일치** | 위에서 따라옵니다. 같은 주장이 아닙니다 |
| `bsm_in_spec` | 절대 밴드 noise 6.65–6.95 | 장비 그룹 상대 median ± 3 × MAD | 실 샘플 문서의 `Ave. Noise` 가 6.277 입니다. mock 의 밴드를 실데이터에 대면 **fab 전체가 hold** 로 잠깁니다 |

실제 스펙이 나오면 office 쪽(`_cd_spec`, `_bsm_bands`)을 먼저 고치고
`docs/datatables/README.md` 의 "아직 사무실 소스가 없는 항목" 에서 지우십시오.

## 사무실에서 먼저 할 일

CD 모니터링 recipe 는 **보통 그대로 두면 됩니다.** fab 마다 recipe 이름이
다르지만 모두 `CD_MONITOR` 로 시작하고(user-confirmed 2026-08-18) 같은 장비에서
주기적으로 도는 일반 측정이라, 기본 `CD_MONITOR*` wildcard 가 meas_hist 에서
그대로 찾아냅니다. `SKEWNONO_CD_MONITOR_RECIPE` 는 두 경우에만 씁니다 — 접두사를
벗어난 이름을 쓰는 fab, 또는 **패턴 크기가 다른 모니터 recipe 를 여러 개 도는**
fab(그대로 두면 서로 다른 CD 가 gate 값 하나로 평균됩니다).

정말 손대야 하는 것은 `SKEWNONO_AXIS_PARAM_MAP` 입니다. staged 진단의 2단계가
prefix 로 찾은 recipe 를, 3단계가 그 fab 의 parameter 어휘 전체와 방향 해석
결과를 출력합니다.

    .venv/bin/python -m back_dev_home.ebeam.pm_planning.providers.office R3

방향은 parameter 이름에 들어 있지만 이름 짓는 방식이 recipe·fab 마다 매우
다양합니다(user-confirmed 2026-08-18). 읽을 수 없는 이름은 그 행이 `cells` 에서
**버려지므로**(기본값 "X" 를 넣지 않습니다) 매핑해 주어야 합니다.

표의 키는 **(recipe, parameter) 쌍**입니다 — 같은 이름이라도 다른 recipe 에서는
다른 feature 를 재기 때문입니다. 양쪽 다 glob 을 받고 더 구체적인 규칙이 이기므로
작성 순서는 상관없습니다. 진단이 해석 실패한 쌍과 붙여 넣을 한 줄을 만들어 줍니다.

    SKEWNONO_AXIS_PARAM_MAP="ADI/*:*_HOR=X,ADI/*:*_VER=Y,ADI/CD_MONITOR_001:Para_13=X"

CD 모니터링 recipe 의 parameter 도 다른 측정에서 쓰는 평범한 이름들이므로
(user-confirmed 2026-08-18) 이 표 하나가 pm-planning 과 tttm 양쪽을 커버합니다.
자세한 이유는 tttm/MIGRATION.md 의 같은 절에 있습니다.

## Verify

    SKEWNONO_PM_PLANNING_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/pm_planning

집에서 어댑터의 계산 자체는 다음으로 검증합니다(사무실 접속 불필요):

    .venv/bin/python -m pytest tests/test_office_tttm_pm_planning.py
