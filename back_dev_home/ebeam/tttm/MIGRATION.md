# tttm — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/<tool_slug>/tttm/check

- Handler: `routes.py` → `data.get_tttm_check(tool_slug, fab_name,
  recipe_id, parameters, window_weeks, eqp_ids)`. `tool_slug` is validated against
  `SEM_TOOL_SLUGS` (400 if not `cdsem`/`hvsem`) before the data call.
  `fab_name` is a required query param (`?fab_name=...`, 400 if missing);
  `recipe_id` is optional; `parameter` is optional and **repeatable**
  (`?parameter=a&parameter=b` — the client's multi-select; the route folds it
  to the `parameters` tuple, blanks and duplicates dropped, request order
  kept); `window_weeks` is optional and defaults to 2; `eqp_id` is optional
  and **repeatable** exactly like `parameter` (`?eqp_id=A&eqp_id=B` — the
  client's tool multi-select; the same `_args` helper folds it to the
  `eqp_ids` tuple).
- **`window_weeks` is how far back to gather, AND how many runs per tool.**
  One of `_analysis_window.WINDOW_WEEKS_CHOICES` (`1`, `2`, `3`, `4`); the route
  refuses anything else with a 400 rather than clamping, and defaults an
  absent/blank value to `DEFAULT_WINDOW_WEEKS` (2). The adapter gathers runs
  from `anchor - 7 * window_weeks` days and asks `recent_runs` for
  `runs_per_tool(window_weeks)` = `RUNS_PER_TOOL_PER_WEEK * window_weeks`
  per tool — both move together on purpose. The lookback used to be a fixed
  60 days behind a fixed cap of 10 runs, which made the cap the real window:
  a tool measuring daily contributed its last ten days whatever the lookback
  said, and the page labelled that "1주". A window the user can widen has to
  widen the evidence. The trend spans the same window (there was a separate
  30-day trend cut-off; gone). Echo `window_weeks` on the payload, including
  on every `available: false` branch. Positional and undefaulted in `data.py`
  for the same reason `parameter` is: a stale `office.py` raises instead of
  answering over its own fixed window.
- **`eqp_ids` narrows the FLEET the comparison is computed over.** `()` means
  the whole fab fleet — the pre-existing behaviour, so a request that never
  sent the key computes exactly what it used to. Otherwise the shared
  `contracts.narrow_fleet` keeps only the requested tools, **in fleet order**
  (the roster indexes every matrix axis, so a reorder by the request would
  move a tool's row between two requests for the same fab), dropping unknown
  ids silently. Everything downstream — `tools`, every `SkewMatrixBlock`,
  `consensus_deviation`, `trend`, `epoch_markers`, `mdc_history` — is
  computed over the narrowed fleet, and `tools` on every branch is the
  narrowed roster, so the payload describes exactly the comparison the user
  asked for. A request naming fewer than two valid tools answers
  `available: false` with a summary saying the REQUEST named too few
  ("요청한 장비가 2대 미만이라 장비간 스큐를 볼 수 없습니다 — 2대 이상
  고르십시오."), not that the fab holds one tool. The office adapter narrows
  **BEFORE `recent_runs(..., roster, ...)`** — that is the whole optimisation:
  a user comparing two tools opens two tools' pickles, not the fab's hundreds
  of MinIO GETs (the `raw` diagnostics echo `requested_tools` so an office run
  can tell the narrowing from the answer). Positional and undefaulted in
  `data.py` (joined 2026-08-28) so a stale `office.py` copy raises a
  `TypeError` instead of silently ignoring the axis.
- **`parameters` narrows the rows, and only inside a recipe.** Each names
  one measured feature of `recipe_id` — a `parameter` value of the recipe's
  MSR rows, which is also what the payload's own `parameters` catalogue lists
  (below). The office adapter filters the MSR rows it computes pairwise skew
  from down to those features; an empty tuple means fold every feature
  together, the pre-existing behaviour, and several names fold exactly those
  (so the client's N배화 group is "tools that match on each of them"). The
  route refuses a `parameter` without `recipe_id` with a 400 before the data
  call, because the same parameter name in another recipe measures something
  else — so the adapter may assume that a non-empty `parameters` arrives with
  a `recipe_id`. Echo **both** back on the payload as `recipe_id` and
  `selected_parameters` (a list, request order), including on the
  `available: false` branch: the client files the response under the pair it
  asked for.
- **`parameters` is the catalogue `parameter` is picked from.** Every distinct
  named `parameter` across the recipe's run pickles in the window, sorted —
  the same rows the skew is computed from, so a name offered is one the filter
  can match (the client used to read this list from recipe-open's `.idp` over
  FTP, which failed for reasons unrelated to the recipe and could name
  features nobody measured). Always the **unfiltered** set even when
  `parameters` is set; `[]` without a `recipe_id` (names are recipe-local, so a
  pooled list would offer one name for several features) and on every
  `available: false` branch. Unnamed points (stabilisation shots) are excluded.
- **`parameter_profile` is the tool × parameter offset table the 장비 그룹
  배치도's PCA runs over** (the client computes the PCA —
  `front-dev-home/app/utils/parameterPca.ts`). One row per roster tool, one
  column per catalogue parameter (same names and order as `parameters`, and
  like it **never narrowed by the selection** — the client picks the columns,
  so selecting never refetches). Each entry is the tool's median CD for that
  parameter minus the fleet **median** for it (nm, signed), `None` when the
  tool did not measure it; a column only one tool measured is all `None`.
  `median_cd_nm` per column is the CD it was read at, so the client can scale
  each column by its own action limit before comparing pattern sizes. Build
  it with the shared `profile.build_parameter_profile(roster, names,
  samples)` — samples being each (tool, feature)'s per-run medians — never
  by hand: the mock and this template share that one derivation. Empty
  (`{parameters: [], tools: [], values: []}`) without a `recipe_id` and on
  every `available: false` branch.
- Contract: `TttmCheckPayload` (large nested tree — see `contracts.py` for
  the full `ToolRef`/`CellSkew`/`SkewMatrixBlock`/`ProductionCorroboration`/
  `FleetToday`/`TrendPoint`/`EpochMarker`/`MdcHistoryEntry` definitions) —

  ```python
  class TttmCheckPayload(TypedDict):
      tool_slug: ToolSlug
      fab_name: str
      recipe_id: str | None
      selected_parameters: list[str]  # the ?parameter= values, request order; [] = all folded
      parameters: list[str]        # every named feature the recipe's runs measured, sorted
      available: bool
      fetched_at: str
      summary: str
      tools: list[ToolRef]
      current_tolerance: float           # default 0.05 (nm)
      tolerance_range: ToleranceRange     # {min: 0.01, max: 0.20, step: 0.005}
      occupied_cells: list[CellSkew]
      parameter_profile: ParameterProfile  # tool × catalogue-parameter offsets, see above
      production_corroboration: ProductionCorroboration
      fleet_today: FleetToday
      trend: list[TrendPoint]
      epoch_markers: list[EpochMarker]
      mdc_history: list[MdcHistoryEntry]
      raw: NotRequired[dict[str, object]]
  ```

- Mock behavior: generates a deterministic payload per
  `tool_slug`/`fab_name`/`recipe_id`/`parameters`, seeded by crc32 of those
  four (pipe-separated, so `recipe_id` and the parameters cannot bleed into
  one another). The
  roster is **`sem_list` filtered to that fab and tool family**, deduplicated
  by `eqp_id` — the same physical tools every other screen shows for the fab,
  not an invented one. `__fixtures__/tttm_cdsem_r3.json` is no longer an
  input; it is a captured sample of this generator's output
  (`scripts/verify/capture_fixtures.py`). A fab holding no tool of the family returns
  an `available: false` empty payload (`tools: []`, `occupied_cells: []`, all
  list fields empty, `current_tolerance: 0.05`,
  `production_corroboration.level: "low"`, `parameters: []`) with a Korean summary saying so —
  this is the "unknown fab" case, not an error. A fab holding exactly one tool,
  and a recipe this fab has never measured, answer `available: false` the same
  way **but keep `tools`** (see the rule below). `recipe_id` and the selected
  parameters are echoed and also seed the numbers, so picking either visibly
  recomputes — the mock does not filter by parameter and stands in for the
  office's row filtering by moving the numbers, which is the property the UI
  depends on. `parameters` is the recipe's feature set from the msr_file
  mock's programs (`program_parameters`), the same programs its mock pickles
  come from; `parameter_profile` is fabricated from the same per-tool bias
  through the shared `profile.py`, with the drifted tool's last column `None`
  so the client's dropped-from-the-map path runs at home.

  **A recipe the fab has not measured is `available: false`, not a seeded
  payload.** The mock resolves the measured set through its own
  `get_tttm_recipes`, so the picker and the check cannot disagree about what
  "measured" means. This mirrors the office branch where `recent_runs` returns
  nothing for the recipe filter, and it exists because the earlier mock seeded a
  full comparison from ANY string: a stale stored `recipe_id` produced a
  confident payload at home and an empty one at the office, so the failure was
  first met on the company network.

  The server never computes N배화
  (maximal-clique) grouping; it only serves raw per-cell pairwise skew
  matrices and lets the client derive groupings.
- Office data source: **구현 완료(2026-08-18), 사무실 검증 대기.**
  `providers/office_example.py` 가 네 소스를 조인합니다 — 장비 명단은
  `sem_list`, 모든 스큐 숫자는 `meas_hist_{cdsem,hvsem}` 실행을 MinIO
  `dict_pkl` 로 풀어 얻은 CD 값, epoch 경계와 `mdc_history` 는
  `mdc_setting` 의 MinIO 아카이브, soft `epoch_markers` 는
  `fab_inform_notes`. 공용 코드는 `ebeam/_office_msr_cd.py`,
  `ebeam/_office_mdc.py`, `ebeam/_office_bm_pm.py` 이며 **tracked** 이므로
  `git pull` 로 갱신됩니다(`office.py` 만 `cp` 대상입니다).
- **`available: false` is built by `contracts.unavailable_payload`, not by hand.**
  Do not write your own — that function is imported by both providers precisely
  because two copies drifted once (the office copy took a `tools` argument and
  returned `[]`), and `tools` is a REQUIRED parameter so no branch can quietly
  decline to state a roster. Every unavailable branch except the genuinely empty
  one (no tool of this family in this fab) therefore returns the fab's `tools`. An empty comparison is not an empty fab, the client renders no
  matrix from an unavailable payload, and the tool picker shares a rail with the
  recipe picker — so blanking `tools` removes the controls the user needs to
  leave the empty state, at exactly the moment they need them.
  `fleet_today.matrix` and `occupied_cells` stay empty on this branch; those
  are the "comparison of nothing" the branch exists to refuse.
- Notes: `fetched_at` is volatile (stamp-at-request-time) and should be
  scrubbed by any parity harness rather than compared exactly. `direct_skew_matrix`/
  `predicted_skew_matrix` in each `CellSkew` are independently nullable —
  a cell with no data for a given tier is `None`, not an empty matrix.
  `SkewMatrixBlock.values` is symmetric with a zero diagonal; a `null` cell
  means that tool pair is not TTTM-able (no shared data), not zero skew.
  Every `ToolRef` owes an `eqp_model_cd` (raw `sem_list` model code — `CG6300`,
  `TP4500`, …): the picker groups its chips by it, so an adapter that omits it
  flattens an 18-tool fab into one unreadable chip row. `eqp_id` must be
  unique across `tools` — it indexes the matrix axes, and a repeat makes a
  tool appear to match itself.

## Endpoint: GET /api/&lt;tool_slug&gt;/tttm/recipes

- Handler: `routes.py` → `data.get_tttm_recipes(tool_slug, fab_name,
  window_weeks)`. Same slug, `fab_name` and `window_weeks` rules as
  `/tttm/check` — a picker scoped differently from the payload it drives
  offers recipes the check then finds nothing for, so the rows are counted
  over the check's window (`anchor - 7 * window_weeks` days) and the client
  re-fetches the list whenever the window moves.
- Contract: `TttmRecipeList` — `{tool_slug, fab_name, window_weeks,
  fetched_at, rows}` where each row is `{recipe_id, fab_name, runs, tools}`.
- **Sourced from measurement history, NOT the Redis recipe registry.**
  `recipe-search` reads `v3_{cdsem,hvsem}_unique_rcp_list`, which lists every
  recipe that EXISTS. On this screen a recipe nobody ran carries no information
  at all — picking it can only answer "no data" — so the picker is fed from
  `meas_hist_{cdsem,hvsem}` instead, filtered exactly the way `recent_runs`
  filters — `fab_name`, the same window, and the SAME shared
  `_office_msr_cd.has_pickle_clause()` (`exists(minio_pkl)`), not a second
  spelling of it. The measured set
  is also far smaller than the catalogue, which is what makes the picker usable.
- `recipe_id` is the `class/recipe` **full_name** where the source carries one,
  because that is the key the axis map scopes by and the identity
  `recent_runs` contrasts within. A picker offering a bare `recipe_name` would
  name something the rest of the pipeline keys differently.
- `tools` is the distinct tool count: **1 means no pair exists**, so no direct
  skew can come out of that recipe however many runs it has. Rows come back
  sorted by `(tools desc, runs desc, recipe_id)` and the client keeps that
  order, so the recipes that can actually support a comparison are on top.
- Office: one `composite` walk over `full_name.keyword` with a
  `cardinality(eqp_id.keyword)` sub-aggregation — not `terms`, which truncates
  at `size` silently and whose per-bucket totals are approximate.

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

## `tolerance_range` 는 절대 nm 이 아닙니다

`current_tolerance` 와 `tolerance_range` 가 실어 보내는 nm 은 **15 nm 모니터
wafer 기준값**입니다. 클라이언트는 이 값을 그 CD 에서의 action limit 대비
비율로 바꾼 뒤, 셀마다 그 셀의 실제 CD 로 되돌려 적용합니다. 즉 허용치는
패턴 크기에 비례해 커집니다.

| knob | 지수 | CD 15 nm | CD 31.8 nm | CD 68 nm |
| --- | --- | --- | --- | --- |
| 0.05 nm | 0.33× | 0.050 nm | 0.106 nm | 0.227 nm |
| 0.20 nm | 1.33× | 0.200 nm | 0.424 nm | 0.907 nm |

그래서 `max` 가 0.20 이어도 **0.20 nm 를 넘는 장비쌍이 통과할 수 있으며, 그것은
상한 위반이 아닙니다**. 이 표를 보지 않고 `max` 를 절대 상한으로 읽으면 셀별
실효 허용치를 0.20 에서 잘라내는 "수정"을 하게 되는데, 그것이 바로 사용자가
기각한 동작입니다.

user-confirmed 2026-08-16, 두 방향 모두: `max` 는 0.20 을 유지하고(Kawada 2009 의
±0.25 로 올리지 않음), 동시에 그 0.20 자체가 모니터 wafer 기준값이라 비례해서
커집니다. 두 답이 함께 있어야 합니다 — 앞의 것만 남기면 "0.20 은 절대 한계"로
읽히고, 그것은 사실이 아닙니다.

## 사무실에서 먼저 할 일 두 가지

계약을 만족시키는 데 필요한데 집에서는 알 수 없는 값이 두 개 있습니다. 둘 다
환경변수이며, 어댑터의 staged 진단이 실제 값을 출력합니다.

    .venv/bin/python -m back_dev_home.ebeam.tttm.providers.office cdsem R3

| 환경변수 | 무엇을 정하는가 | 안 맞으면 |
| --- | --- | --- |
| `SKEWNONO_AXIS_PARAM_MAP` | 어느 parameter 가 X 이고 어느 것이 Y 인지 | `occupied_cells` 가 **빈 채로** 돌아옵니다. summary 가 그 이유를 한국어로 말합니다 |

(`SKEWNONO_CD_MONITOR_RECIPE` 는 pm_planning 전용입니다 — tttm 은 recipe 를
사용자가 고릅니다.)

방향은 parameter 이름에 들어 있으나 이름 짓는 방식이 recipe·fab 마다 **매우
다양합니다**(user-confirmed 2026-08-18). 그래서 내장 정규식표만으로는 부족합니다.

표의 키는 이름 하나가 아니라 **(recipe, parameter) 쌍**입니다. 같은 이름이라도
다른 recipe 에서는 다른 feature 를 재기 때문이며, 이 화면의 `routes.py` 가
`parameter` 를 `recipe_id` 없이 거부하는 것과 같은 이유입니다. 문법은
`[<recipe>:]<parameter>=<X|Y>` 이고 양쪽 다 glob 을 받습니다.

    SKEWNONO_AXIS_PARAM_MAP="ADI/*:*_HOR=X,ADI/*:*_VER=Y,ADI/CD_MONITOR_001:Para_13=X"

더 구체적인 규칙이 이기므로 작성 순서는 상관없습니다 — 정확한 recipe >
recipe glob > 무범위, 각 단계 안에서 정확한 이름 > glob. fab 전체에 통하는
규칙이면 `recipe:` 접두사를 빼십시오. 진단이 해석 실패한 쌍을 전부 출력합니다.

측정 방향은 pickle 에도 meas_hist 에도 없습니다(`docs/datatables/hitachi/msr_file_pickle.txt`
참고). 어댑터는 parameter **이름**에서 되찾고, 읽을 수 없으면 그 행을 **버립니다**.
기본값 "X" 를 넣지 않는 이유는 계약의 `Axis` 가 두 값짜리 Literal 이라 측정된
사실과 구분되지 않고, 그러면 X 셀이 두 방향을 모두 담아 방향별 드리프트가
평균으로 지워지기 때문입니다. 빈 grid 는 시끄럽고, 틀린 axis 는 조용합니다.

## 빈 grid 를 봤을 때 읽는 순서

`occupied_cells` 가 비는 원인은 셋이고 화면에서는 똑같이 보이므로, payload 의
`summary` 가 어느 쪽인지 말합니다. 더 자세한 것은 응답의 `raw` 에 있습니다
(계약상 `NotRequired`, 클라이언트는 무시합니다).

| summary | 원인 | 조치 |
| --- | --- | --- |
| 측정한 이력이 없어 | 고른 parameter 가 한 행도 매칭하지 않음 | parameter 이름 확인 |
| 측정 방향 | axis 를 못 읽음 | `SKEWNONO_AXIS_PARAM_MAP` |
| 함께 측정한 | 두 대 이상이 함께 돈 recipe·parameter 가 없음 | feasibility 문서 6절 1번 — QC/매칭 recipe 존재 여부 |

## Verify

    SKEWNONO_TTTM_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/tttm

집에서 어댑터의 계산 자체는 다음으로 검증합니다(사무실 접속 불필요):

    .venv/bin/python -m pytest tests/test_office_tttm_pm_planning.py
