# 이상치(abnormality) 검출 공용 컨벤션 · 설계

- 작성일: 2026-06-27
- 대상: 앱 전역 공용 레이어 + 파일럿 1면 (skewvoir `AnalyzePanel.vue`)
- 선행 설계: [`2026-06-26-skewvoir-cd-outlier-detection-design.md`](./2026-06-26-skewvoir-cd-outlier-detection-design.md)

## 1. 목적

현재 앱에는 "비정상(abnormal)"을 가리키는 서로 다른 세 가지 방식이 흩어져 있습니다.

- `device-statistics`: point-count `> 2 × median` 임계 (`outlierDetect.ts`)
- `skewvoir`: median+MAD 수정 z-score boolean (`madOutliers.ts`)
- `FdcAnalysis`: FDC drift ±2σ warning / ±3.5σ bad 밴드

세 면이 **서로 다른 통계 정의·시각 표현·용어**를 쓰기 때문에, 사용자가 데이터를
볼 때 "무엇이, 왜 비정상인지"를 일관되게 읽을 수 없습니다. 본 설계의 목적은
**하나의 공용 컨벤션**(검출 결과 모델 + 검출기 인터페이스 + 시각 규약)을 정의하고,
이를 **파일럿 1면(skewvoir `AnalyzePanel`)에서 끝까지 증명**하는 것입니다. 나머지
면의 이관(retrofit)은 후속 작업으로 둡니다.

## 2. 범위 (Scope)

- **공용 레이어**: 검출 결과 타입(`AnomalyVerdict`), 결합 함수
  (`combineVerdicts`), 순수 검출기 3종, 공용 표시 컴포넌트
  (`SkAnomalyBadge`, `SkAnomalyLegend`), 시각 토큰(`--sk-warn`).
- **검출 정의 3종** (모두 뷰가 이미 보유한 데이터로 계산, 백엔드 변경 없음):
  - **peer**: 같은 화면의 다른 값 대비 이상치 (상대적, self-contained)
  - **sibling**: 같아야 할 형제 그룹 대비 이탈 (예: tool-to-tool skew)
  - **drift**: 자기 자신의 시계열 대비 최근 수준 변화 (mean-shift)
- **파일럿**: `AnalyzePanel`에 **단계적**으로 적용 — peer 단독 → 검증 → sibling +
  drift 추가.
- **비목표는 §10** 참조.

## 3. 검출 결과 모델 (the contract)

모든 검출기가 emit하고 모든 UI가 소비하는 단일 타입입니다.

```ts
export type Severity = 'normal' | 'watch' | 'abnormal' | 'insufficient'

export type AnomalySignal = 'peer' | 'sibling' | 'drift'

export interface AnomalyVerdict {
  severity: Severity
  score: number          // 부호 있는 수정 z-score (σ 단위). insufficient면 NaN 허용
  reason: string         // 한국어 + 절대단위 동반, 예: "평균 3.8σ 높음 (Δ 2.1 nm)"
  metric: string         // 대상 지표: 'mean' | 'spread' | 'drift' | 'sibling' ...
  signal: AnomalySignal
}
```

### 3.1 심각도 밴딩 (공용 레이어 소유)

밴딩은 **각 검출기가 아니라 공용 레이어**가 소유하여 면 간 일관성을 보장합니다.

| 조건 | severity |
| --- | --- |
| `N < 검출기 minN` 또는 값이 non-numeric | `insufficient` |
| `|z| < 3.5` | `normal` |
| `3.5 ≤ |z| < 5` | `watch` |
| `|z| ≥ 5` | `abnormal` |

`insufficient`는 **"검출을 수행할 통계적 근거가 없음"**을 명시합니다. 선행 설계는
이를 `normal`(전부 false)로 묶었으나, `normal`이 **무채색(silence)**으로 표시되는
본 컨벤션에서는 "확인했고 정상"과 "확인 불가"가 구분되지 않아 위험합니다(Codex
지적 #3). 따라서 별도 상태로 둡니다.

### 3.2 `combineVerdicts`

한 항목(예: 한 MSR 점)에 여러 signal이 동시에 잡힐 수 있습니다.

```ts
export interface CombinedVerdict {
  severity: Severity          // worst-of (abnormal > watch > normal > insufficient)
  verdicts: AnomalyVerdict[]  // 기여한 개별 verdict들 — 그대로 보존
}
```

- **색(severity)**은 worst-of로 결정하되, **개별 근거는 배열로 보존**합니다.
  문자열을 이어 붙이지 않습니다(Codex #2). Badge tooltip이 signal별 한 줄씩
  나열하므로, 3개가 동시에 잡혀도 읽힙니다.
- worst-of 동률 시 `|score|`가 큰 verdict을 대표로 정렬 맨 위에 둡니다.
- 모든 기여 verdict이 `insufficient` → 결과도 `insufficient`. 일부라도 평가
  가능하면 평가된 것들로 worst-of를 계산합니다.

## 4. 검출기 3종 (순수 함수)

세 검출기 모두 동일 1차 프리미티브(median + MAD → σ 정규화 크기)로 환원되어
**임계·단위(σ)를 공유**합니다. 차이는 **무엇과 비교하느냐**(화면 전체 / 형제 그룹
/ 자기 과거)뿐입니다. 각 검출기는 raw score를 emit하고, 밴딩은 §3.1을 따릅니다.

### 4.1 `peerOutlier` — peer 대비 (madOutliers 리팩터)

- 현행 `madOutliers.ts`의 median+MAD 수정 z-score를 **boolean이 아니라 score로**
  반환하도록 일반화합니다. 현행 `detectMadOutliers(boolean[])`는 신규 함수 위에서
  유지하거나 호출부 교체 후 제거합니다(§6).
- `minN = 5`. 미만이면 `insufficient`.
- reason: `"{metric} {z}σ {높음|낮음} (Δ {x} {unit})"`.

### 4.2 `siblingDivergence` — 형제 그룹 대비

```ts
siblingDivergence(items, {
  groupKey:  (item) => string,   // 같아야 할 통제 facet들 (예: recipe·param·device)
  contrast:  (item) => string,   // 달라도 되는 차원 — reason에 명시 (예: eqp_id)
  value:     (item) => number,   // 그룹 내에서 비교할 지표
  minGroup?: number              // 기본 3; 미만 그룹은 insufficient
})
```

- `groupKey`로 분할 → 그룹별 robust center(median+MAD) → 각 멤버 σ 정규화 →
  밴딩. reason은 이탈 멤버의 **`contrast` 값**을 명시:
  `"동일 recipe·param에서 장비 EQP-03이 그룹 중심 대비 4.1σ 이탈 (Δ 3.0 nm)"`.
- `groupKey`에는 **통제되어야 할** facet(recipe·param·device)을 넣고, `contrast`
  (eqp_id)는 **제외**합니다. tool로 그룹화하면 정상적인 recipe-간 변동을 이탈로
  오판합니다.
- `minGroup` 기본 3. 단, 3은 robust 추정에 여전히 약하므로 — **파일럿 mock에서
  그룹 크기 분포를 먼저 측정**하고(§7) 필요 시 `minGroup` 상향 또는 `groupKey`
  완화를 검토합니다(Codex #6).

### 4.3 `driftChangepoint` — 자기 시계열 대비 (mean-shift)

- 입력: 시간순 정렬된 단일 수치 시계열.
- 방법: 의존성 없는 **two-window mean-shift**. 최근 `w`점의 robust mean을 그
  이전 baseline의 robust mean과 비교하고, **baseline MAD로 정규화**합니다.
  최근 수준 이동(FDC의 "변곡점" 개념)을 잡되, slope/trend는 보지 않습니다.
- `minN ≈ 8`. 미만이면 `insufficient`.
- reason: `"최근 {w}점 평균이 기존 대비 {Δ}σ {상승|하락} (변곡 추정, Δ {x} {unit})"`.

### 4.4 공통 에지 케이스 계약

- **MAD = 0 (분산 0)**: 0으로 나누지 않습니다. 모든 값이 동일하면 그 값은
  score `0`(정상). baseline이 완전 평탄한데 새 값만 다르면 일반 z-score와
  **질적으로 다른** 상황이므로, **"분산 0 기준 이탈"** verdict을 결정론적으로
  emit하되 σ 대신 **절대 Δ**로 reason을 채웁니다:
  `"분산 0 기준에서 이탈, Δ {x} {unit}"`. (현행 mean-abs 폴백은 *크기* 판정
  목적이 분명한 peerOutlier 내부에서만 보조로 유지합니다.)
- **non-numeric / 결측값**: baseline 계산에서 제외하고 해당 항목은
  `insufficient`. NaN/∞가 score로 새어 나가지 않습니다.
- **중복 timestamp**: drift 입력에서 순서를 유지(정렬 안정성)하며 제거하지
  않습니다.
- **재계산 범위**: verdict은 **선택 집합(selected set) 전체** 기준으로
  계산합니다. 화면에 보이는 부분집합(visible subset)이 아닙니다 — 필터/확대에
  따라 색이 흔들리지 않도록.

## 5. 시각 컨벤션

흩어진 표현을 **하나의 토큰 스케일·하나의 배지·하나의 범례**로 통일합니다.

### 5.1 토큰 (`assets/css/main.css`)

기존 `--sk-ok` / `--sk-bad` 스케일의 **빠진 중간값을 채웁니다**.

| severity | 토큰 | 표시 |
| --- | --- | --- |
| `normal` | (없음) | **무채색 — 표시하지 않음** |
| `watch` | **신규 `--sk-warn`** (amber, `-soft`/`-border`, 다크모드 쌍) | amber 점 |
| `abnormal` | 기존 `--sk-bad` (terracotta-red) | red 점 |
| `insufficient` | 기존 중립 ink 토큰 | 작은 회색 점 |

`normal`을 **무채색**으로 두는 이유: 모든 행을 칠하면 노이즈가 커지고, 임계가
지나치게 민감하면 **화면에 amber가 가득 차서 튜닝 문제가 눈으로 드러납니다**.
초록 "ok" 점을 모든 곳에 찍는 것도 또 다른 노이즈이므로 두지 않습니다.

### 5.2 `SkAnomalyBadge`

- props: `verdict: CombinedVerdict | AnomalyVerdict | null`.
  `null`·`normal` → 아무것도 렌더하지 않음(`v-if`).
- severity 색의 점 + (선택) 짧은 라벨. 전체 `reason`(들)은 **tooltip/title**로
  — "explained" 페이로드는 항상 hover 한 번 거리, 행을 어지럽히지 않음.
- `:compact` prop: 점만(차트 점·표 셀 등 고밀도) vs 점 + reason 텍스트(카드).
- `insufficient`는 회색 점 + tooltip `"표본 부족 — 미평가"`.

### 5.3 `SkAnomalyLegend`

- 배지를 쓰는 면마다 1개 배치.
- 3단계 스케일과 의미 + **현재 활성 임계**(`watch ≥ 3.5σ · abnormal ≥ 5σ`)를
  표시 — 엔지니어가 색의 의미를 아는 신뢰 앵커.

### 5.4 부착 패턴 (컨벤션의 "how")

면은 `<script setup>`에서 순수 검출기를 호출해 항목 id별 verdict map을 만들고,
항목이 렌더되는 곳(차트 점·표 행·카드 헤더)마다 `<SkAnomalyBadge>`를
떨어뜨립니다. **검출은 테스트 가능한 util, 컴포넌트는 렌더 전용.**

## 6. 파일럿: skewvoir `AnalyzePanel` (단계적)

선행 설계(2026-06-26)에서 이미 **boolean recolor**가 shipped 되어 있습니다. 본
파일럿은 그 위에서 **bool → graded verdict**, **recolor → `SkAnomalyBadge`**로
진화시킵니다.

### Phase 1 — peer 단독 (컨벤션 증명)

- `AnalyzePanel`의 `timeSeriesPoints`에서 현행 `detectMadOutliers(mean/std)`
  호출을 `peerOutlier`로 교체, score 보존.
- `TimeSeriesChart`의 점별 recolor 대신 `SkAnomalyBadge`(compact)로 표시,
  tooltip에 reason. `insufficient`(선택 MSR < 5)는 회색 점으로 명시.
- 헤더에 `SkAnomalyLegend`, 요약줄에 `watch N · abnormal N` 카운트.
- **여기서 contract·badge·legend·insufficient 표시를 끝까지 검증**한 뒤 Phase 2로.

### Phase 2 — sibling + drift 추가

- sibling: 동일 점들에 `groupKey = recipe·param·device`, `contrast = eqp_id`,
  `value = mean`. **먼저 §7의 그룹 크기 분포를 확인**하고 `minGroup`을 확정.
- drift: focus parameter의 시간순 mean 시계열에 `driftChangepoint`.
- `combineVerdicts`로 MSR 점당 1배지(개별 근거는 tooltip에 다중 행).

백엔드 신규 엔드포인트 없음 — 세 검출기 모두 `useMsrFileApi`가 이미 로드한
선택 데이터로 계산.

## 7. 검증·캘리브레이션 (mock)

- 순수 util `node --test` (저장소 관례):
  `peerOutlier`, `siblingDivergence`, `driftChangepoint`, `combineVerdicts`.
  밴딩 경계(normal/watch/abnormal/insufficient edge), `minN`/`minGroup` 가드,
  MAD=0 / 분산 0 이탈, worst-of + 개별 근거 보존.
- 기존 `madOutliers.test.ts` 케이스는 `peerOutlier.test.ts`로 이관
  (boolean → verdict 단언).
- **sibling 사전 측정**: 파일럿 mock에서 `recipe·param·device` 그룹 크기 분포를
  산출해 `minGroup` 확정 및 coverage 빈약 시 `groupKey` 완화 판단.
- 컴포넌트는 thin/렌더 전용 → 컴포넌트 테스트 없음. Playwright로 네 severity가
  렌더되는지 스팟 체크.

## 8. 데이터 흐름

```text
files (Map<msr, MsrFileResponse>)
  → timeSeriesPoints computed (AnalyzePanel, 선택 집합 전체 기준)
      시간순 정렬 → metric 추출
      → peerOutlier / siblingDivergence / driftChangepoint  (raw score)
      → §3.1 밴딩 → AnomalyVerdict[]
      → combineVerdicts → 항목별 CombinedVerdict map
  → SkAnomalyBadge (차트 점 / 헤더 legend / 요약 카운트)
```

## 9. 에지 케이스 (요약)

- 선택 MSR < minN → `insufficient`(회색 점), `normal`과 구분.
- 모든 값 동일 → 분산 0 → score 0, false positive 없음.
- 평탄 baseline + 단일 상이값 → "분산 0 기준 이탈" 결정론 verdict(절대 Δ).
- 특정 MSR에 parameter 없음 → 입력 단계에서 제외(결측 → `insufficient`).
- sibling 그룹 1~2개 → `minGroup` 미만 → `insufficient`(허위 flag 없음).
- 단일 극단값 masking → MAD 규칙이 정상 검출.

## 10. 비목표 (Non-goals)

- **spec/control limit(USL/LSL) 기반 검출** — Phase-1 mock에 limit 데이터 없음.
- **slope/trend changepoint** — mean-shift만. 실제 시계열이 요구하면 후속.
- **device-statistics·FdcAnalysis 이관** — 본 스펙은 컨벤션을 *증명*만. 각 면은
  후속 스펙에서 채택.
- **per-detector 신뢰도 모델링(Bayesian 등)** — Codex #1의 무거운 버전. Phase-1
  mock에는 과설계. 공유 σ 밴드 + 검출기별 `minN`/`insufficient`로 대응하고,
  실데이터 등장 시 Phase-2/3에서 재검토.
- **실데이터 캘리브레이션 하니스** — 실제 CD 측정 레인지 등장 후 작업.
- 백엔드 엔드포인트, verdict 영속화·알림/피드.
- 사용자 조정 가능한 민감도(k) UI.
