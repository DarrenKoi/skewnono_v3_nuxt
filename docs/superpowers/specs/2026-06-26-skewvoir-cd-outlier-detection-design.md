# Skewvoir CD 시계열 이상치(outlier) 검출 · 설계

- 작성일: 2026-06-26
- 대상 페이지: skewvoir (CD-SEM / HV-SEM)
- 대상 차트: `시계열 추이` (AnalyzePanel 상단, `TimeSeriesChart.vue`)

## 1. 목적

선택한 여러 MSR의 CD 시계열(측정별 mean 1점)에서 통계적으로 비정상인
측정(MSR)을 자동으로 식별하고, 해당 점을 차트 안에서 색·크기로 강조한다.
FDC 차트가 이미 σ 기반 임계 밴드로 장비 이상거동을 표시하는 것에 대응하는,
CD 쪽의 보완 기능이다.

## 2. 범위 (Scope)

- 검출 레벨: **cross-MSR** (측정별 mean 1점을 시간순으로 비교). 단일 MSR
  내부의 chip별 `cd_value`는 대상이 아니다.
- 검출 신호: **CD mean (level shift)** 과 **spread (std)** 두 가지.
- 표시 방식: 차트 내 **점 recolor + 확대** 만. 별도의 밴드/라벨/요약 배지는
  추가하지 않는다 (tooltip 한 줄 보강은 예외 — 기존 tooltip에 편승).
- FDC drift 차트, CD↔FDC scatter, 단일 MSR 상세 뷰는 이번 범위에서 제외.

## 3. 검출 방법

Median + MAD 기반 수정 z-score(modified z-score). 작은 표본에서 소수의
극단값이 임계치를 부풀려 자기 자신을 숨기는 고전 z-score의 약점을 피한다.

- 임계 `k = 3.5` (수정 z-score 표준 기본값).
- 최소 표본 `minN = 5`. 5개 미만이면 MAD가 불안정하므로 검출을 건너뛴다
  (전부 정상 처리, 차트 변화 없음).
- 두 신호(mean, std)에 동일 규칙을 독립 적용한다.

## 4. 구성 단위

### 4.1 `front-dev-home/app/utils/madOutliers.ts` (신규, 순수 함수)

Vue/echarts 의존성 없는 순수 함수.

```ts
export function detectMadOutliers(
  values: number[],
  k = 3.5,
  minN = 5
): boolean[]
```

동작:

- `values.length < minN` → 전부 `false` 배열 반환.
- median 계산 → MAD = `median(|xᵢ − median|)` → 수정 z-score
  `0.6745 · (xᵢ − median) / MAD`. `|수정 z-score| > k` 인 점을 `true`로 표시.
- **MAD = 0 예외**(값의 절반 이상이 동일): 0으로 나누지 않고, **mean
  absolute deviation**(√(π/2)≈1.2533로 σ 스케일링)로 폴백해 *크기* 기준으로
  판정한다. 단순히 median과 다른 값을 전부 flag하면 큰 공유 부분군(예: 7개 중
  20이 3개)을 outlier로 오판하므로 magnitude 기준이 필요하다. meanAD=0(완전
  상수 시계열)이면 아무것도 flag하지 않는다.
- 입력 순서와 1:1 대응하는 boolean 배열을 반환(길이 동일).

### 4.2 `AnalyzePanel.vue` (수정)

`timeSeriesPoints` computed에서:

1. 기존처럼 시간순 정렬된 점들을 만든다.
2. `means = points.map(p => p.mean)`, `stds = points.map(p => p.std)` 추출.
3. `detectMadOutliers(means)`, `detectMadOutliers(stds)` 를 각각 호출.
4. 각 점에 `outlier: { mean: boolean, spread: boolean }` 를 부착해서 넘긴다.

### 4.3 `TimeSeriesChart.vue` (수정)

- `TimeSeriesPoint` 인터페이스에 선택 필드 추가:
  `outlier?: { mean: boolean; spread: boolean }`.
- `mean` series의 데이터를 숫자 배열 대신 per-datum 객체 배열로 구성
  (`{ value, itemStyle, symbolSize }`)하여 점별 스타일을 지정:
  - 정상 → 파랑 `#2563eb`, symbolSize 6
  - mean outlier → 빨강 `#dc2626`, symbolSize 10
  - spread-only outlier(mean은 정상) → 주황 `#d97706`, symbolSize 9
  - mean·spread 둘 다 → 빨강(=mean 우선), symbolSize 10
- 기존 tooltip에 flag된 경우에만 한 줄 추가:
  `⚠ outlier: mean` / `spread` / `mean+spread`.
- min/max 밴드, range area 등 나머지 series는 그대로 둔다.

## 5. 데이터 흐름

```text
files (Map<msr, MsrFileResponse>)
  → timeSeriesPoints computed (AnalyzePanel)
      시간순 정렬 → means/stds 추출
      → detectMadOutliers(means), detectMadOutliers(stds)
      → 각 점에 outlier 플래그 부착
  → TimeSeriesChart props.points
  → ECharts mean series per-datum itemStyle/symbolSize
```

## 6. 에지 케이스

- 선택 MSR < 5 → flag 없음, 차트 기존과 동일.
- 모든 mean(또는 std)이 동일 → MAD=0 → meanAD=0 경로, false positive 없음.
- 절반 이상 동일하지만 큰 공유 부분군 존재 → meanAD 폴백이 magnitude로 판정,
  부분군을 outlier로 오판하지 않음.
- 특정 MSR에 해당 parameter 없음 → 기존 `timeSeriesPoints` 단계에서 이미
  제외되므로 검출 입력에 들어오지 않는다.
- 단일 극단값(masking) → MAD 규칙이 정상 검출(고전 z-score는 놓치는 경우).

## 7. 테스트

`detectMadOutliers` 단위 테스트:

- 빈 배열 → `[]`.
- minN 미만 → 전부 `false`.
- 깨끗한 시계열(이상치 없음) → 전부 `false`.
- 명확한 단일 이상치 → 해당 인덱스만 `true`.
- 전부 동일 값(MAD=0) → 전부 `false`.
- masking 케이스(극단값 1개 + 나머지 군집) → 극단값 `true`.

## 8. 비목표 (Non-goals)

- 사용자 조정 가능한 민감도(k) UI.
- spec/control limit(USL/LSL) 기반 검출.
- 단일 MSR 내부 chip 단위 이상치.
- FDC/scatter 차트로의 확장.
- 백엔드 변경(검출은 현재 선택 집합 기준이라 프런트에서 계산).
