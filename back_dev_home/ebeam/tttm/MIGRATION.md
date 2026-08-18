# tttm — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/<tool_slug>/tttm/check

- Handler: `routes.py` → `data.get_tttm_check(tool_slug, fab_name,
  recipe_id, parameter)`. `tool_slug` is validated against `SEM_TOOL_SLUGS`
  (400 if not `cdsem`/`hvsem`) before the data call. `fab_name` is a required
  query param (`?fab_name=...`, 400 if missing); `recipe_id` and `parameter`
  are optional query params.
- **`parameter` narrows the rows, and only inside a recipe.** It names one
  measured feature of `recipe_id` (a `Parameter` value of that recipe's
  `idp_image_info` — the same catalogue `GET
  /api/<slug>/recipe-search/parameters` lists). The office adapter filters the
  MSR rows it computes pairwise skew from down to that feature; `None` means
  fold every feature together, the pre-existing behaviour. The route refuses
  `parameter` without `recipe_id` with a 400 before the data call, because the
  same parameter name in another recipe measures something else — so the
  adapter may assume that a non-null `parameter` arrives with a `recipe_id`.
  Echo **both** back on the payload, including on the `available: false`
  branch: the client files the response under the pair it asked for.
- Contract: `TttmCheckPayload` (large nested tree — see `contracts.py` for
  the full `ToolRef`/`CellSkew`/`SkewMatrixBlock`/`ProductionCorroboration`/
  `FleetToday`/`TrendPoint`/`EpochMarker`/`MdcHistoryEntry` definitions) —

  ```python
  class TttmCheckPayload(TypedDict):
      tool_slug: ToolSlug
      fab_name: str
      recipe_id: str | None
      parameter: str | None        # one measured feature of recipe_id
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

- Mock behavior: generates a deterministic payload per
  `tool_slug`/`fab_name`/`recipe_id`/`parameter`, seeded by crc32 of those
  four (pipe-separated, so `recipe_id` and `parameter` cannot bleed into one
  another). The
  roster is **`sem_list` filtered to that fab and tool family**, deduplicated
  by `eqp_id` — the same physical tools every other screen shows for the fab,
  not an invented one. `__fixtures__/tttm_cdsem_r3.json` is no longer an
  input; it is a captured sample of this generator's output
  (`scripts/capture_fixtures.py`). A fab holding fewer than two tools of the
  family (or none at all) returns an `available: false` empty payload
  (`tools: []`, `occupied_cells: []`, all list fields empty,
  `current_tolerance: 0.05`, `production_corroboration.level: "low"`) with a
  Korean summary saying which of the two it was — this is the "unknown fab"
  case, not an error. `recipe_id` and `parameter` are echoed and also seed the
  numbers, so picking either visibly recomputes — the mock has no parameter
  catalogue of its own and stands in for the office's row filtering by moving
  the numbers, which is the property the UI depends on. The server never computes N배화
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
| (tttm 은 recipe 를 사용자가 고르므로 `SKEWNONO_CD_MONITOR_RECIPE` 는 pm_planning 전용입니다) | — | — |

측정 방향은 pickle 에도 meas_hist 에도 없습니다(`docs/datatables/msr_file_pickle.txt`
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
