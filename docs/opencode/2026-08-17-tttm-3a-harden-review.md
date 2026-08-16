# TTTM 3a 레이아웃 2차 두 축 리뷰 (oc-review)

- 날짜: 2026-08-17
- 스킬: `oc-review` (Standards + Spec), 이어서 `/simplify` 4각 패스
- 모델: `glm-5.3` (`heavy`) — 23개 파일 · 약 2,100줄 추가
- 기준점: `b57fe504` → `HEAD` (`1612abf5`, `b5123df0`, `6f2a9c0d`)
- Standards 근거 문서: `CLAUDE.md`, `DESIGN.md`, `front-dev-home/app/assets/css/main.css`
- Spec: `.scratch/tttm-3a/design-3a.html`
- 결과 커밋: `96d352e4`, `e986cd97`

이 작업은 이미 1차 리뷰(`2026-08-16-tttm-3a-layout-review.md`)를 거친 코드입니다.
그래서 이번에는 얕은 지적 대신 **코드 구조와 잠복 버그**를 겨냥하도록 프롬프트를
좁혔습니다.

## 티어 선정

프런트엔드 전용 diff 라 `providers/`, `contracts.py`, `_runtime/`,
`docs/datatables/` 중 어느 escalation surface 도 건드리지 않았습니다. 다만 파일
수가 10개를 넘어 규칙표에 따라 `heavy` 로 실행했습니다.

## Standards 축 (원문)

> ## Review — TTTM 3a rebuild (`1612abf5` + fix `b5123df0`)
>
> Prior-pass items (sub-12px values, crimson link, `duration-150`, `signed()` triplication, `exceeds` fix, `scoreCells`/`applyTolerance` split) are confirmed fixed. Latent-bug hunt in the numeric helpers came back **clean**: `barFraction` guards `thresholdNm ≤ 0`/NaN; `countFailingPairs`' strict `>` is the exact complement of `buildAdjacency`'s `<=`; `excludedTools` captures `cell`/`thresholdNm` atomically with `blocker` so the pair, cell and threshold always describe the same row, and its `thresholdNm: 0` default for null-blockers is never rendered; `FleetStatus.maxAbs` is floored at `actionLimit × 1.15`, so no divide-by-zero on an empty/all-zero fleet. The maximality argument behind `ExcludedTool.exceeds` holds: a tool with all pairs measured-and-in-tolerance against every primary member would contradict clique maximality, so the three message branches are exhaustive and correct.
>
> ### Findings
>
> 1. **HARD — sub-12px data values, introduced by the fix commit.** `ExcludedTools.vue:73` (함께 빠짐 chips) and `FleetMap.vue` detached chips render eqp_ids through `.sk-signal-badge` (main.css:593, `font-size: 11px`). The class's own comment authorizes 11px because "the label NAMES a category" — an eqp_id is an identifier, which DESIGN.md §Semantic type classes lists under `.sk-value` ("table cell, stat text, **ID**"), and the sub-12px rule is "a data value never renders below 12px". The same fix commit raised the stress/endpoints to 12px while adding this new 11px value surface.
>
> 2. **JUDGEMENT — values in label colour, inconsistently between rail siblings.** `TttmView.vue` roll-up line (`점유 셀 N개 · 불합격 N쌍 · 최악 0.240 nm`) is entirely `.sk-field-label` = ink-subtle. The litmus ("value → ink; label → ink-muted"; ink-subtle is "disabled/de-emphasized") puts those numbers in full ink — and ScopePanel's count line three cards above does exactly that (`<strong class="…text-(--sk-ink)">`), so the rail contradicts itself. Same pattern in `PairMatrix.vue` header meta (`.sk-meta` carrying CD/threshold values).
>
> 3. **JUDGEMENT — Duplicated Code / inconsistent sibling prop shape.** The PM/BM action limit reaches siblings two ways: `FleetStatus.vue:77-78` computes `actionLimitNm(resolveNominalCd(...))` from its `fleet` prop; `ExcludedTools.vue` receives it as a prop from `TttmView.vue:238`'s identical `fleetActionLimit` computed. Same number, two mechanisms — tune one and the cards disagree.
>
> 4. **Carried-over latent crash, worth a line.** `subsetSkewMatrix` preserves *each matrix's own* tool order (tttmFleetSubset.ts:28), and `groupFromCells` throws unless all cells share one order (tttmGrouping.ts:139). Office cells returned in differing orders will throw inside `groups`, taking down the entire `v-else` (rail included). Pre-existing — the rebuild now routes every cell through it.
>
> No baseline smells beyond #3; no inline hex, cool-palette classes, or off-scale radii in added lines; `useTttmSettings` goes through `usePersistedState` as required.

## Spec 축 (원문)

> Read the spec, the diff, all `tttm/*.vue` components and the two new utils. Note: the diff itself contains a prior oc-review (`docs/opencode/2026-08-16-tttm-3a-layout-review.md`) that already adjudicated several deviations; findings below mark what is new.
>
> ## (a) Missing / partly done
>
> 1. **FleetMap group annotation — new finding, missed by the prior review.** The spec's map draws an ellipse around the recommended group with label "N배화 그룹 · 4대" (lines 170–171) and a dashed red connector HCDX392→ECDX204 annotated "0.240 nm" (lines 177–178). `FleetMap.vue` renders only a scatter with red/normal point coloring — no group boundary, no group-size label, no worst-pair link. The card's title "장비 그룹 배치도" (line 167) promises the 그룹; the plot never shows it.
> 2. App shell (header nav lines 23–41, CD/HV/VS/PR + fab rail lines 44–60) — absent from the diff, but pre-existing app chrome; agreed deliberate.
>
> ## (b) Scope creep (nobody asked for)
>
> 1. **Sticky rail** — `xl:sticky xl:top-2` in TttmView.vue:29. Spec line 267 explicitly defers it: `다음에 해볼 것: "레일을 스크롤에 고정해줘"`. Implemented anyway (adjudicated: kept).
> 2. **ScopePanel dropdown extras** — per-tool fleet-wide residual, "측정 없음" badge, 전체/해제 footer buttons, 100-row recipe cap message, "비교하려면 2대 이상" guard. Spec lines 101–103 specify only triggers like `CG6300 2/7` + chevron.
> 3. Smaller additions: "함께 빠짐" chips, FleetMap "지도에서 제외" row, CellSeverityList's extra parenthetical "(CD의 1% 규칙은 … 확장입니다.)" beyond spec line 194's text, RecommendationCard "목록" disclosure, MdcTimeline's "장비 N대" aggregation beyond line 256's `HCDX392 · 2건`.
>
> ## (c) Implemented but meaning differs from spec text
>
> 1. **Monitor-wafer CD is 15 nm, spec says 15.1 nm — new finding.** Spec line 124: "모니터 wafer 15.1 nm 기준." and line 125: "예: CD 68 nm 셀에서는 0.225 nm." `tttmLimits.ts:40` hardcodes `MONITOR_WAFER_CD_NM = 15`, so the knob caption prints "모니터 wafer 15 nm", the 68 nm example computes 0.227 nm, and the "0.33×" index is 0.05/0.15 not 0.05/0.151. The constant's comment cites a user quote ("모니터 wafer는 15nm에서") contradicting the mock — one of the two is wrong; worth confirming which.
> 2. **"불합격 장비쌍 N쌍" counts cell-occurrences, not pairs.** Spec line 132: "점유 셀 4개 · 불합격 장비쌍 4쌍" — 장비쌍 that fail. TttmView.vue:277-279 sums `failingPairs` across cells, so one pair failing in 3 cells counts 3×, then relabels "(셀 합계)". The number printed under the spec's words no longer has the spec's meaning (adjudicated: deliberate, but the dedup-vs-sum semantic difference was not stated in the adjudication).
> 3. **Trend span** — spec line 239: "최근 5주"; implementation prints the computed date range (adjudicated: kept).
> 4. **최약 장비쌍 order** — spec line 152: "0.048 nm · CD 대비 0.32×"; impl renders index first (adjudicated: kept, commented).
>
> Everything else — rail/results split, information order (판정 → 지도·셀 → 행렬 → 잔차·트렌드 → folds), stats, tolerance knob, captions, matrix tabs, fold panels — matches the spec's structure and copy.

## Claude 판단

### 인용 검증

HARD 로 표시된 지적은 인용된 규칙을 직접 열어 확인했습니다.

| 지적 | 인용 | 검증 결과 |
| --- | --- | --- |
| Standards 1 | `main.css:593` = 11px, `DESIGN.md` §Semantic type classes 의 `.sk-value` 항목이 ID 를 값으로 명시 | 사실입니다 |
| Standards 2 | `.sk-field-label` = ink-subtle (`main.css:662`), §Colors 의 litmus | 사실입니다 |
| Standards 3 | `FleetStatus.vue` 와 `TttmView.vue` 가 같은 수를 각자 유도 | 사실입니다 |
| Standards 4 | `tttmFleetSubset.ts:28`, `tttmGrouping.ts:135-141` | 사실이며, 목록에서 순위가 가장 잘못 매겨진 항목입니다 |
| Spec (a)1 | 스펙 170-178행의 타원·점선 | 사실입니다 |
| Spec (c)1 | `tttmLimits.ts:40` | **근거 없음** — 아래를 보십시오 |

### 순위를 바로잡습니다 — Standards 4 가 가장 중대합니다

모델은 이 항목을 "worth a line" 으로 맨 뒤에 두었지만, 두 축을 통틀어 가장
심각한 지적입니다. `groupFromCells` 는 셀을 **위치 인덱스로** 접고, 모든 셀의
tool 목록이 `cells[0]` 과 정확히 같지 않으면 예외를 던집니다. 그 예외는 렌더
중에 소비되는 computed 안에서 발생하므로 카드 하나가 아니라 `v-else` 전체,
즉 조작 레일까지 함께 사라집니다.

그리고 백엔드 계약이 그 불변식을 약속한 적이 없습니다. `contracts.py:34-37` 은
`tools` 가 `values` 의 두 축을 인덱싱한다는 것만 말하고, null 이 "이 셀에서 그
장비쌍은 데이터가 없다" 를 뜻한다고 명시합니다. 따라서 셀마다 다른 tool 목록을
돌려주는 office 어댑터는 **계약상 합법**입니다. 반면 `mock.py:245` 는 모든 셀을
한 헬퍼로 만들기 때문에 **집에서는 어떤 테스트를 추가해도 이 결함이 드러나지
않습니다.** `.claude/oc-project.md` 가 escalation surface 를 정의하는 바로 그
모양입니다.

### 모델이 틀린 곳 — Spec (c)1 은 근거가 없습니다

`MONITOR_WAFER_CD_NM = 15` 와 스펙의 15.1 은 **서로 다른 양**입니다.

- `15` 는 모니터 wafer 기준값이며 `tttmLimits.ts:24-31` 에 `user-confirmed
  2026-08-16` 로 출처가 붙어 있습니다 ("모니터 wafer는 15nm에서 +-0.15를 기준으로 함").
- `15.1` 은 mock 의 **측정된** fleet CD 중앙값입니다 (`mock.py:66`,
  `_FLEET_MEDIAN_CD_NM`). `FleetStatus.vue` 의 `cdBasis` 는 이미 이 값을
  `측정 CD 중앙값 15.1 nm` 로 정확히 출력합니다.

스펙 목업의 knob 캡션이 두 값을 뒤섞어 적었을 뿐이고, **코드가 목업보다
정확합니다.** 수정하지 않았습니다.

### 두 축이 모두 놓친 것

`DESIGN.md:162` 는 "ECharts 는 캔버스에 그리므로 sk-\* 클래스가 닿지 않는다,
`utils/chartType.ts` 가 그 문맥의 하한을 다시 적어 두었고 **이 화면의 모든
차트가 거기서 읽는다**" 고 못박습니다. `FleetMap.vue:183` 은 같은 eqp_id 를
그리면서 `fontSize: 11` 을 손으로 적고 있었습니다. Standards 축이 HTML 만 읽어
지나친, 1번과 같은 위반의 세 번째 지점입니다.

## 조치

| 지적 | 조치 |
| --- | --- |
| Standards 1 | `.sk-signal-badge` → `.sk-badge`. 단, "측정 없음" 과 등급 칩은 실제로 범주를 **가리키는** 라벨이라 11px 를 유지했습니다 |
| Standards 2 | roll-up 문장을 `.sk-meta` + 숫자를 `.sk-value-num` 으로 |
| Standards 3 | `fleetCd` 하나가 두 카드를 먹입니다. `FleetStatus` 는 실제로 읽는 잔차만 받습니다 |
| Standards 4 | `alignSkewMatrix` 신설, `cellInputs` 가 모든 셀을 선택 basis 로 정렬. 테스트 5개 추가 |
| Spec (a)1 | 그룹 경계 + 차단 장비쌍 점선을 그립니다 |
| Spec (c)1 | **거부** — 근거 없음 (위 참조) |
| Spec (b) 전부 | 1차 리뷰에서 이미 판정된 항목이라 유지 |
| Claude 추가 | `fontSize: 11` → `CHART_AXIS_LABEL` |

## `/simplify` 4각 패스

| 각도 | 결과 |
| --- | --- |
| Reuse | `utils/stats.ts` 의 `mean` 재구현 1건 → 교체 |
| Simplification | `blockedPair` 의 필드별 복사 제거, `FleetStatus` 의 prop 축소 |
| Efficiency | **조치 없음.** `chartOption` 은 이전부터 프레임마다 재빌드되고 있었고, 추가된 것은 datum 1개짜리 series 2개로 한정됩니다 |
| Altitude | 호출부에서 고친 것이 옳은 깊이라고 판정. 다만 `alignSkewMatrix` 는 `tttmGrouping` 으로 옮기라고 권고 → 반영 |

Altitude 축의 논거를 남겨 둘 만합니다. `groupFromCells` 가 스스로 정렬하게 하면
basis 를 **엔진이 지어내야** 하고(합집합 등), 그것은 사용자가 해제한 장비를 조용히
되돌리는 정책 결정이 됩니다. basis 는 호출부만 아는 값입니다.

## 검증

- `npm run typecheck` — 통과
- `npm run lint` — 오류 0 (경고 2건은 무관한 `ImageViewer.vue` 의 기존 항목)
- `npm test` — 1,570건 전부 통과 (신규 5건)
- 브라우저 — `/ebeam/cd-sem/R3/tttm` 을 직접 구동. 그룹 경계·점선·칩·roll-up 확인,
  tolerance 를 0.01↔0.20 으로 훑어도 페이지 유지, 콘솔 오류 0건

브라우저 확인에서 결함이 하나 더 나왔습니다. 라벨을 11px→13px 로 올리자 17대
선택 상태의 클러스터에서 라벨이 겹쳐 읽을 수 없게 되었습니다. `moveOverlap`
뒤에 `hideOverlap` 를 붙여 옮길 수 없는 라벨은 숨기도록 고쳤습니다 (`e986cd97`).
정적 diff 만 읽은 두 축은 찾을 수 없는 종류의 결함입니다.
