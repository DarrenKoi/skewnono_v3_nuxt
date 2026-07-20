# 12. 통계 유틸과 웨이퍼 좌표 모델

이 프로젝트의 도메인은 반도체 계측입니다. UI 뒤에는 **로버스트 통계**와 **물리 좌표 변환**이 깔려 있고, 이들은 전부 `utils/`의 **순수 함수**로 구현되어 있습니다(프레임워크·DOM·Nuxt 의존성 0 → `node --test`로 검증. 테스트 규율은 `13-testing/` 참고).

백엔드 개발자에게 이 챕터의 가치: **"UI 로직"이라고 뭉뚱그리던 것이 사실은 잘 정의된 수학이라는 것**, 그리고 그 수학이 왜 이렇게(평균이 아니라 median, std가 아니라 MAD) 구현됐는지의 *이유*입니다.

## 1. 왜 mean/std가 아니라 median/MAD인가

계측 데이터에는 **이상치(outlier)**가 섞입니다 — 오작동한 장비, 튄 측정 한 점. 평균(mean)과 표준편차(std)는 이상치 하나에 **크게 흔들립니다**(breakdown point 0). 반면 중앙값(median)과 MAD(median absolute deviation)는 데이터의 절반이 오염돼도 버팁니다(breakdown point 50%). 그래서 "정상 범위"를 정할 때 로버스트 통계를 씁니다.

### 1.1 median + MAD + modified z-score — `utils/radialAnalysis.ts`

```ts
const median = (values: number[]): number => {
  const sorted = [...values].sort((a, b) => a - b)
  return quantileSorted(sorted, 0.5)
}
```

```ts
const residualMedian = median(residuals)
const residualMad = 1.4826 * median(residuals.map(residual => Math.abs(residual - residualMedian)))
```

수학 해설:

- **MAD** = `median(|xᵢ − median(x)|)`. "각 점이 중앙값에서 얼마나 떨어졌나"의 중앙값.
- **`× 1.4826`** = `1 / Φ⁻¹(0.75)`. 정규분포 가정 하에서 MAD를 **표준편차 σ의 일치추정량(consistent estimator)**으로 만드는 보정 상수. 이걸 곱하면 MAD가 "로버스트한 σ"가 됩니다.
- **modified z-score** = `(xᵢ − median) / (1.4826·MAD)`. 평범한 z-score(`(x−mean)/std`)와 같은 뜻이지만, 극단값이 분모(스케일)를 부풀리지 못해 **몇 개의 이상치가 자기 자신을 정상으로 위장하지 못합니다.**

여기서는 `residualMad`를 곡선 적합(fit) 품질 지표로, `residualStd`(평범한 std)와 나란히 씁니다.

### 1.2 단순 median × multiplier 규칙 — `utils/outlierDetect.ts`

모든 이상치 탐지가 MAD를 쓰는 건 아닙니다. 더 단순한 규칙도 있습니다.

```ts
export const detectDeviceOutliers = (
  recipes: RecipeInput[],
  multiplier: number = DEFAULT_OUTLIER_MULTIPLIER   // 기본 2
): DeviceOutlierResult => {
  const allPoints = recipes.flatMap(r => r.parameters.map(p => p.point_count))
  const med = median(allPoints)
  const threshold = med * multiplier
  const outliers: PointOutlier[] = []
  for (const r of recipes) {
    for (const p of r.parameters) {
      if (p.point_count > threshold) {   // 임계값과 '정확히 같으면' 이상치 아님(strictly greater)
        outliers.push({ recipe_id: r.recipe_id, name: p.name, point_count: p.point_count })
      }
    }
  }
  return { median: med, threshold, outliers, outlier_count: outliers.length }
}
```

한 장비의 모든 레시피 `point_count`의 중앙값을 기준으로, `multiplier × median`을 초과하면 이상치. 콜로케이트된 `.test.ts`가 엣지 케이스를 못박습니다: 빈 배열 → median 0; **임계값과 정확히 같은 값은 이상치 아님**(`>`이지 `>=` 아님); multiplier 설정 가능; 기본값 2.

> **교훈**: "이상치"의 정의가 파일마다 다릅니다. 어떤 화면은 로버스트 z-score(radialAnalysis), 어떤 화면은 median×배수(outlierDetect), 또 어떤 화면은 σ 밴딩(아래 anomaly). **도메인 맥락이 통계 선택을 결정**합니다 — 정답이 하나가 아닙니다.

### 1.3 σ 기반 z-score 밴딩 — `utils/anomaly/score.ts`

`scoreByStddev`는 고전적인 `k = (value − mean) / std`를 계산해 `normal / watch / abnormal`로 밴딩합니다. `scoreByRange`는 leave-one-out 중심 대비 퍼센트 편차 방식(이쪽이 이 폴더의 "권위 있는" 판정). 이 `anomaly/` 서브폴더가 "이상 판정"의 소유자입니다.

## 2. 기술 통계의 단일 소스 — `utils/stats.ts`

descriptive statistics를 한곳에 모아 둡니다. **각 함수의 결정에 이유가 있습니다.**

```ts
export const iqrFences = (values: number[]): IqrFences | null => {
  const sorted = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return null
  const q1 = quantileSorted(sorted, 0.25)
  const q3 = quantileSorted(sorted, 0.75)
  const iqr = q3 - q1
  return { q1, q3, lower: q1 - 1.5 * iqr, upper: q3 + 1.5 * iqr }
}
```

주요 설계 결정:

- **`mean`은 빈 배열에서 `NaN`을 반환**(0이 아님). 0을 반환하면 "평균이 0"과 "데이터 없음"을 구분 못 함 — `01-typescript/03-null-undefined-...`의 교훈과 같은 맥락.
- **`sampleStd`는 2-pass n−1 방식.** CD가 ~100nm인데 편차가 ~1nm 수준이라, 1-pass(제곱합) 공식은 **파국적 상쇄(catastrophic cancellation)**로 정밀도를 잃습니다. 2-pass가 안전.
- **`quantileSorted`는 R-7 선형보간**(numpy·Excel 기본). 분위수 정의는 여러 개라서 어느 걸 쓰는지 명시가 중요.
- **`pearson`은 n≥3 요구, 아니면 `null`**(가짜 0 안 만듦). `spearman`은 순위에 대한 Pearson(동순위 평균 보정).
- **`iqrFences`(Tukey 1.5×IQR)는 whisker 렌더링 전용 — 이상치 판정이 아님.** 주석에 명시.

## 3. 박스플롯 — 함대가 작을 땐 fencing을 끈다

`utils/boxplotStats.ts`:

```ts
export const boxStats = (values: number[]): BoxStats | null => {
  const sorted = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b)
  if (sorted.length === 0) return null
  return {
    min: sorted[0]!,
    q1: quantileSorted(sorted, 0.25),
    median: quantileSorted(sorted, 0.5),
    q3: quantileSorted(sorted, 0.75),
    max: sorted[sorted.length - 1]!
  }
}
```

**대조 포인트**: `boxStats`는 min/max에 **진짜 극값**을 씁니다(fencing 없음). `iqrFences`와 정반대 정책입니다. 왜? 하드웨어 함대는 장비가 4~6대뿐이라, 1.5×IQR fencing을 걸면 **실재하는 장비가 이상치로 숨겨집니다.** 데이터 규모와 도메인이 정책을 뒤집는 예입니다.

## 4. 웨이퍼 좌표 모델 — `utils/waferGeometry.ts`

계측 데이터는 웨이퍼 위 물리적 위치에 붙어 있습니다. 세 개의 도메인 필드를 이해해야 합니다.

| 필드 | 의미 | 단위 |
| --- | --- | --- |
| `chip_number` | die **인덱스** `(col, row)` — 웨이퍼 중심 기준 | 정수 격자 |
| `stage_coordinate` | 물리 좌표 `(x, y)` — **코너 원점** | **nm** |
| `exe_detail_info.wafer_size` | 웨이퍼 지름 | **mm** |
| `exe_detail_info.chip_pitch` | die 하나의 간격 | **nm** |

웨이퍼 중심은 nm 좌표계에서 `(wafer_size/2, wafer_size/2)`에 있습니다. 모든 플롯은 **웨이퍼 중심 기준 mm**로 변환합니다. `NM_PER_MM = 1_000_000`.

```ts
export const parseWaferGeometry = (info?: ExeDetailInfo | null): WaferGeometry => {
  const sizeMm = num(info?.wafer_size) || 300
  const [px, py] = (info?.chip_pitch ?? '').split(',')
  const pxNm = num(px)
  const pyNm = num(py)
  return {
    sizeMm,
    radiusMm: sizeMm / 2,
    centerNm: (sizeMm / 2) * NM_PER_MM,
    pitchXmm: pxNm > 0 ? pxNm / NM_PER_MM : 0,
    pitchYmm: pyNm > 0 ? pyNm / NM_PER_MM : 0
  }
}

// stage_coordinate 문자열 → 웨이퍼 중심 기준 물리 위치(mm)
export const stagePosMm = (stage: string, geo: WaferGeometry): [number, number] | null => {
  const parts = stage.split(',')
  if (parts.length !== 2) return null
  const x = num(parts[0])
  const y = num(parts[1])
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null
  return [(x - geo.centerNm) / NM_PER_MM, (y - geo.centerNm) / NM_PER_MM]
}

// chip_number "(col,row)" → die 중심(mm). pitch를 쓰므로 측정 offset과 무관하게 격자에 안착.
export const dieCenterMm = (col: number, row: number, geo: WaferGeometry): [number, number] =>
  [col * geo.pitchXmm, row * geo.pitchYmm]

// stage_coordinate → 웨이퍼 중심으로부터의 거리(mm). radius-plot의 x축.
export const siteRadiusMm = (stage: string, geo: WaferGeometry): number | null => {
  const p = stagePosMm(stage, geo)
  return p ? Math.hypot(p[0], p[1]) : null
}
```

읽을 때 포인트:

- **단위 변환이 명시적.** nm ↔ mm를 `NM_PER_MM`로 한곳에서 처리. 단위 혼동은 계측 소프트웨어의 대표적 버그원이므로 이렇게 격리합니다.
- **`stagePosMm` = 측정된 실제 위치**, **`dieCenterMm` = pitch로 계산한 격자 중심.** 둘은 다릅니다 — 측정점은 die 안에서 조금씩 어긋나지만, die 타일은 격자에 딱 맞아야 예쁩니다.
- **결측/이상 입력에 `null` 반환** → 호출부가 mm 라벨로 fallback하거나 그 점을 건너뜁니다.

## 5. 좌표에서 플롯으로 — `utils/waferPoints.ts`

`buildWaferPoints(rows, geo)`가 두 가지 해상도로 세 점 집합을 만듭니다.

- **`fieldPoints`** — 측정 row 하나당 한 점, **물리 위치**(`stagePosMm`)에. 개별 hover 가능, `n = 1`.
- **`diePoints`** — `chip_number`당 한 점, 값 = 그 die 측정들의 **평균**, 위치 = `dieCenterMm(col,row)`(pitch 격자 중심). `n` = 측정 개수.
- **`failurePoints`** — 측정 안 된 row(`cd_value` null)를 물리 위치에.

`chip_number`는 `utils/waferChip.ts::parseChipXY`가 파싱합니다("x, y" 분리 후 정확히 두 개의 유한수 요구 — `Number.isNaN(undefined)`가 `false`라서 길이 검사도 필요하다는 주석이 있음). 표시 토글(crosshair, die-grid, notch, 수동/자동 색범위)은 `utils/waferMapOptions.ts`가 관리합니다.

## 6. 이 챕터의 큰 교훈

- **로버스트 통계(median/MAD)는 계측처럼 이상치가 섞이는 데이터의 기본기.** mean/std는 이상치에 흔들린다.
- **"이상치"의 정의는 하나가 아니다.** 화면·도메인 맥락이 통계 방법(z-score / median×배수 / σ밴딩 / IQR)을 고른다.
- **엣지 케이스를 타입/반환값으로 정직하게.** 빈 데이터는 `NaN`/`null`, 가짜 0을 만들지 않는다.
- **단위 변환은 한곳에 격리.** nm↔mm 혼동은 계측 SW의 단골 버그.
- **모든 계산은 순수 함수 + 콜로케이트 테스트.** `13-testing/`가 그 규율을 다룬다.
