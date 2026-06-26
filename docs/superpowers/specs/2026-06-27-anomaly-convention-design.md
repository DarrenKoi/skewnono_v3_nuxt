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
  결정합니다. **중심값은 leave-one-out(LOO)** — 판정 대상 점을 *제외한* 나머지로
  계산합니다(§4.2, masking 방지).
  - **peer**: 같은 화면의 *나머지* 값들의 평균
  - **sibling**: 같아야 할 형제 그룹의 *나머지* 평균 (예: tool-to-tool skew)
  - **recent-shift (최근 수준 변화)**: 자기 시계열의 직전 baseline 평균 대비 최근
    수준 이동. (이름이 "drift"였으나 실제로는 **step 변화 감지**이므로 개명 — gradual
    trend는 보지 않음.)
- **채점 방식(scoring method)** — *어떻게* 거리를 판정하는가.
  - **범위(range)** — **주(主) 방식, 기본값**: 중심값 ± **사용자 지정 %** 밖이면
    이상치 (기본 ±10% / ±20%). **배지·요약·triage는 항상 range 기준.**
  - **표준편차(stddev)** — **보조 진단 렌즈**: 평균 ± **k·표준편차** (기본 ±2σ /
    ±3σ). 사용자가 토글로 전환해 *진단용*으로 볼 수 있으나 권위 있는 verdict은
    아닙니다(Codex #5 — 방식 자유선택의 triage 불일치 방지).

검출기(비교 기준)는 LOO **중심값(및 표준편차)**만 제공하고, 활성 채점 방식이
거리를 밴딩합니다. **같은 데이터에 대한 두 관점**입니다.

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

export type AnomalySignal = 'peer' | 'sibling' | 'recent-shift'

export type ScoringMethod = 'range' | 'stddev'

export interface AnomalyVerdict {
  status: EvalStatus     // 'insufficient' = 검출 수행 불가 (severity·score 무의미)
  severity: Severity     // status === 'evaluated'일 때만 의미 있음
  method: ScoringMethod  // 점수의 단위를 결정 (range → %, stddev → σ)
  score: number          // 부호 있는 거리. range → % 편차, stddev → σ 배수
  reason: string         // 한국어 + 실측·절대단위 동반
  metric: string         // 대상 지표: 'mean' | 'spread' | 'shift' | 'sibling' ...
  signal: AnomalySignal  // 비교 기준: peer | sibling | recent-shift
}
```

**권위(authority)**: 한 면의 배지·요약·triage는 **range 방식**의 verdict을
권위로 삼습니다. stddev는 사용자가 토글로 보는 **보조 진단**일 뿐입니다(§5.4).

- **`status`와 `severity`는 별개 축입니다.** `severity`는 "얼마나 비정상인가"의
  순서형(normal < watch < abnormal) 척도, `status`는 "검출을 수행했는가"의 평가
  상태입니다. `status === 'insufficient'`이면 `severity`/`score`는 읽지 않습니다.
- **`method`가 `score`의 단위를 규정합니다.** UI/범례/문구는 이 값을 보고 % 또는
  σ로 렌더합니다.

### 3.1 심각도 밴딩 (공용 레이어 소유, 방식별)

밴딩은 각 검출기가 아니라 **공용 레이어**가 소유해 면 간 일관성을 보장합니다.
먼저 `status`를 정하고, `evaluated`일 때만 활성 방식의 임계로 `severity`를
밴딩합니다. 임계값은 **설정 객체**로 주입되며 사용자가 조정합니다(§5.4).

**범위(range) 방식** — `dev% = (value − center) / |center| × 100`, `center`는
**LOO 평균**(판정 점 제외):

| 조건 | status | severity |
| --- | --- | --- |
| `유효 N < minN`, 비수치, 또는 `|center| < minAbsCenter` | `insufficient` | — |
| `|dev%| < watchPct` (기본 10) | `evaluated` | `normal` |
| `watchPct ≤ |dev%| < abnormalPct` (기본 20) | `evaluated` | `watch` |
| `|dev%| ≥ abnormalPct` | `evaluated` | `abnormal` |

**표준편차(stddev) 방식** — `k = (value − mean) / std`. `mean`·`std`는 **LOO**(판정
점 제외), `std`는 **표본표준편차(n−1)**:

| 조건 | status | severity |
| --- | --- | --- |
| `유효 N < minN` 또는 비수치 | `insufficient` | — |
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

- **범위(range)**: LOO 중심값 대비 % 편차. `|center| < minAbsCenter`(지표·단위별
  설정, 0-중심 지표 보호)이면 % 밴드가 무의미하므로 `insufficient`. reason 예:
  `"나머지 평균 10 대비 +14% (실측 11.4) · 허용 ±10% 초과"`.
- **표준편차(stddev)**: LOO 평균 ± k·표본표준편차. reason 예:
  `"나머지 평균 10.0, 표준편차 0.5 · +3.2σ (실측 11.6) · ±3σ 초과"`.
  - **std = 0 (분산 0)** 예외: 0으로 나누지 않습니다. LOO 나머지가 모두 동일하고
    판정 값도 같으면 `normal`(score 0). 나머지는 완전 평탄한데 판정 값만 다르면
    일반 σ 판정과 질적으로 다르므로, severity = **`abnormal`**(결정론), score는
    σ 대신 **절대 Δ**, reason은 `"표준편차 0 기준에서 이탈, Δ {x}"`. (이 branch의
    score 단위가 σ가 아님을 contract 주석에 명시.)

### 4.2 비교 기준 (comparison base) — 검출기 3종

각 검출기는 항목별 **LOO 중심값**(및 stddev용 표준편차)을 산출해 채점 방식에
넘깁니다. 차이는 **무엇을 중심으로 보느냐**뿐입니다.

> **LOO(leave-one-out)가 핵심**: 판정 대상 점을 중심값 계산에서 제외하면, 극단값이
> 자기 밴드를 부풀려 스스로를 숨기는 **masking**(Codex #1·#4 — 실측 +20% outlier가
> N=5에서 +15.4%로만 보임)이 사라집니다. recent-shift는 판정 점이 baseline에 애초에
> 포함되지 않아 이미 LOO입니다.

- **`peer`**: 각 점을 *나머지* 점들의 평균(LOO) 중심으로 채점.
  `minN` 기본 3(range)·5(stddev). metric은 `mean`/`spread`.
- **`siblingDivergence(items, { groupKey, contrast, value, minGroup })`**:
  `groupKey`(같아야 할 통제 facet, 예: `recipe·param·device`)로 분할 → 멤버를
  *그룹 내 나머지*(LOO) 중심으로 채점. reason은 이탈 멤버의 **`contrast` 값**(예:
  `eqp_id`) 명시: `"동일 recipe·param에서 장비 EQP-03이 그룹 평균 대비 +12% 이탈"`.
  `groupKey`엔 통제 facet, `contrast`(eqp_id)는 **제외**. `minGroup` 기본 3 —
  **파일럿 mock에서 그룹 크기 분포를 먼저 측정**(§7)해 확정·완화(Codex #6).
- **`recentShift(series, { window, minN })`** (구 drift): 시간순 시계열에서 직전
  baseline 평균을 중심으로 최근 `window`점을 채점 — **step 변화 감지**(gradual
  trend·slope는 보지 않음). `minN` 기본 8. window 경계를 tooltip에 표시. reason:
  `"최근 {w}점이 기존 평균 대비 +13% 상승 (최근 수준 변화)"`. **peer 캘리브레이션
  검증 후 도입**(Codex #7).

### 4.3 공통 계약 (모든 검출기·방식)

- **비수치 / 결측값**: 중심값 계산에서 제외하고 해당 항목은 `insufficient`.
  NaN/∞가 score로 새어 나가지 않습니다. **결측 제외 후 남은 유효 N을 다시
  검사** — `minN` 미만으로 줄면 전부 `insufficient`(Codex #8, N이 2~3으로 쪼그라든
  채 평가되는 것 방지).
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

- 뷰 헤더(범례 옆)에 **방식 토글**: `범위 ⇄ 표준편차`. 기본 **범위(권위)**.
  표준편차는 `보조 진단` 라벨을 달아 권위 verdict이 아님을 명시(§3 authority).
- 범위 선택 시 **% 입력**(watch/abnormal, 기본 10·20)을 노출 — 사용자가 조정.
  표준편차 선택 시 k 입력(기본 2·3). 변경은 즉시 재계산.
- **활성 방식·임계를 배지/범례에 항상 노출** — 스크린샷·논의에서 어떤 기준의
  결과인지 빠지지 않도록(Codex #5 triage 일관성). 임계는 "사용자 허용범위"이지
  통계적 표준이 아님을 범례 문구로 구분.
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
- recent-shift: focus parameter의 시간순 mean 시계열에 `recentShift` (peer
  캘리브레이션 검증 후).
- `combineVerdicts`로 MSR 점당 1배지(개별 근거는 tooltip 다중 행).

백엔드 신규 엔드포인트 없음 — 모두 `useMsrFileApi`가 이미 로드한 선택 데이터로 계산.

## 7. 검증·캘리브레이션 (mock)

- 순수 util `node --test`:
  - 채점 방식 `range`/`stddev`: 밴딩 경계(normal/watch/abnormal edge),
    `|center| < minAbsCenter` → insufficient, `std=0` → 분산 0 이탈(abnormal,
    절대 Δ), 부호(±) 정확성.
  - **masking 적대 fixture (필수)**: N=5·10·15에서 단일/복수 동방향 outlier가
    **LOO 덕분에 abnormal로 잡히는지** — 비-LOO였다면 묻혔을 케이스를 명시 검증.
  - 검출기 `peer`/`siblingDivergence`/`recentShift`: LOO 중심값 산출, `minN`/
    `minGroup` 가드, **결측 제외 후 유효 N 재검사**.
  - `combineVerdicts`: worst-of(평가된 것만) + insufficient 보존.
- 기존 `madOutliers.test.ts`는 제거하고 새 방식 테스트로 대체(MAD 미사용).
- **sibling 사전 측정**: 파일럿 mock에서 `recipe·param·device` 그룹 크기 분포를
  산출해 `minGroup`/`groupKey` 확정.
- **캘리브레이션 게이트 (Phase 2 진입 전, Codex #6)**: known-good mock fixture에서
  기본 임계(10/20%, 2/3σ)의 **예상 flag 비율**을 측정하고, 임계 sweep 스크린샷으로
  과다/과소 경보를 확인. 기본값이 과경보면 지표별 preset 검토(현 D22 k=2 교훈).
- 컴포넌트는 thin → 컴포넌트 테스트 없음. Playwright로 방식 전환(권위=range) + 네
  상태(insufficient/normal/watch/abnormal) 렌더 스팟 체크.

## 8. 데이터 흐름

```text
files (Map<msr, MsrFileResponse>) + 활성 method/임계 (뷰 상태)
  → timeSeriesPoints computed (AnalyzePanel, 선택 집합 전체 기준)
      시간순 정렬 → metric 추출
      → 검출기(peer/sibling/recent-shift): LOO 중심값(+std) 산출
      → 활성 채점 방식(range 권위 | stddev 진단): §3.1 밴딩 → AnomalyVerdict[]
      → combineVerdicts → 항목별 CombinedVerdict map
  → SkAnomalyBadge (차트 점) · SkAnomalyLegend · 방식 토글 · 요약 카운트
```

## 9. 에지 케이스 (요약)

- 선택 MSR < minN(또는 결측 제외 후 유효 N < minN) → `insufficient`(회색 점).
- range 방식에서 `|LOO center| < minAbsCenter` → % 밴드 무의미 → `insufficient`.
- 단일/복수 동방향 outlier → **LOO 중심** 덕에 masking 없이 검출(§4.2 fixture).
- stddev 방식에서 LOO 나머지 동일 + 판정 값 같음(std=0) → score 0, FP 없음.
- stddev 방식에서 평탄 나머지 + 단일 상이값 → "표준편차 0 기준 이탈"(abnormal, 절대 Δ).
- 특정 MSR에 parameter 없음 → 입력 단계 제외(결측 → `insufficient`).
- sibling 그룹 1~2개 → `minGroup` 미만 → `insufficient`.
- 방식(권위 range)/임계 변경 → 전 항목 재계산(stale 없음).

## 10. 비목표 (Non-goals)

- **고정 spec/control limit(USL/LSL, 절대 nm)** — 범위 방식이 평균 대비 %라 mock에
  한정해 충분. 절대 한계 기반은 실데이터 등장 후.
- **slope/trend(점진 추세) 검출** — recent-shift는 **step 변화만** 봅니다. 점진
  trend 검출은 실 시계열 요구 시 후속.
- **지표별 임계 preset 자동화** — Phase-1은 사용자 설정 + 캘리브레이션 게이트(§7)로
  대응. 자동 preset은 실데이터·flag율 데이터 확보 후.
- **MAD/수정 z-score** — 팀 비친숙으로 채택 안 함(평균/표준편차/범위만 노출).
- **device-statistics·FdcAnalysis 이관** — 본 스펙은 컨벤션을 *증명*만. 각 면은
  후속 스펙에서 채택(FDC의 ±3.5σ는 `abnormalK` 설정으로 흡수 검토).
- 백엔드 엔드포인트, verdict 영속화·알림/피드.
