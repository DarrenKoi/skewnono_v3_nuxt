# 이상치(abnormality) 검출 공용 컨벤션 · 설계

- 작성일: 2026-06-27
- 대상: 앱 전역 공용 레이어 + 파일럿 1면 (skewvoir `AnalyzePanel.vue`)
- 선행 설계: [`2026-06-26-skewvoir-cd-outlier-detection-design.md`](./2026-06-26-skewvoir-cd-outlier-detection-design.md)

## 1. 목적

현재 앱에는 "비정상(abnormal)"을 가리키는 서로 다른 방식이 흩어져 있습니다.

- `device-statistics`: point-count `> 2 × median` 임계 (`outlierDetect.ts`)
- `skewvoir`: median+MAD 수정 z-score boolean (`madOutliers.ts`)
- `FdcAnalysis`: FDC drift ±2σ warning / ±3.5σ bad 밴드

세 면이 **서로 다른 정의·시각 표현·용어**를 쓰기 때문에, 사용자가 데이터를 볼 때
"무엇이, 왜 비정상인지"를 일관되게 읽을 수 없습니다. 본 설계의 목적은 **하나의
공용 컨벤션**(검출 결과 모델 + 채점 방식 + 시각 규약)을 정의하고, 이를 **파일럿
1면(skewvoir `AnalyzePanel`)에서 끝까지 증명**하는 것입니다. 나머지 면의
이관(retrofit)은 후속 작업으로 둡니다.

**용어 원칙**: 화면·툴팁·범례의 모든 문구는 팀이 익숙한 용어(평균, 표준편차,
범위, % 초과)로 표기합니다. `z-score`/`MAD`/`modified z-score` 같은 용어는
사용하지 않습니다.

## 2. 범위 (Scope)

본 컨벤션은 **두 개의 독립 축**으로 구성됩니다.

- **비교 기준(comparison base)** — *무엇과* 비교하는가. 비교 대상의 **중심값**을
  결정합니다.
  - **peer**: 같은 화면의 다른 값들의 평균
  - **sibling**: 같아야 할 형제 그룹의 평균 (예: tool-to-tool skew)
  - **drift**: 자기 시계열의 baseline 평균 (최근 수준 변화)
- **채점 방식(scoring method)** — *어떻게* 거리를 판정하는가. 사용자가 고르는
  렌즈입니다.
  - **범위(range)**: 중심값 ± **사용자 지정 %** 밖이면 이상치 (기본 ±10% / ±20%)
  - **표준편차(stddev)**: 평균 ± **k·표준편차** 밖이면 이상치 (기본 ±2σ / ±3σ)

검출기(비교 기준)는 "중심값(및 표준편차)"만 제공하고, 활성 채점 방식이 거리를
밴딩합니다. **같은 데이터에 대한 두 가지 관점**이며 사용자가 토글로 전환합니다.

- 모두 뷰가 이미 보유한 데이터로 계산 — **백엔드 변경 없음**.
- **공용 표시**: `SkAnomalyBadge`, `SkAnomalyLegend`, 시각 토큰(`--sk-warn`),
  방식 토글 컨트롤.
- **파일럿**: `AnalyzePanel`에 **단계적** 적용 — peer 단독(두 방식 모두) → 검증
  → sibling + drift.
- 비목표는 §10 참조.

## 3. 검출 결과 모델 (the contract)

모든 검출기·방식이 emit하고 모든 UI가 소비하는 단일 타입입니다.

```ts
export type EvalStatus = 'evaluated' | 'insufficient'

export type Severity = 'normal' | 'watch' | 'abnormal'   // evaluated일 때만 유효

export type AnomalySignal = 'peer' | 'sibling' | 'drift'

export type ScoringMethod = 'range' | 'stddev'

export interface AnomalyVerdict {
  status: EvalStatus     // 'insufficient' = 검출 수행 불가 (severity·score 무의미)
  severity: Severity     // status === 'evaluated'일 때만 의미 있음
  method: ScoringMethod  // 점수의 단위를 결정 (range → %, stddev → σ)
  score: number          // 부호 있는 거리. range → % 편차, stddev → σ 배수
  reason: string         // 한국어 + 실측·절대단위 동반
  metric: string         // 대상 지표: 'mean' | 'spread' | 'drift' | 'sibling' ...
  signal: AnomalySignal
}
```

- **`status`와 `severity`는 별개 축입니다.** `severity`는 "얼마나 비정상인가"의
  순서형(normal < watch < abnormal) 척도, `status`는 "검출을 수행했는가"의 평가
  상태입니다. `status === 'insufficient'`이면 `severity`/`score`는 읽지 않습니다.
- **`method`가 `score`의 단위를 규정합니다.** UI/범례/문구는 이 값을 보고 % 또는
  σ로 렌더합니다.

### 3.1 심각도 밴딩 (공용 레이어 소유, 방식별)

밴딩은 각 검출기가 아니라 **공용 레이어**가 소유해 면 간 일관성을 보장합니다.
먼저 `status`를 정하고, `evaluated`일 때만 활성 방식의 임계로 `severity`를
밴딩합니다. 임계값은 **설정 객체**로 주입되며 사용자가 조정합니다(§5.4).

**범위(range) 방식** — `dev% = (value − center) / |center| × 100`:

| 조건 | status | severity |
| --- | --- | --- |
| `N < minN`, 비수치, 또는 `center ≈ 0` | `insufficient` | — |
| `|dev%| < watchPct` (기본 10) | `evaluated` | `normal` |
| `watchPct ≤ |dev%| < abnormalPct` (기본 20) | `evaluated` | `watch` |
| `|dev%| ≥ abnormalPct` | `evaluated` | `abnormal` |

**표준편차(stddev) 방식** — `k = (value − mean) / std`:

| 조건 | status | severity |
| --- | --- | --- |
| `N < minN` 또는 비수치 | `insufficient` | — |
| `|k| < watchK` (기본 2) | `evaluated` | `normal` |
| `watchK ≤ |k| < abnormalK` (기본 3) | `evaluated` | `watch` |
| `|k| ≥ abnormalK` | `evaluated` | `abnormal` |

> 참고: 기존 `FdcAnalysis`는 ±2σ warning / **±3.5σ** bad를 씁니다. 본 컨벤션
> 기본은 ±3σ(고전 3시그마)로 두되, 추후 FDC 이관 시 `abnormalK`를 3.5로 맞출지
> 확정합니다(설정으로 흡수 가능).

`status: insufficient`는 **"검출을 수행할 통계적 근거가 없음"**을 명시합니다.
`normal`이 **무채색(silence)**으로 표시되므로 "확인했고 정상"과 "확인 불가"를
반드시 구분합니다(Codex #3).

### 3.2 `combineVerdicts`

한 항목(예: 한 MSR 점)에 여러 signal이 동시에 잡힐 수 있습니다. **한 뷰의 모든
verdict은 동일한 활성 `method`로 계산**되므로 단위가 섞이지 않습니다.

```ts
export interface CombinedVerdict {
  status: EvalStatus          // 평가된 verdict이 하나라도 있으면 'evaluated'
  severity: Severity          // evaluated 중 worst-of (abnormal > watch > normal)
  verdicts: AnomalyVerdict[]  // 기여한 개별 verdict들 — status 무관하게 보존
}
```

- **평가된 verdict만으로 worst-of**(abnormal > watch > normal). `insufficient`는
  정렬에서 빠지지만 **배열에는 보존**되어 "한 검출기가 평가 불가"라는 사실이
  tooltip에서 사라지지 않습니다.
- 평가된 verdict이 **하나도 없으면** `status: insufficient`.
- **개별 근거는 배열로 보존**하고 문자열을 이어 붙이지 않습니다(Codex #2). Badge
  tooltip이 signal별 한 줄씩 나열하므로 3개가 동시에 잡혀도 읽힙니다.
- worst-of 동률 시 `|score|`가 큰 verdict을 대표로 정렬 맨 위에 둡니다.

## 4. 두 축의 구성 단위 (순수 함수)

### 4.1 채점 방식 (scoring method)

검출기가 제공한 `{ value, center, std? }`를 받아 §3.1 표대로 밴딩해 `severity`·
`score`·`reason`을 만드는 순수 함수입니다. 검출기와 분리되어 어느 비교 기준과도
조합됩니다.

```ts
score(input: { value: number; center: number; std?: number },
      cfg: MethodConfig): { status; severity; score; reason }
```

- **범위(range)**: 중심값 대비 % 편차. `center ≈ 0`이면 % 밴드가 무의미하므로
  `insufficient`. reason 예: `"평균 10 대비 +14% (실측 11.4) · 허용 ±10% 초과"`.
- **표준편차(stddev)**: 고전 평균 ± k·표준편차. reason 예:
  `"평균 10.0, 표준편차 0.5 · 평균+3.2σ (실측 11.6) · ±3σ 초과"`.
  - **std = 0 (분산 0)** 예외: 0으로 나누지 않습니다. 모든 값이 동일하면 그 값은
    `normal`(score 0). baseline이 완전 평탄한데 새 값만 다르면 일반 σ 판정과
    질적으로 다르므로, **"표준편차 0 기준에서 이탈, Δ {x}"** verdict을 결정론적으로
    emit하되 σ 대신 절대 Δ로 reason을 채웁니다.

### 4.2 비교 기준 (comparison base) — 검출기 3종

각 검출기는 항목 집합에서 비교 단위의 **중심값**(및 stddev 방식용 표준편차)을
산출해 채점 방식에 넘깁니다. 차이는 **무엇을 중심으로 보느냐**뿐입니다.

- **`peer`**: 화면 내 값들의 평균을 중심값으로, 각 값을 채점.
  `minN` 기본 3(range)·5(stddev). reason의 metric은 `mean`/`spread`.
- **`siblingDivergence(items, { groupKey, contrast, value, minGroup })`**:
  `groupKey`(같아야 할 통제 facet, 예: `recipe·param·device`)로 분할 → 그룹별
  중심값 → 멤버를 채점. reason은 이탈 멤버의 **`contrast` 값**(예: `eqp_id`)을
  명시: `"동일 recipe·param에서 장비 EQP-03이 그룹 평균 대비 +12% 이탈"`.
  `groupKey`에는 통제 facet을, `contrast`(eqp_id)는 **제외**합니다. `minGroup`
  기본 3 — **파일럿 mock에서 그룹 크기 분포를 먼저 측정**(§7)해 확정·완화(Codex #6).
- **`driftChangepoint(series, { window, minN })`**: 시간순 시계열에서 baseline
  평균을 중심값으로, 최근 `window`점을 채점(최근 수준 이동 = FDC "변곡점").
  slope/trend는 보지 않습니다. `minN` 기본 8. reason:
  `"최근 {w}점이 기존 평균 대비 +13% 상승 (변곡 추정)"`.

### 4.3 공통 계약 (모든 검출기·방식)

- **비수치 / 결측값**: 중심값 계산에서 제외하고 해당 항목은 `insufficient`.
  NaN/∞가 score로 새어 나가지 않습니다.
- **재계산 범위**: verdict은 **선택 집합(selected set) 전체** 기준으로 계산합니다.
  화면에 보이는 부분집합이 아닙니다(필터/확대에 색이 흔들리지 않도록).
- **중복 timestamp**: drift 입력에서 순서를 유지하며 제거하지 않습니다.
- **방식 전환**: 활성 `method`가 바뀌면 전 항목 재계산. tooltip의 stale 방지.

## 5. 시각 컨벤션

흩어진 표현을 **하나의 토큰 스케일·하나의 배지·하나의 범례·하나의 방식 토글**로
통일합니다.

### 5.1 토큰 (`assets/css/main.css`)

기존 `--sk-ok` / `--sk-bad` 스케일의 **빠진 중간값을 채웁니다**. (방식과 무관하게
severity만으로 색이 정해지므로 색 규칙은 한 벌입니다.)

| 상태 | 토큰 | 표시 |
| --- | --- | --- |
| `insufficient` (status) | 기존 중립 ink 토큰 | 작은 회색 점 |
| `evaluated` · `normal` | (없음) | **무채색 — 표시하지 않음** |
| `evaluated` · `watch` | **신규 `--sk-warn`** (amber, `-soft`/`-border`, 다크모드 쌍) | amber 점 |
| `evaluated` · `abnormal` | 기존 `--sk-bad` (terracotta-red) | red 점 |

`normal`을 무채색으로 두면, 임계가 지나치게 민감할 때 amber가 화면에 가득 차
**튜닝 문제가 눈으로 드러납니다**. 초록 "ok" 점을 모든 곳에 찍는 것도 노이즈이므로
두지 않습니다.

### 5.2 `SkAnomalyBadge`

- props: `verdict: CombinedVerdict | AnomalyVerdict | null`. 렌더 분기는
  **status 먼저, 그다음 severity**:
  - `null` 또는 `evaluated`+`normal` → 렌더 안 함(`v-if`).
  - `insufficient` → 회색 점 + tooltip `"표본 부족 — 미평가"`.
  - `evaluated`+`watch`/`abnormal` → 해당 색 점.
- 전체 `reason`(들)은 **tooltip/title**로 — 행을 어지럽히지 않음.
- `:compact` prop: 점만(차트 점·표 셀) vs 점 + reason 텍스트(카드).

### 5.3 `SkAnomalyLegend`

- 배지를 쓰는 면마다 1개. **활성 방식의 용어로** 스케일과 임계를 표시:
  - range: `정상 ±10% · 주의 ±10~20% · 이상 ±20% 초과`
  - stddev: `정상 ±2σ 이내 · 주의 ±2σ · 이상 ±3σ 초과`

### 5.4 방식 토글 + 임계 컨트롤

- 뷰 헤더(범례 옆)에 **방식 토글**: `범위 ⇄ 표준편차`. 기본 **범위**.
- 범위 선택 시 **% 입력**(watch/abnormal, 기본 10·20)을 노출 — 사용자가 조정.
  표준편차 선택 시 k 입력(기본 2·3). 변경은 즉시 재계산.
- 선택값은 뷰 단위 상태(필요 시 `useState`+localStorage, 도구×fab 스코프 —
  기존 working-set 패턴 준용)로 보존.

### 5.5 부착 패턴

면은 `<script setup>`에서 순수 검출기+방식을 호출해 항목 id별 verdict map을 만들고,
항목이 렌더되는 곳마다 `<SkAnomalyBadge>`를 떨어뜨립니다. **검출은 테스트 가능한
util, 컴포넌트는 렌더 전용.**

## 6. 파일럿: skewvoir `AnalyzePanel` (단계적)

선행 설계(2026-06-26)에서 **boolean recolor**가 이미 shipped. 본 파일럿은 그 위에서
**bool → graded verdict**, **recolor → `SkAnomalyBadge`**, **단일 고정 방식 → 방식
토글**로 진화시킵니다.

### Phase 1 — peer 단독 + 방식 토글 (컨벤션 증명)

- `timeSeriesPoints`의 현행 `detectMadOutliers(mean/std)`를 `peer` 검출기 +
  활성 채점 방식 호출로 교체.
- `TimeSeriesChart` 점별 recolor 대신 `SkAnomalyBadge`(compact), tooltip에 reason.
  `insufficient`(선택 MSR < minN)는 회색 점.
- 헤더에 `SkAnomalyLegend` + **방식 토글/임계 컨트롤**(§5.4), 요약줄에
  `주의 N · 이상 N` 카운트.
- **여기서 contract·두 방식·badge·legend·insufficient·토글을 끝까지 검증**한 뒤
  Phase 2로.

### Phase 2 — sibling + drift 추가

- sibling: 동일 점들에 `groupKey = recipe·param·device`, `contrast = eqp_id`,
  `value = mean`. **먼저 §7 그룹 크기 분포 확인** 후 `minGroup` 확정.
- drift: focus parameter의 시간순 mean 시계열에 `driftChangepoint`.
- `combineVerdicts`로 MSR 점당 1배지(개별 근거는 tooltip 다중 행).

백엔드 신규 엔드포인트 없음 — 모두 `useMsrFileApi`가 이미 로드한 선택 데이터로 계산.

## 7. 검증·캘리브레이션 (mock)

- 순수 util `node --test`:
  - 채점 방식 `range`/`stddev`: 밴딩 경계(normal/watch/abnormal edge), `center≈0`
    → insufficient, `std=0` → 분산 0 이탈, 부호(±) 정확성.
  - 검출기 `peer`/`siblingDivergence`/`driftChangepoint`: 중심값 산출, `minN`/
    `minGroup` 가드, 결측 제외.
  - `combineVerdicts`: worst-of(평가된 것만) + insufficient 보존.
- 기존 `madOutliers.test.ts`는 제거하고 새 방식 테스트로 대체(MAD 미사용).
- **sibling 사전 측정**: 파일럿 mock에서 `recipe·param·device` 그룹 크기 분포를
  산출해 `minGroup`/`groupKey` 확정.
- 컴포넌트는 thin → 컴포넌트 테스트 없음. Playwright로 두 방식 전환 + 네 상태
  (insufficient/normal/watch/abnormal) 렌더 스팟 체크.

## 8. 데이터 흐름

```text
files (Map<msr, MsrFileResponse>) + 활성 method/임계 (뷰 상태)
  → timeSeriesPoints computed (AnalyzePanel, 선택 집합 전체 기준)
      시간순 정렬 → metric 추출
      → 검출기(peer/sibling/drift): 중심값(+std) 산출
      → 활성 채점 방식(range|stddev): §3.1 밴딩 → AnomalyVerdict[]
      → combineVerdicts → 항목별 CombinedVerdict map
  → SkAnomalyBadge (차트 점) · SkAnomalyLegend · 방식 토글 · 요약 카운트
```

## 9. 에지 케이스 (요약)

- 선택 MSR < minN → `insufficient`(회색 점), `normal`과 구분.
- range 방식에서 평균 ≈ 0 → % 밴드 무의미 → `insufficient`.
- stddev 방식에서 모든 값 동일(std=0) → score 0, false positive 없음.
- stddev 방식에서 평탄 baseline + 단일 상이값 → "표준편차 0 기준 이탈"(절대 Δ).
- 특정 MSR에 parameter 없음 → 입력 단계 제외(결측 → `insufficient`).
- sibling 그룹 1~2개 → `minGroup` 미만 → `insufficient`.
- 방식/임계 변경 → 전 항목 재계산(stale 없음).

## 10. 비목표 (Non-goals)

- **고정 spec/control limit(USL/LSL, 절대 nm)** — 범위 방식이 평균 대비 %라 mock에
  한정해 충분. 절대 한계 기반은 실데이터 등장 후.
- **slope/trend changepoint** — mean-shift만. 실 시계열 요구 시 후속.
- **MAD/수정 z-score** — 팀 비친숙으로 채택 안 함(평균/표준편차/범위만 노출).
- **device-statistics·FdcAnalysis 이관** — 본 스펙은 컨벤션을 *증명*만. 각 면은
  후속 스펙에서 채택(FDC의 ±3.5σ는 `abnormalK` 설정으로 흡수 검토).
- 백엔드 엔드포인트, verdict 영속화·알림/피드.
