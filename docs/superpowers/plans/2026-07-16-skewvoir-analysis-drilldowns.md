# Skewvoir 상세 분석 워크스페이스 Implementation Plan

> **Status:** 설계·구현 계획 초안 완료, 사용자 검토 및 구현 대기입니다. 이 문서는 구현 순서와 검증 gate이며 현재 작업에서 UI 코드는 변경하지 않습니다.

**Goal:** `측정 개요`를 빠른 summary/router로 유지하면서 `위치 비교`, `Time-Series`, `상관 / 분포`, `이미지 갤러리`를 단일 MSR 진단과 다중 MSR 비교에 각각 유용한 엔지니어링 workbench로 재구성합니다.

**Design:** [2026-07-16-skewvoir-analysis-drilldowns-design.md](../specs/2026-07-16-skewvoir-analysis-drilldowns-design.md)

**Research:** [wafer-analysis-method-research.md](../../issues/skewvoir/wafer-analysis-method-research.md), [analysis-drilldown-benchmark-research.md](../../issues/skewvoir/analysis-drilldown-benchmark-research.md)

**Architecture:** 기존 URL-driven workspace와 `useSkewvoirAnalysis`를 유지합니다. 공통 context/manifest 계층을 먼저 만들고, 페이지별 계산은 framework-free utility로 분리합니다. 원시 데이터는 `meas_hist`와 `msr_file` 계약을 사용하며 office 전환은 기존 `routes.py → data.py → providers/mock.py|office.py` seam에서 처리합니다. 다중 분석은 compatibility gate를 통과한 MSR만 사용하고, baseline 기반 분석은 별도 계약이 준비될 때까지 descriptive mode로 제한합니다.

**Tech Stack:** Nuxt 4, Vue 3, TypeScript, Nuxt UI, ECharts 6, Flask provider seam, Node test runner, ESLint, Nuxt typecheck, markdownlint-cli2.

---

## 0. 구현 원칙

1. `측정 개요`는 계속 focus MSR 한 건을 빠르게 로드합니다. 상세 비교 때문에 초기 Dashboard가 set fan-out을 지불하지 않습니다.
2. 단일 MSR과 다중 MSR은 같은 메뉴를 공유하지만 질문·grain·empty state가 다릅니다.
3. 다중 계산은 `선택 수`가 아니라 `호환 MSR 수`를 기준으로 합니다.
4. overview, spatial, trend, relationship, image evidence를 하나의 health score로 합치지 않습니다.
5. 현재 mock의 `health`와 placeholder `spm_dict`는 모든 판정·검증 경로에서 제외합니다.
6. 각 task는 framework-free 계산 test → component wiring → live evidence 순서로 닫습니다.
7. UI 구현 중 [wafer map enhancement design](../specs/2026-07-16-skewvoir-wafer-map-enhancement-design.md)과 겹치는 `WaferMap.vue`, `RadiusChart.vue`, `dashboard/RadiusPlot.vue`, `dashboard/MeasurementPoints.vue` 변경은 **Task 0에서 먼저 착륙시킨 뒤** 그 결과 위에서 시작합니다.

## 1. 단계와 의존성

```text
C0 분석 범위·호환성·연결 선택
 ├─ C1 위치 비교
 ├─ C2 Time-Series
 ├─ C3 상관 / 분포
 └─ C4 이미지 갤러리
       ↓
C5 측정 개요 hand-off + cross-page QA
       ↓
C6 승인 baseline / variance / advanced research (별도 계획)
```

C1~C4는 C0 이후 서로 독립적으로 구현할 수 있습니다. 한 번에 네 페이지를 바꾸지 않고
각 페이지를 vertical slice로 출하합니다.

## 2. Phase-1 완료 경계 (mock backend)

이 계획의 모든 Task를 Phase 1(offline mock) 안에서 "완료"로 볼 수 없습니다. mock
`msr_file`은 `site_layout_id`/layout hash, coordinate-transform version, recipe revision,
sequence timestamp, 승인 baseline, USL/LSL, image ROI/edge/line-profile, reference
artifact를 제공하지 않습니다. 따라서 Task를 다음처럼 구분합니다.

| 구분 | Task | Phase-1에서의 상태 |
| --- | --- | --- |
| Phase-1 buildable·verifiable | Task 1~5, 7, 9, 11, 13, 14 | C0 공통 계층, 단일 MSR 진단, review-queue gallery, hand-off를 mock 데이터로 live-verify 합니다. |
| Office-contract-gated | Task 6, 12 | canonical layout/좌표·image evidence 계약이 연결된 뒤에만 live-verify 합니다. Phase-1에서는 readiness `unavailable` placeholder까지만 만듭니다. |
| Partially gated | Task 8, 10 | descriptive run chart·tool/lot 층화(8), MSR-grain pooled/stratified(10)는 mock으로 가능합니다. control chart·recipe-revision facet(8), capability·variance·spatial/same-site 연결(10)은 계약 대기입니다. |

Office-contract-gated Task는 실제 계약 없이 UI를 완성하지 않습니다. 각 Task 아래
entry gate를 명시하고, 계약이 없으면 clearly-labeled fixture로만 렌더하되 화면에
`office 계약 대기`를 표시합니다. Phase-1 출하 "완료" 조건은 buildable Task와 partially
gated Task의 mock-가능 부분입니다.

---

## Task 0: 진행 중 wafer-map 작업 선착륙 (gating)

**이유:** 현재 worktree에 커밋되지 않은
[wafer map enhancement](../specs/2026-07-16-skewvoir-wafer-map-enhancement-design.md)
변경이 이 계획과 같은 파일을 건드립니다. 충돌을 피하기 위해 먼저 착륙시킵니다.

**Files (선착륙·병합 확인 대상):**

- `front-dev-home/app/components/ebeam/skewvoir/WaferMap.vue`
- `front-dev-home/app/components/ebeam/skewvoir/RadiusChart.vue`
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/RadiusPlot.vue`
- `front-dev-home/app/components/ebeam/skewvoir/dashboard/MeasurementPoints.vue`

**Gate:**

- [ ] wafer-map enhancement 변경을 커밋하여 위 파일에 대해 `git status`가 clean이 됩니다.
- [ ] clean 이전에는 Task 5/6/13을 시작하지 않습니다.

---

## Task 1: 현재 동작을 characterization test로 고정

**Files:**

- Read: `front-dev-home/app/composables/useSkewvoirRoute.ts`
- Read: `front-dev-home/app/composables/useSkewvoirWorkspace.ts`
- Read: `front-dev-home/app/composables/useSkewvoirAnalysis.ts`
- Read: `front-dev-home/app/components/ebeam/skewvoir/views/{Dashboard,PositionStack,TimeSeries,Correlation,Gallery}.vue`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/currentContracts.test.ts`

**Steps:**

- [ ] URL의 `msr`, `msrs`, `mp`, `view` parsing/serialization 사례를 test fixture로 고정합니다.
- [ ] `msrs` 순서, focus MSR, 30개 trend cap, missing MSR 처리의 현재 동작을 기록합니다.
- [ ] 단일 Dashboard만 열 때 `fetchMsrFiles`가 실행되지 않는 lazy-load invariant를 확인합니다.
- [ ] `msr_file.rows`의 nullable `cd_value`와 parameter별 단위를 fixture에서 보존합니다.
- [ ] 현재 Position Stack이 chip coordinate를 직접 합성하고 Correlation/Gallery가 focus file만 사용하는 한계를 test name 또는 주석으로 명시합니다.

**Verify:**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run typecheck
```

**Commit:** `test(skewvoir): characterize analysis workspace contracts`

---

## Task 2: 분석 truth types와 compatibility manifest 추가

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/types.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/compatibility.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/compatibility.test.ts`
- Modify: `front-dev-home/app/composables/useMsrFileApi.ts`
- Modify: `back_dev_home/msr_file/providers/mock.py`
- Modify: `back_dev_home/msr_file/providers/office.py`
- Add: `back_dev_home/msr_file/tests/test_contract.py`
- Add: `docs/api-contracts/msr-file.yaml`

**Interfaces:**

- `AnalysisScope = 'single' | 'set'`
- `CompatibilitySignature`
- `CompatibilityGroup`
- `AnalysisManifest`
- `Readiness = { status: 'ready' | 'limited' | 'unavailable', reasons: string[] }`
- `CanonicalSiteKey`
- `ReferenceDescriptor`

**Steps:**

- [ ] signature에 recipe identity/revision, parameter/unit, method/object/kind, mag/vac/pixel, coordinate metadata, wafer size, site-layout hash를 정의합니다.
- [ ] 현재 데이터에 없는 필드는 `unknown`으로 보존합니다. unknown끼리 같다고 판정하지 않습니다.
- [ ] mock provider는 생성에 사용한 recipe/layout 정보를 명시적으로 응답합니다. 화면 결과를 맞추기 위해 숨은 값으로 compatibility를 조작하지 않습니다.
- [ ] office adapter는 canonical metadata가 연결되기 전 `NotImplemented` 또는 limited reason을 반환하도록 계약을 문서화합니다.
- [ ] `buildAnalysisManifest(focus, files, parameter)`가 포함/제외/group/readiness를 계산합니다.
- [ ] 동일 layout이 아니면 multi delta, variability, same-site gallery readiness가 `unavailable`이 되는 test를 작성합니다.
- [ ] 일부 site만 겹치면 common coverage와 `limited`가 되는 test를 작성합니다.
- [ ] backend contract test로 mock provider가 선언한 signature 필드를 실제로 emit하고, 계약에 없는 필드(layout hash·recipe revision·sequence timestamp 등)는 응답에 나타나지 않음을 고정합니다.
- [ ] office adapter가 canonical metadata 연결 전 `NotImplemented` 또는 limited reason을 반환하는 계약을 backend test로 고정합니다.

**Acceptance:**

- 사용자가 12개를 골라도 화면은 `12 선택 · 10 로드 · 8 호환 · 2 제외`를 재현 가능하게 설명합니다.
- 제외 reason code는 recipe/layout/unit/method/metadata missing을 구분합니다.

**Verify:**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run lint
npm --prefix front-dev-home run typecheck
python -m pytest back_dev_home/msr_file   # mock signature 필드 + office NotImplemented/limited 계약
```

**Commit:** `feat(skewvoir): add analysis compatibility manifest`

---

## Task 3: 공통 분석 context와 shareable state 구성

**Files:**

- Modify: `front-dev-home/app/composables/useSkewvoirRoute.ts`
- Modify: `front-dev-home/app/composables/useSkewvoirWorkspace.ts`
- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/workspace/AnalysisContextBar.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/workspace/ReadinessDrawer.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/Workspace.vue`

**Interfaces:**

- URL: `scope`, `site`, `ref`, `metric`, `grain`, `x`, `y`
- `analysis.manifest`
- `analysis.focusedSite`
- `analysis.reference`
- `analysis.setFocusedMsr(msr)`
- `analysis.setFocusedSite(siteKey | null)`

**Steps:**

- [ ] `scope=single|set`을 selection count와 별도 보존합니다. 다중 set에서 focus는 기존 `msr`입니다.
- [ ] route parsing은 잘못된 query를 안전한 default로 정규화하고 기존 공유 링크를 계속 엽니다.
- [ ] `wantSet`을 `time-series|position-stack` 하드코딩에서 `scope=set`인 상세 페이지 전체로 일반화합니다. Dashboard는 제외합니다.
- [ ] 공통 context bar에 scope, focus, parameter, compatible/excluded count, reference provenance, set editor를 표시합니다.
- [ ] readiness drawer에 group 구성, 제외 MSR과 이유, capability별 ready/limited/unavailable을 표시합니다.
- [ ] parameter 또는 focus group이 바뀌어 site key가 유효하지 않으면 linked site를 reset합니다.
- [ ] keyboard shortcut 1~5와 combobox guard의 기존 동작을 유지합니다.

**Acceptance:**

- Time-Series에서 편집한 비교 세트가 위치/상관/갤러리에 동일하게 나타납니다.
- 공유 URL을 새 탭에서 열면 scope, focus, parameter, site, reference가 복원됩니다.
- Dashboard만 열 때 set batch request는 발생하지 않습니다.

**Commit:** `feat(skewvoir): add shared analysis context and readiness`

---

## Task 4: 공통 feature table과 provenance 구축

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/features.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/features.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/ProvenanceDrawer.vue`
- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts`

**Interfaces:**

- `MsrFeatureRow`
- `FeatureDefinition = { id, label, unit, grain, source, aggregation, family }`
- `DerivedValue<T> = { value, unit, n, missing, transform, reference, version }`
- `analysis.featureRows`
- `analysis.featureRegistry`

**Steps:**

- [ ] MSR별 level/spread/coverage/failure/spatial/fixed FDC/dynamic FDC summary를 한 행으로 만듭니다.
- [ ] dynamic FDC는 mean/std/range/robust slope/missing을 sequence grain에서 먼저 축약합니다.
- [ ] feature마다 source, unit, aggregation, missing을 보존합니다.
- [ ] 서로 다른 단위의 parameter를 자동 합산하지 않습니다.
- [ ] current mock `health`와 `spm_dict`가 feature registry에 들어가지 않는 test를 작성합니다.
- [ ] chart/table의 `근거 보기` action이 provenance drawer를 열도록 공통 contract를 만듭니다.

**Acceptance:**

- Time-Series와 다중 Correlation이 같은 feature value를 재계산하지 않고 공유합니다.
- export 가능한 모든 derived value가 raw source와 transform으로 추적됩니다.

**Commit:** `feat(skewvoir): build grain-safe MSR feature table`

---

## Task 5: 위치 비교 단일 MSR — 공간 진단

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/spatial.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/spatial.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SpatialLayerMap.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/RadialProfile.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SectorProfile.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SiteEvidenceDrawer.vue`
- Modify (branch-by-abstraction): `front-dev-home/app/components/ebeam/skewvoir/views/PositionStack.vue`

**Steps:**

- [ ] 기존 composite-mean 뷰를 즉시 삭제하지 않고, 새 단일-MSR workbench를 flag/조건 뒤에 붙여 verify 전까지 기존 화면이 계속 동작하게 합니다.
- [ ] raw, median-centered, residual, failure layer를 정의합니다.
- [ ] radius bin별 median/spread/N과 검증된 notch 기반 sector summary를 계산합니다.
- [ ] coordinate readiness가 부족하면 raw layer와 table만 남기고 이유를 표시합니다.
- [ ] sequence scan-path overlay로 공간과 측정 순서의 혼재를 확인할 수 있게 합니다.
- [ ] map/profile/table/SEM preview를 `focusedSite`로 연결합니다.
- [ ] Answer strip은 center-edge delta, direction contrast, largest local residual, coverage를 별도 evidence로 표시합니다.
- [ ] 단일 MSR에서 wafer-to-wafer σ를 계산하지 않는 test를 고정합니다.

**Live verification:**

- CD-SEM과 HV-SEM 각각에서 raw→centered→failure layer를 전환합니다.
- map site 클릭 시 profile/table/SEM이 같은 site로 이동합니다.
- coordinate metadata를 제거한 fixture에서는 sector가 `평가 불가`가 됩니다.

**Commit:** `feat(skewvoir): turn position view into single-MSR spatial diagnosis`

---

## Task 6: 위치 비교 다중 MSR — reference/delta workbench

> ⚠ **Office-contract-gated (Phase-1 제외).** Entry gate: canonical layout/좌표 identity
> 계약(§10.2 PhysicalSiteKey)이 backend에 연결되어야 합니다. Phase-1 mock에서는 layout이
> `unknown`이므로 delta/variability map을 만들지 않고 readiness `unavailable`과 필요한
> 계약만 표시합니다.

**Files:**

- Extend: `front-dev-home/app/utils/skewvoirAnalysis/spatial.ts`
- Extend: `front-dev-home/app/utils/skewvoirAnalysis/spatial.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SpatialComparison.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/SiteHistory.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/position/WaferSmallMultiples.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/PositionStack.vue`

**Steps:**

- [ ] leave-focus-out site median reference, focus delta, site variability, coverage를 계산합니다.
- [ ] focus를 reference 계산에서 제외하는 test를 작성합니다.
- [ ] 공통 site가 없는 MSR은 계산에서 조용히 빠지지 않고 manifest exclusion으로 보냅니다.
- [ ] reference와 delta가 첫 화면이 되도록 하고 current Composite Mean은 secondary layer로 내립니다.
- [ ] 모든 비교 map은 pin scale을 지원합니다.
- [ ] selected site의 MSR history와 same-site Gallery hand-off를 연결합니다.
- [ ] center-corrected RMSE/correlation은 `pattern similarity`로만 표시하고 fault label을 생성하지 않습니다.

**Acceptance:**

- focus를 바꾸면 reference가 다시 계산되며 delta 0 고정 버그가 없습니다.
- variability tooltip은 σ/MAD와 함께 site별 valid MSR N을 표시합니다.
- layout 불일치 세트는 false alignment map을 만들지 않습니다.

**Commit:** `feat(skewvoir): add compatible-set spatial comparison`

---

## Task 7: Time-Series 단일 MSR — sequence와 dynamic FDC 연결

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/sequence.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/sequence.test.ts`
- Reuse/Modify: `front-dev-home/app/components/ebeam/skewvoir/FdcSequenceTrend.vue`
- Reuse/Modify: `front-dev-home/app/components/ebeam/skewvoir/FdcScatter.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceWorkbench.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/SequenceEventLane.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/TimeSeries.vue`

**Steps:**

- [ ] 단일 scope에서 제목과 X축을 `측정 순서 (Sequence)`로 바꿉니다.
- [ ] CD와 dynamic FDC를 shared cursor를 가진 stacked pane으로 표시합니다.
- [ ] start/end/range/robust slope/missing을 계산하고 단위를 `per sequence`로 표시합니다.
- [ ] failure/image/alignment evidence를 sequence event lane에 배치합니다.
- [ ] sequence cursor를 wafer scan path와 `focusedSite`에 연결합니다.
- [ ] 단위가 다른 CD/FDC를 한 Y축에 합치지 않습니다.
- [ ] home mock에서 CD와 dynamic FDC가 공통 `health` scalar로 결합됨을 pane meta에 `데모 데이터 · 방법 검증 불가`로 표시합니다.
- [ ] sequence timestamp가 없을 때 초당 slope와 time lag UI가 나타나지 않는 test를 작성합니다.

**Acceptance:**

- cursor 한 번으로 CD, FDC, wafer 위치, image가 같은 sequence를 가리킵니다.
- dynamic FDC가 없는 MSR은 CD sequence만 보여주고 `FDC 없음`을 원인과 함께 표시합니다.

**Commit:** `feat(skewvoir): add single-run sequence and FDC workbench`

---

## Task 8: Time-Series 다중 MSR — run chart와 event context

> ⚠ **Partially gated.** descriptive run chart와 tool/lot 층화는 Phase-1 mock으로
> 구현·verify 합니다. control chart(I-MR/EWMA/CUSUM)와 recipe-revision facet은 승인
> baseline·recipe revision 계약이 없으므로 disabled readiness로만 두고 Phase-1 완료
> 조건에서 제외합니다.

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/trend.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/trend.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/MetricPicker.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/RunChart.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/EventLane.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/timeseries/StratifiedTrends.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/TimeSeries.vue`

**Steps:**

- [ ] metric picker를 level/spread/completeness/spatial/tool evidence family로 구성합니다.
- [ ] 기본 화면을 CD level, uniformity(WCDU·MAD), measurement quality, tool context의 네 lane으로 구성하고 같은 시간 cursor로 연결합니다.
- [ ] metric picker는 evidence family를 한 score로 합치지 않고 각 lane의 대표 metric만 바꿉니다.
- [ ] tool/lot/recipe revision/maintenance regime color·facet을 제공합니다.
- [ ] 실제 timestamp와 irregular elapsed gap을 시각적으로 보존합니다.
- [ ] 현재 peer `%/σ` control을 `선택 집합 탐색 편차`로 재명명합니다.
- [ ] 승인 baseline이 없으면 I-MR/EWMA/CUSUM control을 숨기지 말고 disabled readiness로 설명합니다.
- [ ] spec/engineering/control limit이 같은 style을 공유하지 않도록 theme token을 분리합니다.
- [ ] point 클릭으로 focus MSR을 변경하고 다른 페이지에 상태를 전달합니다.

**Deferred in this task:**

- 승인 baseline registry와 control limit 계산입니다.
- hardware service의 실제 pre/during/post event-time join입니다.
- 자동 change-point의 공식 판정 사용입니다.

**Acceptance:**

- 선택 집합을 바꿔도 공식 control limit처럼 보이는 새 한계선이 자동 생성되지 않습니다.
- tool을 facet하면 pooled trend와 각 tool trend의 차이를 확인할 수 있습니다.
- MSR point에서 raw feature provenance와 측정 개요로 이동할 수 있습니다.

**Commit:** `feat(skewvoir): add stratified multi-MSR run charts`

---

## Task 9: 상관 / 분포 단일 MSR — exact-pair factor explorer

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/relationships.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/QueryBuilder.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/CorrelationScatter.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/DistributionChart.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/RelationshipSummary.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/PairedEvidenceTable.vue`
- Modify (branch-by-abstraction): `front-dev-home/app/components/ebeam/skewvoir/views/Correlation.vue`

**Steps:**

- [ ] 기존 focus-only scatter/분포 뷰를 verify 전까지 유지하고, 새 exact-pair explorer를 flag 뒤에 붙입니다.
- [ ] canonical site(PhysicalSiteKey) 또는 same sequence exact join만 허용합니다. CD↔FDC·X↔Y처럼 서로 다른 parameter는 parameter를 뺀 PhysicalSiteKey로 join합니다.
- [ ] Pearson r, Spearman ρ, pair N, missing N, constant-variable readiness를 계산합니다.
- [ ] active query가 scatter, marginal distribution, group distribution, evidence table을 함께 갱신합니다.
- [ ] histogram 외에 ECDF를 기본 비교 후보로 추가하고 box/violin 위에 raw point 또는 N을 표시합니다.
- [ ] radius/sector group은 coordinate readiness를 통과한 경우만 제공합니다.
- [ ] CD↔dynamic FDC는 같은 MSR+sequence join임을 chart meta에 표시합니다.
- [ ] home mock에서 CD와 dynamic FDC는 공통 `health` scalar로 결합되므로, 이 데이터의 CD↔FDC 상관 chart에 `데모 데이터 · 방법 검증 불가` 표식을 붙입니다.
- [ ] correlation이 `연관이며 원인 증명이 아님`이라는 문구를 항상 표시합니다.

**Acceptance:**

- pair가 0이거나 한 축이 상수이면 `r=0`이 아니라 평가 불가입니다.
- 다른 parameter의 missing row가 index 순서로 잘못 짝지어지지 않습니다.
- scatter point 클릭 시 focused site와 SEM preview가 연결됩니다.

**Commit:** `feat(skewvoir): add paired-site relationship explorer`

---

## Task 10: 상관 / 분포 다중 MSR — stratified feature analysis

> ⚠ **Partially gated.** MSR-grain pooled/stratified 관계는 Phase-1 mock으로
> 구현·verify 합니다. Cp/Cpk(spec 계약), variance component, 그리고 PhysicalSiteKey가
> 필요한 spatial·same-site 연결은 계약 대기로 두고 Phase-1 완료 조건에서 제외합니다.

**Files:**

- Extend: `front-dev-home/app/utils/skewvoirAnalysis/relationships.ts`
- Extend: `front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/FeatureMatrix.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/StratifiedEstimate.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/factor/GroupDistribution.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Correlation.vue`

**Steps:**

- [ ] grain을 MSR로 고정하고 Task 4의 feature row를 사용합니다.
- [ ] 전체 pooled scatter와 tool별 estimate를 나란히 보여줍니다.
- [ ] color/facet을 tool, lot, maintenance regime, recipe revision에서 고릅니다.
- [ ] correlation matrix cell을 선택하면 X/Y query로 drill-down합니다.
- [ ] discovery matrix는 multiple comparison 경고와 feature/missing count를 표시합니다.
- [ ] authoritative spec metadata가 없으면 Cp/Cpk와 out-of-spec count를 제공하지 않습니다.
- [ ] variance component는 readiness placeholder만 제공하고 별도 C6 계획으로 미룹니다.
- [ ] home mock CD↔FDC 결과에는 `데모 데이터 · 방법 검증 불가` 표식을 표시합니다.

**Acceptance:**

- pooled 관계와 tool별 관계가 반대인 fixture에서 둘 다 보이며 하나로 요약되지 않습니다.
- site row 수가 MSR grain N을 부풀리지 않습니다.
- feature tooltip에 source, unit, aggregation window, missing이 있습니다.

**Commit:** `feat(skewvoir): add stratified MSR feature analysis`

---

## Task 11: 이미지 갤러리 단일 MSR — priority review queue

**Files:**

- Add: `front-dev-home/app/utils/skewvoirAnalysis/gallery.ts`
- Add: `front-dev-home/app/utils/skewvoirAnalysis/gallery.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/ReviewFilters.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/EvidenceCard.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/ImageEvidenceDrawer.vue`
- Modify (branch-by-abstraction): `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue`

**Steps:**

- [ ] 기존 filename grid를 verify 전까지 유지하고, 새 review-queue를 flag 뒤에 붙입니다.
- [ ] image row를 failure, residual, vendor-score-monitor, sequence reason으로 분류합니다. `abnormal/watch` site verdict는 **판정 provenance가 제공될 때만** 분류 근거로 쓰고, mock `health`로 유도하지 않습니다(§0.5).
- [ ] 기본 sort는 failure → residual magnitude → sequence입니다. verdict provenance가 있을 때만 abnormal/watch를 failure 다음 우선순위로 삽입합니다.
- [ ] vendor score는 monitoring badge만 만들고 verdict reason에는 포함하지 않습니다.
- [ ] card에 chip/MP, sequence, parameter/value/unit, residual, reason을 표시합니다.
- [ ] virtualized/lazy grid와 per-image retry를 적용합니다.
- [ ] viewer에서 pan/zoom, physical scale bar, keyboard 이전/다음, metadata, wafer 위치 이동을 제공합니다.
- [ ] backend가 ROI/edge/CD gauge/line profile과 algorithm version을 제공하면 measurement-evidence layer를 표시하고, 없으면 capability를 숨긴 채 `원본 image만 제공됨`을 표시합니다.
- [ ] charging/contrast, focus/astigmatism, image drift, contamination/repeat exposure, edge algorithm, pixel calibration을 pattern verdict와 분리된 `artifact 의심` review tag로 제공합니다.
- [ ] focused site를 map/table/gallery가 공유합니다.

**Acceptance:**

- `이상·실패 우선` filter가 근거가 있는 image만 보여줍니다.
- image가 없어도 site evidence row는 사라지지 않고 `이미지 없음`을 표시합니다.
- image URL 1개 실패가 전체 Gallery loading state를 막지 않습니다.

**Commit:** `feat(skewvoir): turn gallery into visual evidence queue`

---

## Task 12: 이미지 갤러리 다중 MSR — same-site filmstrip

> ⚠ **Office-contract-gated (Phase-1 제외).** Entry gate: PhysicalSiteKey(§10.2)와
> image acquisition/scale metadata 계약이 필요합니다. Phase-1 mock에서는 canonical
> site를 확정할 수 없으므로 filmstrip을 만들지 않고 readiness `unavailable`을 표시합니다.

**Files:**

- Extend: `front-dev-home/app/utils/skewvoirAnalysis/gallery.ts`
- Extend: `front-dev-home/app/utils/skewvoirAnalysis/gallery.test.ts`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/SameSiteFilmstrip.vue`
- Add: `front-dev-home/app/components/ebeam/skewvoir/gallery/PinnedComparison.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Gallery.vue`

**Steps:**

- [ ] canonical site별로 compatible MSR 이미지를 시간순 그룹화합니다.
- [ ] focus/reference/before-after image를 최대 4장 pin하여 같은 scale로 봅니다.
- [ ] 각 frame에 CD/delta/tool/lot/timestamp/mag/vac/pixel을 표시합니다.
- [ ] missing image를 빈 cell로 남깁니다.
- [ ] 배율·pixel·method가 다른 경우 visual compatibility warning을 표시합니다.
- [ ] 등록 metadata가 없으면 pixel diff action을 제공하지 않습니다.
- [ ] physical pixel scale이 다르면 같은 크기로 보이는 thumbnail만으로 직접 비교하지 않고 calibration warning을 표시합니다.
- [ ] 위치 비교의 selected site와 Gallery filmstrip을 양방향 연결합니다.

**Acceptance:**

- 다른 layout의 동일 `chip_number`가 같은 site로 합쳐지지 않습니다.
- filmstrip 순서는 실제 timestamp이며 현재 set 선택 순서에 의존하지 않습니다.
- pinned image 비교에서 acquisition condition 차이를 즉시 확인할 수 있습니다.

**Commit:** `feat(skewvoir): add same-site historical image comparison`

---

## Task 13: 측정 개요에서 evidence hand-off 연결

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Dashboard.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/overview/StatBar.vue`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/dashboard/ParamNav.vue`
- Modify as needed: `front-dev-home/app/components/ebeam/skewvoir/dashboard/{WaferMap,RadiusPlot,MeasurementPoints,SemImage,Distribution}.vue`

**Steps:**

- [ ] overview에 상세 mini chart를 추가하지 않습니다.
- [ ] 확인된 사실에서만 `공간 pattern 자세히`, `측정 순서와 FDC`, `짝지은 값`, `검토할 이미지` hand-off를 생성합니다.
- [ ] hand-off에 view, parameter, focused site/sequence, X/Y query, filter를 전달합니다.
- [ ] 데이터가 준비되지 않은 상세 페이지는 CTA 대신 이유를 표시합니다.
- [ ] linked selection과 current compact no-page-scroll layout을 유지합니다.

**Acceptance:**

- overview의 wafer site에서 Gallery로 이동하면 같은 site와 parameter가 선택됩니다.
- sequence evidence에서 Time-Series로 이동하면 단일 scope의 sequence cursor가 복원됩니다.
- overview의 초기 load request 수와 layout 높이는 상세 페이지 개편 전과 동일합니다.

**Commit:** `feat(skewvoir): route overview evidence into drilldowns`

---

## Task 14: Cross-page UX, 접근성, 성능, export 검증

**Files:**

- Modify: `front-dev-home/app/utils/echartsThemes.ts`
- Modify: `front-dev-home/app/utils/chartPalette.ts`
- Add: `front-dev-home/tests/e2e/skewvoir-analysis-workflow.spec.ts` 또는 현재 E2E convention 경로
- Modify: 관련 view/component test
- Update: 사용자 문서와 API 계약

**Steps:**

- [ ] spec/engineering/control/reference line의 색·dash token을 분리합니다.
- [ ] chart에 keyboard focus, accessible name, text summary를 제공합니다.
- [ ] red/green 외 symbol·line style로 상태를 구분합니다.
- [ ] desktop은 viewport 안에서 panel 내부 scroll, mobile은 summary 우선 + full-screen workbench를 검증합니다.
- [ ] set batch request 수, image lazy load, chart point 상한과 progressive rendering을 측정합니다.
- [ ] export에 scope, grain, included/excluded MSR, unit, transform, reference, baseline/version, missing을 포함합니다.
- [ ] CD-SEM/HV-SEM, single/set, complete/missing/incompatible fixtures를 모두 검증합니다.

**Quality gate:**

```bash
npm --prefix front-dev-home test
npm --prefix front-dev-home run lint
npm --prefix front-dev-home run typecheck
npm --prefix front-dev-home run build
npx markdownlint-cli2 \
  docs/superpowers/specs/2026-07-16-skewvoir-analysis-drilldowns-design.md \
  docs/superpowers/plans/2026-07-16-skewvoir-analysis-drilldowns.md \
  docs/issues/skewvoir/analysis-drilldown-benchmark-research.md
git diff --check
```

**Live scenarios:**

1. 단일 MSR → 측정 개요 → 위치 비교 → same-site Gallery입니다.
2. 단일 MSR → sequence/FDC → paired CD/FDC scatter → image입니다.
3. 다중 MSR → compatibility exclusion → focus delta → MSR run chart입니다.
4. 다중 MSR → pooled vs tool-stratified 관계 → focus MSR evidence입니다.
5. missing coordinate/layout/image/FDC와 승인 baseline 없음 상태입니다.

**Commit:** `test(skewvoir): verify analysis drilldown workflow`

---

## Task 15: 별도 후속 계획으로 분리할 항목

다음은 UI placeholder를 만들기 위해 성급하게 구현하지 않습니다.

- 승인 historical baseline registry, versioning, review/contamination policy입니다.
- I-MR/EWMA/CUSUM의 offline false-alarm·shift detection 검증입니다.
- hardware BSM/Reso/MDC/SCE/BM·PM event-time join입니다.
- tool/lot/wafer/site variance component와 identifiability gate입니다.
- reference-artifact 기반 tool-to-tool matching과 metrology/process bias 분해입니다.
- spatial signature library와 engineer labeling workflow입니다.
- PCA/MSPC, virtual metrology, dynamic sampling입니다.
- image registration, edge/ROI·gray-level line profile office contract, similarity model입니다.

각 항목은 real office history와 별도의 acceptance dataset을 요구하므로 C0~C5 출하 후
독립 spec/plan으로 진행합니다.

---

## Self-Review

**Design coverage:**

- Design §2~§4의 progressive disclosure, adaptive scope, context bar, linked selection은 Tasks 2~4에 반영했습니다.
- Design §5 위치 비교는 Tasks 5~6에 단일/다중 vertical slice로 분리했습니다.
- Design §6 Time-Series는 Tasks 7~8에서 sequence와 real-time run을 분리했습니다.
- Design §7 상관 / 분포는 Tasks 9~10에서 exact site pair와 MSR feature grain을 분리했습니다.
- Design §8 Gallery는 Tasks 11~12에서 review queue와 same-site filmstrip으로 분리했습니다.
- Design §9~§11 grain, URL, provenance, 통계 무결성은 Tasks 2~4와 14의 gate입니다.
- Design §13의 advanced 기능은 Task 15로 명시적으로 이관했습니다.

**Current-code alignment:**

- `useSkewvoirAnalysis`의 Dashboard single fetch와 lazy set fetch를 유지합니다.
- 기존 `fixed_fdc`, `dynamic_fdc`, `fdc_params`, image URL seam을 재사용합니다.
- 기존 `focusedSequence`, `activeParam`, URL `msrs`를 교체하지 않고 확장합니다.
- 현재 `Correlation.vue`/`Gallery.vue`가 focus-only인 점과 Position/Time-Series만 set을 로드하는 점을 C0에서 먼저 통일합니다.
- backend 변경은 existing `msr_file/routes.py → data.py → providers` seam을 넘지 않습니다.

**Primary risks:**

| Risk | Gate |
| --- | --- |
| 같은 이름의 recipe/layout을 잘못 합침 | compatibility signature + unknown-safe 정책 |
| 단일 site를 독립 run처럼 사용 | explicit grain + MSR feature row |
| selection set으로 control limit 생성 | baseline readiness + descriptive default |
| mock 상관을 검증 결과로 오해 | mock label + method validation 금지 |
| Gallery가 request/render를 폭증 | lazy original + virtual grid + batch context |
| overview가 다시 무거워짐 | Dashboard set fetch 금지 characterization test |
| current wafer-map 작업과 충돌 | Task 0/implementation start에서 worktree 재확인 |

이 plan의 완료 조건은 네 페이지에 차트가 생기는 것이 아니라, **각 페이지가 하나의
엔지니어링 질문에 답하고 모든 답이 호환성·grain·N·missing·reference·raw evidence를
잃지 않는 것**입니다.
