# CD-SEM Mag/Pixel 가이드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 배율·픽셀 설정에서 픽셀당 실제 길이(nm/px)를 유도하고, 목표 CD로부터 적정 배율·픽셀 조합을 역산해주는 CD-SEM 레시피 셋업 가이드를 만든다.

**Architecture:** 모든 계산은 `FOV_µm = 135000 / Mag` 상수 하나에서 유도되는 순수 함수다. 백엔드 변경 없음, API 호출 없음. `app/utils/magPixel.ts`가 단일 계산 코어이고, `/mag-pixel` 페이지와 기존 스큐보아 갤러리가 같은 함수를 공유한다.

**Tech Stack:** Nuxt 4 (`ssr: false`), NuxtUI, TypeScript, `node:test` + `node:assert/strict`

## Global Constraints

- 테스트 실행: `npm --prefix front-dev-home test` (`node --test "app/**/*.test.ts"`)
- 린트: `npm --prefix front-dev-home run lint` · 마크다운: `npm run lint:md` (repo root)
- 계산 함수는 유효하지 않은 입력에 **`null`을 반환**한다. `Infinity`/`NaN`을 반환 경로 밖으로 내보내지 않는다.
- Series 판정은 **모델코드 접두사**로만 한다. `TOOL_SPECS.eqp_models` 목록을 분류에 쓰지 않는다.
- 화면 문구는 한국어, `~입니다/~합니다` 체를 쓴다.
- 백엔드(`back_dev_home/`) 파일은 이 계획에서 **하나도 수정하지 않는다.**
- 커밋은 `type(scope): summary` 형식, 본문에 무엇을 왜 바꿨는지 적는다.

## File Structure

| 파일 | 책임 |
| --- | --- |
| `docs/datatables/cdsem_mag_pixel_table.txt` | 원본 스키마 기록 (정정 2건) |
| `front-dev-home/app/utils/magPixel.ts` | 계산 코어 — 유도·판정·추천 전부 |
| `front-dev-home/app/utils/magPixel.test.ts` | 코어 테스트 |
| `front-dev-home/app/pages/mag-pixel.vue` | 페이지 셸 + 입력 상태 |
| `front-dev-home/app/components/magpixel/ResultTable.vue` | 통합 테이블 (참조/판정 2모드) |
| `front-dev-home/app/components/magpixel/RecommendationPanel.vue` | 추천 카드 + 민감도 + 512vs1024 안내 |
| `front-dev-home/app/components/magpixel/PatternSchematic.vue` | 모식도 ① 전체 FOV + ② Pitch 확대 |
| `front-dev-home/app/components/magpixel/SemSimulation.vue` | SEM 이미지 시뮬레이션 (접힘 토글) |
| `front-dev-home/app/components/nav/AppHeader.vue` | 헤더 우측 진입 버튼 |
| `front-dev-home/app/components/nav/FeatureTabs.vue` | `INFO_PATHS` 등록 |
| `front-dev-home/app/utils/skewvoirAnalysis/gallery.ts` | 갤러리 엔트리 파생 필드 |
| `front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue` | 스케일 바 캘리브레이션 |

계산은 전부 `magPixel.ts`에 모으고 Vue 컴포넌트는 렌더링만 한다. 판정 문구까지 순수 함수로 두어 테스트로 고정한다.

---

### Task 1: 계산 코어 — FOV·픽셀 크기·파싱 (+ 원본 문서 정정)

**Files:**

- Modify: `docs/datatables/cdsem_mag_pixel_table.txt` (5행, 18행)
- Create: `front-dev-home/app/utils/magPixel.ts`
- Test: `front-dev-home/app/utils/magPixel.test.ts`

**Interfaces:**

- Consumes: 없음 (최초 태스크)
- Produces: `fovUm(mag)`, `fovNm(mag)`, `parsePixelSetting(text)`, `pixelSizeNm(mag, pixels)`, `pxPerCd(mag, pixels, cdNm)`, `scanTimeFactor(pixels)`, `PIXEL_SETTINGS`, `PixelDims`. 전부 무효 입력에 `null`.

- [ ] **Step 1: 원본 문서 정정 2건**

`docs/datatables/cdsem_mag_pixel_table.txt`의 5행에서 `4900`을 `5000`으로 바꾼다. 정정 후 5행:

```text
Mag (1000, 2000, 5000, 8000, 10000, 20000, 50000, 60000, 70000, 80000, 100000, 120000, 150000, 180000
```

같은 파일 18행을 아래로 바꾼다. 원문은 상수 단위를 `nm`이라고 적었지만, FOV가 µm으로 정의되어 있으므로 상수도 µm이어야 한다(135,000 µm = 135 mm).

```text
135000 is constant (screen width in um at 1x magnification of the tool = 135 mm)
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`front-dev-home/app/utils/magPixel.test.ts`를 새로 만든다.

```ts
// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { fovUm, fovNm, parsePixelSetting, pixelSizeNm, pxPerCd, scanTimeFactor } from './magPixel.ts'

const near = (actual: number | null, expected: number, tol = 1e-6) => {
  assert.notEqual(actual, null)
  assert.ok(Math.abs((actual as number) - expected) < tol, `${actual} !≈ ${expected}`)
}

test('fovUm derives field of view from the 135000 um screen width', () => {
  near(fovUm(250_000), 0.54)
  near(fovUm(180_000), 0.75)
  near(fovNm(180_000), 750)
})

test('pixelSizeNm converts FOV to nanometres per pixel', () => {
  near(pixelSizeNm(250_000, 512), 1.0546875)
  near(pixelSizeNm(180_000, 512), 1.46484375)
  near(pixelSizeNm(1_000_000, 4096), 0.032958984375)
})

test('pxPerCd reports how many pixels land on one CD', () => {
  near(pxPerCd(180_000, 512, 40), 27.306666666, 1e-6)
})

test('invalid magnification yields null, never Infinity', () => {
  // mock msr rows carry mag 0 on empty rows (msr_file/providers/mock.py:562)
  assert.equal(fovUm(0), null)
  assert.equal(fovNm(0), null)
  assert.equal(pixelSizeNm(0, 512), null)
  assert.equal(fovUm(-1), null)
  assert.equal(fovUm(Number.NaN), null)
  assert.equal(fovUm(Number.POSITIVE_INFINITY), null)
})

test('invalid pixel counts yield null', () => {
  assert.equal(pixelSizeNm(180_000, 0), null)
  assert.equal(pixelSizeNm(180_000, -512), null)
  assert.equal(pxPerCd(180_000, 512, 0), null)
})

test('parsePixelSetting reads the "512,512" string form', () => {
  assert.deepEqual(parsePixelSetting('512,512'), { x: 512, y: 512 })
  assert.deepEqual(parsePixelSetting(' 1024 , 1024 '), { x: 1024, y: 1024 })
})

test('parsePixelSetting rejects the empty-row sentinel and malformed input', () => {
  assert.equal(parsePixelSetting('0,0'), null)
  assert.equal(parsePixelSetting(''), null)
  assert.equal(parsePixelSetting('512'), null)
  assert.equal(parsePixelSetting('512,512,512'), null)
  assert.equal(parsePixelSetting('abc,def'), null)
  assert.equal(parsePixelSetting(null), null)
  assert.equal(parsePixelSetting(undefined), null)
})

test('scanTimeFactor is quadratic in pixel count', () => {
  assert.equal(scanTimeFactor(512), 1)
  assert.equal(scanTimeFactor(1024), 4)
  assert.equal(scanTimeFactor(2048), 16)
  assert.equal(scanTimeFactor(4096), 64)
  assert.equal(scanTimeFactor(0), null)
})
```

- [ ] **Step 3: 테스트가 실패하는지 확인한다**

Run: `npm --prefix front-dev-home test 2>&1 | tail -20`
Expected: FAIL — `Cannot find module './magPixel.ts'`

- [ ] **Step 4: 최소 구현을 쓴다**

`front-dev-home/app/utils/magPixel.ts`를 새로 만든다.

```ts
// CD-SEM 배율 ↔ 픽셀 크기 유도.
//
// 원본: docs/datatables/cdsem_mag_pixel_table.txt
//   FOV_µm       = 135000 / Mag
//   PixelSize_nm = FOV_µm × 1000 / N_pixels
//
// 135000의 단위는 µm(= 135 mm 화면폭)이다. 원본 문서는 이를 nm으로 적었으나
// 그러면 FOV가 µm으로 나오지 않는다 — 문서 쪽을 정정했다.
//
// null 규율: mock은 빈 row에 mag 0 / pixel "0,0"을 싣는다
// (msr_file/providers/mock.py:562). 135000/0은 Infinity이므로, 유효하지 않은
// 입력에는 null을 반환하고 호출부가 게이팅한다. useMsrFileApi.ts의 cd_value가
// 쓰는 것과 같은 규율이다 — 절대 0으로 강제 변환하지 않는다.

/** 1× 배율에서의 장비 화면폭 (µm). 135,000 µm = 135 mm. */
const SCREEN_WIDTH_UM = 135_000

/** 장비가 제공하는 픽셀 설정. 실사용은 512·1024가 대부분이다. */
export const PIXEL_SETTINGS = [512, 1024, 2048, 4096] as const
export type PixelSetting = typeof PIXEL_SETTINGS[number]

/** 스캔 시간 기준 픽셀 수 — 배수는 이 값 대비로 센다. */
const BASE_PIXELS = 512

const isPositive = (n: unknown): n is number =>
  typeof n === 'number' && Number.isFinite(n) && n > 0

/** 배율에서 FOV(µm). mag가 양의 유한수가 아니면 null. */
export const fovUm = (mag: number): number | null =>
  isPositive(mag) ? SCREEN_WIDTH_UM / mag : null

/** 배율에서 FOV(nm). */
export const fovNm = (mag: number): number | null => {
  const um = fovUm(mag)
  return um === null ? null : um * 1000
}

export interface PixelDims {
  x: number
  y: number
}

/**
 * `meas_condition_pixel`("512,512")을 파싱한다.
 * 빈 row 센티널 "0,0", 빈 문자열, 형식 오류는 전부 null.
 */
export const parsePixelSetting = (text: string | null | undefined): PixelDims | null => {
  if (typeof text !== 'string') return null
  const parts = text.split(',')
  if (parts.length !== 2) return null
  const x = Number(parts[0]?.trim())
  const y = Number(parts[1]?.trim())
  return isPositive(x) && isPositive(y) ? { x, y } : null
}

/**
 * 픽셀당 실제 길이(nm).
 * FOV는 **폭**이므로 비정사각 설정이 오면 x(가로 픽셀 수)를 넘겨야 한다.
 */
export const pixelSizeNm = (mag: number, pixels: number): number | null => {
  const nm = fovNm(mag)
  return nm !== null && isPositive(pixels) ? nm / pixels : null
}

/** CD 하나에 얹히는 픽셀 수. */
export const pxPerCd = (mag: number, pixels: number, cdNm: number): number | null => {
  const size = pixelSizeNm(mag, pixels)
  return size !== null && isPositive(cdNm) ? cdNm / size : null
}

/** 512 px 대비 상대 스캔 시간. 시간 ∝ X×Y이므로 픽셀 수의 제곱에 비례한다. */
export const scanTimeFactor = (pixels: number): number | null =>
  isPositive(pixels) ? (pixels / BASE_PIXELS) ** 2 : null
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

Run: `npm --prefix front-dev-home test 2>&1 | tail -20`
Expected: PASS — 신규 8개 테스트 통과, 기존 테스트 회귀 없음

- [ ] **Step 6: 린트**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -10`
Expected: 신규 파일에 오류 없음

- [ ] **Step 7: 커밋**

```bash
git add docs/datatables/cdsem_mag_pixel_table.txt \
        front-dev-home/app/utils/magPixel.ts \
        front-dev-home/app/utils/magPixel.test.ts
git commit -m "feat(mag-pixel): derive nm-per-pixel from magnification

Adds the calculation core behind FOV = 135000/Mag. Every MSR row already
carries meas_condition_mag and meas_condition_pixel; until now neither could
be turned into the physical quantity engineers reason about.

Invalid input returns null rather than Infinity. The mock writes mag 0 and
pixel \"0,0\" on empty rows, so an ungated 135000/0 would render as
'Infinity nm/px' -- the same trap cd_value already documents in
useMsrFileApi.ts.

Also corrects the source datatable: the 135000 constant is documented as nm
but must be um (135 mm screen width), and the CG MAG list's 4900 is a typo
for 5000 (user-confirmed 2026-07-25)."
```

---

### Task 2: Series(CG/GT) 판정과 참조표 생성

**Files:**

- Modify: `front-dev-home/app/utils/magPixel.ts` (append)
- Test: `front-dev-home/app/utils/magPixel.test.ts` (append)

**Interfaces:**

- Consumes: Task 1의 `fovNm`, `PIXEL_SETTINGS`, `scanTimeFactor`
- Produces: `MagSeries` (`'CG' | 'GT'`), `seriesFromModel(modelCd)`, `magRange(series)`, `isAssumedMag(series, mag)`, `buildMagPixelTable(series)`, `MagPixelRow { mag, fovNm, assumed, cells }`, `MagPixelCell { pixels, nmPerPx, scanFactor }`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`magPixel.test.ts` 맨 아래에 덧붙인다. import 줄도 함께 늘린다.

```ts
import {
  seriesFromModel, magRange, isAssumedMag, buildMagPixelTable
} from './magPixel.ts'

test('seriesFromModel classifies on the model-code PREFIX', () => {
  assert.equal(seriesFromModel('CG6300'), 'CG')
  assert.equal(seriesFromModel('GT2000'), 'GT')
  assert.equal(seriesFromModel('GT2000S'), 'GT')
})

test('seriesFromModel normalises case and surrounding whitespace', () => {
  // parquet/Redis text cells carry both; a stray space must not drop a tool
  assert.equal(seriesFromModel(' cg6320 '), 'CG')
  assert.equal(seriesFromModel('gt2000'), 'GT')
})

test('seriesFromModel returns null for non-CD-SEM families', () => {
  assert.equal(seriesFromModel('TP3000'), null)
  assert.equal(seriesFromModel('VERITYSEM_1'), null)
  assert.equal(seriesFromModel(''), null)
  assert.equal(seriesFromModel(null), null)
})

test('seriesFromModel accepts codes absent from the mock roster', () => {
  // eqp_models in _tool_specs.py is mock fodder, NOT a classifier: judging real
  // tools against it silently dropped 8 office tools on 2026-07-24
  assert.equal(seriesFromModel('CG9999'), 'CG')
  assert.equal(seriesFromModel('GT7777'), 'GT')
})

test('magRange covers CG to 500K and GT to 1000K', () => {
  const cg = magRange('CG')
  const gt = magRange('GT')
  assert.equal(cg.length, 23)
  assert.equal(gt.length, 28)
  assert.equal(cg[0], 1000)
  assert.equal(cg[cg.length - 1], 500_000)
  assert.equal(gt[gt.length - 1], 1_000_000)
})

test('magRange carries the corrected 5000, not the 4900 typo', () => {
  assert.ok(magRange('CG').includes(5000))
  assert.ok(!magRange('CG').includes(4900))
})

test('isAssumedMag flags only the unverified GT tail above 500K', () => {
  // the source doc says "500000 이후 단위가 어떻게 되는지 확인 안되지만,
  // 100000단위로 가정" — those rows must not read as confirmed
  assert.equal(isAssumedMag('GT', 600_000), true)
  assert.equal(isAssumedMag('GT', 1_000_000), true)
  assert.equal(isAssumedMag('GT', 500_000), false)
  assert.equal(isAssumedMag('CG', 500_000), false)
})

test('buildMagPixelTable emits one row per mag with all four pixel settings', () => {
  const rows = buildMagPixelTable('CG')
  assert.equal(rows.length, 23)
  const row = rows.find(r => r.mag === 180_000)
  assert.notEqual(row, undefined)
  near(row!.fovNm, 750)
  assert.equal(row!.assumed, false)
  assert.equal(row!.cells.length, 4)
  assert.deepEqual(row!.cells.map(c => c.pixels), [512, 1024, 2048, 4096])
  near(row!.cells[0]!.nmPerPx, 1.46484375)
  assert.equal(row!.cells[1]!.scanFactor, 4)
})
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `npm --prefix front-dev-home test 2>&1 | tail -20`
Expected: FAIL — `seriesFromModel is not exported` 계열 오류

- [ ] **Step 3: 구현을 덧붙인다**

`magPixel.ts` 맨 아래에 덧붙인다.

```ts
// ── Series (CG / GT) ────────────────────────────────────────────────────────
//
// MAG 범위가 계열마다 다르다. 판정은 반드시 모델코드 **접두사**로 한다 —
// back_dev_home/ebeam/hitachi/_tool_specs.py의 model_to_tool_type()과
// composables/useSemListApi.ts의 classifyToolType()이 쓰는 방식이다.
// TOOL_SPECS.eqp_models 목록은 mock 재료이지 분류기가 아니다: 그 목록으로
// 분류했다가 목록에 없는 실장비 8대가 오피스 화면에서 조용히 사라진 적이
// 있다(2026-07-24).

export type MagSeries = 'CG' | 'GT'

/** CG 계열 MAG (23개). 확인된 전 구간. */
const MAG_CG: readonly number[] = [
  1000, 2000, 5000, 8000, 10_000, 20_000, 50_000, 60_000, 70_000, 80_000,
  100_000, 120_000, 150_000, 180_000, 200_000, 220_000, 250_000, 300_000,
  350_000, 400_000, 420_000, 450_000, 500_000
]

/**
 * GT 계열이 500K 위로 더 갖는 구간 (5개).
 * 원본 문서가 "확인 안되지만 100000단위로 가정"이라고 명시한 값이므로
 * isAssumedMag()로 표시해 확정값과 구분한다.
 */
const MAG_GT_ASSUMED: readonly number[] = [600_000, 700_000, 800_000, 900_000, 1_000_000]

const MAG_GT: readonly number[] = [...MAG_CG, ...MAG_GT_ASSUMED]

const SERIES_PREFIXES: readonly MagSeries[] = ['CG', 'GT']

/** 모델코드 접두사로 계열을 판정한다. CD-SEM이 아니면 null. */
export const seriesFromModel = (eqpModelCd: string | null | undefined): MagSeries | null => {
  if (typeof eqpModelCd !== 'string') return null
  const code = eqpModelCd.trim().toUpperCase()
  return SERIES_PREFIXES.find(prefix => code.startsWith(prefix)) ?? null
}

export const magRange = (series: MagSeries): readonly number[] =>
  series === 'GT' ? MAG_GT : MAG_CG

/** 원본 문서에서 확인되지 않아 가정한 구간인지. */
export const isAssumedMag = (series: MagSeries, mag: number): boolean =>
  series === 'GT' && MAG_GT_ASSUMED.includes(mag)

export interface MagPixelCell {
  pixels: number
  nmPerPx: number
  /** 512 px 대비 상대 스캔 시간. */
  scanFactor: number
}

export interface MagPixelRow {
  mag: number
  fovNm: number
  /** true면 원본 문서 미확인 구간 — 화면에서 `가정` 배지를 붙인다. */
  assumed: boolean
  cells: MagPixelCell[]
}

/** 계열 전체의 Mag × Pixel 참조표. 입력이 없을 때 그대로 렌더된다. */
export const buildMagPixelTable = (series: MagSeries): MagPixelRow[] => {
  const rows: MagPixelRow[] = []
  for (const mag of magRange(series)) {
    const fov = fovNm(mag)
    if (fov === null) continue
    const cells: MagPixelCell[] = []
    for (const pixels of PIXEL_SETTINGS) {
      const factor = scanTimeFactor(pixels)
      if (factor === null) continue
      cells.push({ pixels, nmPerPx: fov / pixels, scanFactor: factor })
    }
    rows.push({ mag, fovNm: fov, assumed: isAssumedMag(series, mag), cells })
  }
  return rows
}
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `npm --prefix front-dev-home test 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add front-dev-home/app/utils/magPixel.ts front-dev-home/app/utils/magPixel.test.ts
git commit -m "feat(mag-pixel): add CG/GT series ranges and the reference table

CG tops out at 500K, GT at 1000K, so mag range is the first place cd-sem
needs to split by series -- model_to_tool_type() collapses both to 'cd-sem'.

Classification goes by model-code PREFIX, mirroring _tool_specs.py. A test
pins that codes absent from the mock roster (CG9999) still classify: judging
real tools against eqp_models is what silently dropped 8 office tools on
2026-07-24.

GT's 600K-1000K rows are flagged assumed -- the source doc states the step
above 500K was never confirmed."
```

---

### Task 3: 필요 FOV·추천 엔진·안내 문구

**Files:**

- Modify: `front-dev-home/app/utils/magPixel.ts` (append)
- Test: `front-dev-home/app/utils/magPixel.test.ts` (append)

**Interfaces:**

- Consumes: Task 1·2 전체
- Produces: `requiredFovNm(patternCount, pitchNm, marginRatio)`, `recommend(input): Recommendation | null`, `cellVerdict(...)`, `marginSensitivity(input)`, `pixelGuidance(rec, minPxPerCd)`, 상수 `MARGIN_PRESETS`, `DEFAULT_MARGIN`, `DEFAULT_MIN_PX_PER_CD`, `DEFAULT_PATTERN_COUNT`, 타입 `CalcInput`, `Recommendation`, `CellVerdict`, `PixelGuidance`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`magPixel.test.ts` 맨 아래에 덧붙인다.

```ts
import {
  requiredFovNm, recommend, cellVerdict, marginSensitivity, pixelGuidance,
  MARGIN_PRESETS, DEFAULT_MARGIN, DEFAULT_MIN_PX_PER_CD
} from './magPixel.ts'
import type { CalcInput } from './magPixel.ts'

const input = (over: Partial<CalcInput> = {}): CalcInput => ({
  series: 'CG', cdNm: 40, pitchNm: 90, patternCount: 8,
  marginRatio: DEFAULT_MARGIN, minPxPerCd: DEFAULT_MIN_PX_PER_CD, ...over
})

test('requiredFovNm widens the field of view to leave a margin on each side', () => {
  near(requiredFovNm(8, 90, 0), 720)
  near(requiredFovNm(8, 90, 0.10), 900)
  near(requiredFovNm(8, 90, 0.20), 1200)
})

test('requiredFovNm rejects a margin that leaves no room for the pattern', () => {
  assert.equal(requiredFovNm(8, 90, 0.5), null)
  assert.equal(requiredFovNm(8, 90, 0.6), null)
  assert.equal(requiredFovNm(8, 90, -0.1), null)
  assert.equal(requiredFovNm(0, 90, 0.1), null)
  assert.equal(requiredFovNm(8, 0, 0.1), null)
})

test('MARGIN_PRESETS are the five selectable values, defaulting to 10%', () => {
  assert.deepEqual([...MARGIN_PRESETS], [0, 0.05, 0.10, 0.15, 0.20])
  assert.equal(DEFAULT_MARGIN, 0.10)
})

// ── the regression this whole feature turns on ─────────────────────────────
test('margin changes the recommended magnification, not just the drawing', () => {
  // 8 patterns x 90nm = 720nm span. With no margin that fits 180K (FOV 750nm)
  // -- patterns flush against the frame edge. With 10% per side the required
  // FOV becomes 900nm and only 150K qualifies.
  assert.equal(recommend(input({ marginRatio: 0 }))?.mag, 180_000)
  assert.equal(recommend(input({ marginRatio: 0.10 }))?.mag, 150_000)
})

test('recommend picks the highest mag that still fits, and the cheapest pixels', () => {
  const rec = recommend(input())
  assert.equal(rec?.reason, 'ok')
  assert.equal(rec?.mag, 150_000)
  assert.equal(rec?.pixels, 512)
  assert.equal(rec?.scanFactor, 1)
  near(rec?.requiredFovNm ?? null, 900)
  near(rec?.pxPerCd ?? null, 22.7555555, 1e-5)
})

test('recommend falls back to CD x 2 when pitch is unknown', () => {
  const rec = recommend(input({ pitchNm: null }))
  assert.equal(rec?.pitchAssumed, true)
  assert.equal(rec?.effectivePitchNm, 80)
  const known = recommend(input())
  assert.equal(known?.pitchAssumed, false)
  assert.equal(known?.effectivePitchNm, 90)
})

test('recommend refuses a pitch that cannot hold the CD', () => {
  assert.equal(recommend(input({ pitchNm: 40 })), null)
  assert.equal(recommend(input({ pitchNm: 20 })), null)
  assert.equal(recommend(input({ cdNm: 0 })), null)
})

test('recommend reports no-mag when even the lowest magnification is too tight', () => {
  // 400 patterns x 90nm / 0.8 = 45000nm required; 1K gives only 135000nm... so
  // push far past that: 20000 patterns needs 2.25e6 nm, above every FOV
  const rec = recommend(input({ patternCount: 20_000 }))
  assert.equal(rec?.reason, 'no-mag')
  assert.equal(rec?.mag, null)
})

test('recommend reports no-pixels when even 4096 misses the threshold', () => {
  const rec = recommend(input({ cdNm: 0.4, pitchNm: 90, minPxPerCd: 8 }))
  assert.equal(rec?.reason, 'no-pixels')
  assert.notEqual(rec?.mag, null)
  assert.equal(rec?.pixels, null)
})

test('cellVerdict separates an FOV failure from a pixel failure', () => {
  const req = 900
  assert.equal(cellVerdict(180_000, 512, 40, req, 8), 'over-fov')
  assert.equal(cellVerdict(150_000, 512, 40, req, 8), 'ok')
  assert.equal(cellVerdict(20_000, 512, 40, req, 8), 'under-pixel')
})

test('marginSensitivity shows the staircase across every preset', () => {
  const rows = marginSensitivity(input())
  assert.equal(rows.length, 5)
  assert.deepEqual(rows.map(r => r.mag), [180_000, 150_000, 150_000, 120_000, 100_000])
  near(rows[0]!.requiredFovNm, 720)
  near(rows[4]!.requiredFovNm, 1200)
})

test('pixelGuidance tells the user 512 is enough and what 1024 would cost', () => {
  const g = pixelGuidance(recommend(input())!, DEFAULT_MIN_PX_PER_CD)
  assert.equal(g.tone, 'ok')
  assert.match(g.headline, /512/)
  assert.match(g.detail, /4배/)
})

test('pixelGuidance warns when a larger pixel count is actually required', () => {
  const rec = recommend(input({ cdNm: 4, pitchNm: 90 }))!
  assert.notEqual(rec.pixels, 512)
  const g = pixelGuidance(rec, DEFAULT_MIN_PX_PER_CD)
  assert.equal(g.tone, 'warn')
})

test('pixelGuidance escalates when nothing works', () => {
  assert.equal(pixelGuidance(recommend(input({ patternCount: 20_000 }))!, 8).tone, 'error')
})
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `npm --prefix front-dev-home test 2>&1 | tail -20`
Expected: FAIL — `requiredFovNm is not exported`

- [ ] **Step 3: 구현을 덧붙인다**

`magPixel.ts` 맨 아래에 덧붙인다.

```ts
// ── 셋업 역산 ───────────────────────────────────────────────────────────────
//
// 제약이 둘이고 서로 반대 방향으로 당긴다.
//   ① FOV 제약  — 패턴 N개 + 여유 마진이 화면에 다 들어와야 한다 → 배율 상한
//   ② 픽셀 제약 — CD 하나에 픽셀이 충분히 얹혀야 측정된다      → 픽셀 하한
// 그래서 답은 하나가 아니라 성립 구간이고, 추천은 그 구간의 한 점이다.

/** 여유 마진 프리셋 (각 변 기준). 배율이 이산값이라 자유 입력은 없는 정밀도를 시사한다. */
export const MARGIN_PRESETS = [0, 0.05, 0.10, 0.15, 0.20] as const
export const DEFAULT_MARGIN = 0.10
export const DEFAULT_PATTERN_COUNT = 8

/**
 * CD 하나를 신뢰성 있게 측정하기 위한 최소 픽셀 수 — **잠정값**.
 * 사내 계측 기준이 아직 정해지지 않았다(사용자 확인 2026-07-25). 화면에서
 * 조정 가능하게 열어두었으므로, 기준이 확정되면 이 상수만 바꾸면 된다.
 */
export const DEFAULT_MIN_PX_PER_CD = 8

/**
 * 패턴 span과 여유 마진을 담기 위해 필요한 FOV(nm).
 *
 * 패턴은 화면 가운데에 놓이고 각 변에 marginRatio만큼 빈 공간이 필요하므로,
 * 패턴이 차지하는 비율은 (1 − 2r)이다. 마진 10%면 패턴은 FOV의 80%.
 *
 * 이 값은 렌더링용이 아니라 **배율 선택을 구속하는 값**이다. 마진을 빼면
 * 패턴이 화면 끝에 붙는 배율이 추천된다.
 */
export const requiredFovNm = (
  patternCount: number,
  pitchNm: number,
  marginRatio: number
): number | null => {
  if (!isPositive(patternCount) || !isPositive(pitchNm)) return null
  if (typeof marginRatio !== 'number' || !Number.isFinite(marginRatio)) return null
  if (marginRatio < 0 || marginRatio >= 0.5) return null
  return (patternCount * pitchNm) / (1 - 2 * marginRatio)
}

export type CellVerdict = 'ok' | 'under-pixel' | 'over-fov'

/** 표의 한 칸 판정. FOV 실패와 픽셀 실패는 원인이 달라 구분해서 표시한다. */
export const cellVerdict = (
  mag: number,
  pixels: number,
  cdNm: number,
  requiredFov: number,
  minPxPerCd: number
): CellVerdict | null => {
  const fov = fovNm(mag)
  if (fov === null) return null
  if (fov < requiredFov) return 'over-fov'
  const ratio = pxPerCd(mag, pixels, cdNm)
  if (ratio === null) return null
  return ratio >= minPxPerCd ? 'ok' : 'under-pixel'
}

export interface CalcInput {
  series: MagSeries
  cdNm: number
  /** null이면 CD × 2 (bar:space 1:1)로 가정한다. */
  pitchNm: number | null
  patternCount: number
  marginRatio: number
  minPxPerCd: number
}

export interface Recommendation {
  requiredFovNm: number
  effectivePitchNm: number
  /** true면 pitch를 CD × 2로 가정했다 — 화면에 밝힌다. */
  pitchAssumed: boolean
  mag: number | null
  pixels: number | null
  nmPerPx: number | null
  pxPerCd: number | null
  scanFactor: number | null
  reason: 'ok' | 'no-mag' | 'no-pixels'
}

/**
 * 배율은 높을수록 FOV가 좁아 px/CD가 커지므로, 패턴이 들어오는 한도 안에서
 * **가장 높은 배율**이 해상도상 최적이다. 픽셀 수는 기준만 넘으면 더 키울
 * 이유가 없고 스캔 시간만 제곱으로 늘어나므로 **가장 작은 값**을 고른다.
 */
export const recommend = (calc: CalcInput): Recommendation | null => {
  const { series, cdNm, patternCount, marginRatio, minPxPerCd } = calc
  if (!isPositive(cdNm) || !isPositive(minPxPerCd)) return null

  const pitchAssumed = calc.pitchNm === null
  const effectivePitchNm = pitchAssumed ? cdNm * 2 : calc.pitchNm
  if (!isPositive(effectivePitchNm) || effectivePitchNm <= cdNm) return null

  const required = requiredFovNm(patternCount, effectivePitchNm, marginRatio)
  if (required === null) return null

  const base = { requiredFovNm: required, effectivePitchNm, pitchAssumed }
  const empty = { nmPerPx: null, pxPerCd: null, scanFactor: null }

  const fitting = magRange(series).filter(mag => {
    const fov = fovNm(mag)
    return fov !== null && fov >= required
  })
  if (fitting.length === 0) {
    return { ...base, ...empty, mag: null, pixels: null, reason: 'no-mag' }
  }

  const mag = Math.max(...fitting)
  const pixels = PIXEL_SETTINGS.find(p => {
    const ratio = pxPerCd(mag, p, cdNm)
    return ratio !== null && ratio >= minPxPerCd
  })
  if (pixels === undefined) {
    return { ...base, ...empty, mag, pixels: null, reason: 'no-pixels' }
  }

  return {
    ...base,
    mag,
    pixels,
    nmPerPx: pixelSizeNm(mag, pixels),
    pxPerCd: pxPerCd(mag, pixels, cdNm),
    scanFactor: scanTimeFactor(pixels),
    reason: 'ok'
  }
}

export interface MarginSensitivityRow {
  marginRatio: number
  requiredFovNm: number | null
  mag: number | null
}

/**
 * 마진 프리셋별 결과. 배율이 이산값이라 마진이 연속적으로 반응하지 않는다 —
 * 5%와 10%가 같은 배율로 떨어지는 구간이 있다. 지금 마진에 여유가 얼마나
 * 남았는지 보여주는 것이 목적이다.
 */
export const marginSensitivity = (calc: CalcInput): MarginSensitivityRow[] =>
  MARGIN_PRESETS.map((marginRatio) => {
    const rec = recommend({ ...calc, marginRatio })
    return {
      marginRatio,
      requiredFovNm: rec?.requiredFovNm ?? null,
      mag: rec?.mag ?? null
    }
  })

export interface PixelGuidance {
  tone: 'ok' | 'warn' | 'error'
  headline: string
  detail: string
}

/**
 * 실사용은 512·1024 둘뿐이고 그 사이가 스캔 시간 4배 차이다. 이 화면이 실제로
 * 답하는 질문은 "512로 되나, 1024로 올려야 하나"이므로 결론과 근거를 함께 낸다.
 */
export const pixelGuidance = (rec: Recommendation, minPxPerCd: number): PixelGuidance => {
  if (rec.reason === 'no-mag') {
    return {
      tone: 'error',
      headline: '성립하는 배율이 없습니다',
      detail: `최저 배율에서도 필요 FOV ${Math.round(rec.requiredFovNm).toLocaleString()} nm를 담을 수 없습니다. 패턴 수나 여유 마진을 줄이세요.`
    }
  }
  if (rec.reason === 'no-pixels') {
    return {
      tone: 'error',
      headline: '픽셀이 부족합니다',
      detail: `${(rec.mag ?? 0).toLocaleString()}× 에서는 4096 px로도 기준 ${minPxPerCd} px/CD에 미달합니다. 패턴 수를 줄이거나 기준을 재검토하세요.`
    }
  }
  const ratio = rec.pxPerCd ?? 0
  if (rec.pixels === 512) {
    return {
      tone: 'ok',
      headline: '512로 충분합니다',
      detail: `${ratio.toFixed(1)} px/CD로 기준 ${minPxPerCd}의 ${(ratio / minPxPerCd).toFixed(1)}배입니다. 1024로 올리면 스캔 시간만 4배가 됩니다.`
    }
  }
  return {
    tone: 'warn',
    headline: `${rec.pixels} px가 필요합니다`,
    detail: `512로는 기준 ${minPxPerCd} px/CD에 미달합니다. 스캔 시간 ×${rec.scanFactor ?? '—'}를 감수해야 합니다.`
  }
}
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `npm --prefix front-dev-home test 2>&1 | tail -25`
Expected: PASS — 특히 `margin changes the recommended magnification` 통과

- [ ] **Step 5: 커밋**

```bash
git add front-dev-home/app/utils/magPixel.ts front-dev-home/app/utils/magPixel.test.ts
git commit -m "feat(mag-pixel): recommend a mag/pixel pair from a target CD

Inverts the calculation: target CD and pitch -> required FOV -> the highest
magnification that still frames the pattern, then the smallest pixel count
that clears the px/CD threshold.

The margin is in the arithmetic, not the drawing. Patterns sit centred with
~10% empty on each side, so required FOV = span / (1 - 2*margin). For 8
patterns at 90nm that is 900nm, not 720nm, and the answer moves from 180K to
150K -- 180K would have put the pattern flush against the frame edge. A
regression test pins both values against the same input.

Scan time is quadratic in pixel count (512=x1, 1024=x4), and only 512/1024
see real use, so pixelGuidance() states plainly whether 512 suffices and what
stepping up would cost. The px/CD threshold defaults to 8 but stays a
parameter -- no internal standard exists yet."
```

---

### Task 4: 갤러리 파생값과 이미지 뷰어 캘리브레이션

**Files:**

- Modify: `front-dev-home/app/utils/skewvoirAnalysis/gallery.ts` (엔트리 생성부, 현재 236-240행 부근)
- Modify: `front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue` (309-319행, `meta` computed)
- Test: `front-dev-home/app/utils/skewvoirAnalysis/gallery.test.ts` (append)

**Interfaces:**

- Consumes: Task 1의 `pixelSizeNm`, `parsePixelSetting`
- Produces: 갤러리 엔트리에 `nmPerPx: number | null` 필드

> **주의 — 스케일 바 기하는 건드리지 말 것.** 스케일 바는 고정 64 CSS px이고 이미지는 `ZoomableImage`로 확대/축소된다. 막대 길이 자체를 "N nm"라고 주장하면 줌 배율마다 거짓이 된다. nm/px는 줌과 무관한 취득 속성이므로 **문구와 메타 레일에만** 넣고, 막대의 `w-16`과 `scaleLabel`은 그대로 둔다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-dev-home/app/utils/skewvoirAnalysis/gallery.test.ts` 맨 아래에 덧붙인다. 파일 상단의 기존 행 팩토리(`meas_condition_mag: 250030`, `meas_condition_pixel: '512,512'`를 쓰는 것)를 그대로 재사용한다.

```ts
test('gallery entries carry a derived nm-per-pixel', () => {
  const [entry] = buildGallery(/* 기존 테스트가 쓰는 인자 그대로 */).entries
  // 250030x with 512px: FOV 135000000/250030 = 539.9352nm, / 512
  assert.notEqual(entry!.nmPerPx, null)
  assert.ok(Math.abs(entry!.nmPerPx! - 1.0545609) < 1e-6)
})

test('an empty row derives no scale rather than Infinity', () => {
  // mock writes mag 0 / pixel "0,0" on empty rows
  const [entry] = buildGallery(/* mag 0, pixel '0,0'인 행으로 */).entries
  assert.equal(entry!.nmPerPx, null)
})
```

> 기존 `gallery.test.ts`가 `buildGallery`를 어떤 이름·시그니처로 부르는지 먼저 읽고, 위 두 테스트를 그 호출 형태에 맞춰 적는다. 새 헬퍼를 만들지 말고 파일에 이미 있는 행 팩토리를 쓴다.

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `npm --prefix front-dev-home test 2>&1 | grep -A5 "nm-per-pixel"`
Expected: FAIL — `nmPerPx` undefined

- [ ] **Step 3: 갤러리 엔트리에 파생 필드를 넣는다**

`gallery.ts` 상단 import에 추가한다.

```ts
import { parsePixelSetting, pixelSizeNm } from '~/utils/magPixel'
```

엔트리를 만들어 반환하는 객체 리터럴(현재 `mag: r.meas_condition_mag,` 가 있는 곳)에서 `vac` 다음에 한 줄 덧붙인다.

```ts
      mag: r.meas_condition_mag,
      pixel: r.meas_condition_pixel,
      vac: r.meas_condition_vac,
      // FOV는 폭이므로 가로 픽셀 수(x)를 쓴다. 빈 row(mag 0 / "0,0")는 null.
      nmPerPx: pixelSizeNm(
        r.meas_condition_mag,
        parsePixelSetting(r.meas_condition_pixel)?.x ?? 0
      )
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `npm --prefix front-dev-home test 2>&1 | tail -20`
Expected: PASS

- [ ] **Step 5: 이미지 뷰어의 낡은 주석과 문구를 고친다**

`ImageViewer.vue`의 309-319행을 통째로 아래로 교체한다. 기존 주석은 "FOV가 없어서 캘리브레이션을 유도할 수 없다"고 적혀 있는데, 이제 배율에서 유도된다.

```ts
// Physical scale bar. The image RESOLUTION comes from meas_condition_pixel and
// the FIELD OF VIEW is derived from meas_condition_mag (FOV = 135000/Mag, see
// utils/magPixel.ts), so a real nm/pixel calibration is now available.
//
// The bar itself stays a pixel ruler on purpose: it is a fixed 64 CSS px while
// the image sits inside ZoomableImage, so claiming the BAR spans N nm would be
// wrong at every zoom level but one. nm/px is a property of the acquisition,
// not of the display, so it goes in the note and the metadata rail instead.
const pixelDims = computed(() => entry.value?.pixel ?? '')
const scaleLabel = computed(() => {
  const w = Number(pixelDims.value.split(',')[0])
  return Number.isFinite(w) && w > 0 ? `${Math.round(w / 8)} px` : '— px'
})
const scaleNote = computed(() => {
  const nmPerPx = entry.value?.nmPerPx
  const res = `해상도 ${pixelDims.value || '—'}`
  return nmPerPx != null ? `${res} · ${nmPerPx.toFixed(3)} nm/px` : `${res} · 배율 정보 없음`
})
```

- [ ] **Step 6: 메타 레일에 픽셀 크기를 넣는다**

같은 파일 `meta` computed에서 `배율` 줄 바로 다음에 한 줄 덧붙인다.

```ts
  items.push({ k: '배율', v: e.mag ? `${e.mag.toLocaleString()}x` : '—' })
  items.push({ k: '픽셀 크기', v: e.nmPerPx != null ? `${e.nmPerPx.toFixed(3)} nm/px` : '—' })
  items.push({ k: '진공', v: e.vac ? String(e.vac) : '—' })
```

- [ ] **Step 7: 타입체크와 린트**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -10`
Expected: 오류 없음

Run: `npm --prefix front-dev-home test 2>&1 | tail -5`
Expected: 전체 PASS

- [ ] **Step 8: 커밋**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/gallery.ts \
        front-dev-home/app/utils/skewvoirAnalysis/gallery.test.ts \
        front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue
git commit -m "feat(skewvoir): calibrate the gallery scale bar in nanometres

The viewer carried a comment saying a true nm/pixel calibration 'cannot be
derived' because Phase-1 metadata has resolution but no field of view, and it
showed '물리 보정 미제공' to the user. That premise was never a data limit --
FOV follows from meas_condition_mag, which was on the row all along. The note
now carries the real figure.

The bar stays a pixel ruler deliberately. It is a fixed 64 CSS px inside a
ZoomableImage, so stating the BAR spans N nm would be false at every zoom
level but one. nm/px belongs to the acquisition, not the display.

Empty rows (mag 0, pixel \"0,0\") derive null and render '—' rather than
Infinity."
```

---

### Task 5: `/mag-pixel` 페이지 셸과 통합 테이블

**Files:**

- Create: `front-dev-home/app/pages/mag-pixel.vue`
- Create: `front-dev-home/app/components/magpixel/ResultTable.vue`
- Modify: `front-dev-home/app/components/nav/AppHeader.vue` (`/endpoints` 버튼 다음)
- Modify: `front-dev-home/app/components/nav/FeatureTabs.vue:11` (`INFO_PATHS`)

**Interfaces:**

- Consumes: Task 1·2·3 전체
- Produces: `magPixelInput` 상태 형태 — `ResultTable`은 `props: { rows: MagPixelRow[], showWide: boolean, requiredFovNm: number | null, cdNm: number, minPxPerCd: number, recommendedMag: number | null, recommendedPixels: number | null }`

- [ ] **Step 1: 헤더 진입 버튼을 넣는다**

`AppHeader.vue`에서 `/endpoints` `UButton` 블록 바로 다음에 넣는다.

```vue
      <UButton
        to="/mag-pixel"
        icon="i-lucide-ruler"
        color="neutral"
        variant="ghost"
        aria-label="Mag/Pixel 가이드"
        :aria-current="isActivePath('/mag-pixel') ? 'page' : undefined"
        :class="headerActionClass('/mag-pixel')"
      />
```

- [ ] **Step 2: 정보 페이지 계층에 등록한다**

`FeatureTabs.vue:11`을 바꾼다. 이래야 이 페이지에서도 feature 탭이 유지되어 원래 보던 화면으로 돌아갈 수 있다.

```ts
const INFO_PATHS = ['/intro', '/endpoints', '/activity', '/settings', '/mag-pixel']
```

- [ ] **Step 3: 통합 테이블 컴포넌트를 만든다**

`front-dev-home/app/components/magpixel/ResultTable.vue`를 새로 만든다.

```vue
<script setup lang="ts">
import { cellVerdict, type MagPixelRow } from '~/utils/magPixel'

const props = defineProps<{
  rows: MagPixelRow[]
  /** 2048·4096까지 보여줄지. 실사용은 512·1024가 대부분이다. */
  showWide: boolean
  /** null이면 판정 없이 순수 참조표로 렌더한다. */
  requiredFovNm: number | null
  cdNm: number
  minPxPerCd: number
  recommendedMag: number | null
  recommendedPixels: number | null
}>()

const visiblePixels = computed(() => props.showWide ? [512, 1024, 2048, 4096] : [512, 1024])

const scanFactorLabel = (pixels: number) => `×${(pixels / 512) ** 2}`

const verdictOf = (mag: number, pixels: number) =>
  props.requiredFovNm === null
    ? null
    : cellVerdict(mag, pixels, props.cdNm, props.requiredFovNm, props.minPxPerCd)

const isRecommended = (mag: number, pixels: number) =>
  props.recommendedMag === mag && props.recommendedPixels === pixels

const cellClass = (mag: number, pixels: number) => {
  const v = verdictOf(mag, pixels)
  if (v === null) return 'text-(--sk-ink)'
  if (v === 'over-fov' || v === 'under-pixel') return 'text-red-600 dark:text-red-400'
  return isRecommended(mag, pixels)
    ? 'text-emerald-600 dark:text-emerald-400 font-bold'
    : 'text-emerald-600 dark:text-emerald-400'
}

/** 참조 모드는 nm/px, 판정 모드는 px/CD를 보여준다. */
const cellText = (row: MagPixelRow, pixels: number) => {
  const cell = row.cells.find(c => c.pixels === pixels)
  if (!cell) return '—'
  if (props.requiredFovNm === null) return cell.nmPerPx.toFixed(3)
  const v = verdictOf(row.mag, pixels)
  if (v === 'over-fov') return '✗ FOV'
  const ratio = props.cdNm / cell.nmPerPx
  return `${v === 'under-pixel' ? '✗' : isRecommended(row.mag, pixels) ? '★' : '●'} ${ratio.toFixed(1)}`
}

const magLabel = (mag: number) => mag >= 1000 ? `${mag / 1000}K` : String(mag)
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full border-collapse font-mono text-[12px]">
      <thead>
        <tr class="text-[10px] tracking-wide text-(--sk-ink-muted)">
          <th class="border-b border-(--sk-border) px-2 py-1.5 text-left">
            MAG
          </th>
          <th class="border-b border-(--sk-border) px-2 py-1.5 text-right">
            FOV(nm)
          </th>
          <th
            v-for="p in visiblePixels"
            :key="p"
            class="border-b border-(--sk-border) px-2 py-1.5 text-center"
          >
            {{ p }} <span class="opacity-60">{{ scanFactorLabel(p) }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.mag"
          :class="recommendedMag === row.mag ? 'bg-emerald-500/10' : undefined"
        >
          <td class="px-2 py-1">
            {{ magLabel(row.mag) }}
            <span
              v-if="row.assumed"
              class="ml-1 rounded px-1 text-[9px] text-amber-600 ring-1 ring-amber-500/40 dark:text-amber-400"
            >가정</span>
          </td>
          <td class="px-2 py-1 text-right">
            {{ Math.round(row.fovNm).toLocaleString() }}
          </td>
          <td
            v-for="p in visiblePixels"
            :key="p"
            class="px-2 py-1 text-center"
            :class="cellClass(row.mag, p)"
          >
            {{ cellText(row, p) }}
          </td>
        </tr>
      </tbody>
    </table>

    <p class="mt-3 font-mono text-[10.5px] leading-relaxed text-(--sk-ink-muted)">
      <template v-if="requiredFovNm === null">
        셀 값 = 픽셀당 길이(nm/px) · 헤더 ×N = 512 대비 상대 스캔 시간
      </template>
      <template v-else>
        셀 값 = px/CD · ● 기준 통과 · ✗ 픽셀 부족 · ✗ FOV 패턴 미수용 · ★ 추천<br>
        헤더 ×N = 512 대비 상대 스캔 시간 (픽셀 총량 X×Y 비례)
      </template>
    </p>
  </div>
</template>
```

- [ ] **Step 4: 페이지를 만든다**

`front-dev-home/app/pages/mag-pixel.vue`를 새로 만든다.

```vue
<script setup lang="ts">
import {
  buildMagPixelTable, recommend, MARGIN_PRESETS, DEFAULT_MARGIN,
  DEFAULT_MIN_PX_PER_CD, DEFAULT_PATTERN_COUNT, type MagSeries
} from '~/utils/magPixel'

useHead({ title: 'Mag/Pixel 가이드 | SKEWNONO' })

const series = ref<MagSeries>('CG')
const cdNm = ref<number | null>(null)
const pitchNm = ref<number | null>(null)
const patternCount = ref(DEFAULT_PATTERN_COUNT)
const marginRatio = ref<number>(DEFAULT_MARGIN)
const minPxPerCd = ref(DEFAULT_MIN_PX_PER_CD)
const showWide = ref(false)

const rows = computed(() => buildMagPixelTable(series.value))

/** CD가 없으면 판정하지 않고 순수 참조표로 둔다. */
const pitchError = computed(() =>
  cdNm.value != null && pitchNm.value != null && pitchNm.value <= cdNm.value
    ? 'Pitch는 CD보다 커야 합니다.'
    : null
)

const result = computed(() => {
  if (cdNm.value == null || cdNm.value <= 0 || pitchError.value) return null
  return recommend({
    series: series.value,
    cdNm: cdNm.value,
    pitchNm: pitchNm.value,
    patternCount: patternCount.value,
    marginRatio: marginRatio.value,
    minPxPerCd: minPxPerCd.value
  })
})

const marginLabel = (r: number) => `${Math.round(r * 100)}%`
</script>

<template>
  <div class="mx-auto flex max-w-6xl flex-col gap-5 p-5">
    <header>
      <h1 class="sk-title text-lg">
        CD-SEM Mag / Pixel 가이드
      </h1>
      <p class="mt-1 text-sm text-(--sk-ink-muted)">
        목표 패턴 크기에서 적정 배율과 픽셀 수를 역산합니다. FOV = 135,000 µm ÷ Mag.
      </p>
    </header>

    <!-- 입력 -->
    <section class="flex flex-wrap items-end gap-3 rounded-(--sk-r-sidebar) border border-(--sk-border) p-4">
      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          SERIES
        </div>
        <UButtonGroup size="xs">
          <UButton
            v-for="s in (['CG', 'GT'] as MagSeries[])"
            :key="s"
            :label="s"
            :color="series === s ? 'primary' : 'neutral'"
            :variant="series === s ? 'solid' : 'outline'"
            @click="series = s"
          />
        </UButtonGroup>
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          CD (nm)
        </div>
        <UInput
          v-model.number="cdNm"
          type="number"
          size="xs"
          placeholder="40"
          class="w-24"
        />
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          PITCH (nm) · 선택
        </div>
        <UInput
          v-model.number="pitchNm"
          type="number"
          size="xs"
          placeholder="CD × 2"
          class="w-28"
        />
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          패턴 수
        </div>
        <UInput
          v-model.number="patternCount"
          type="number"
          size="xs"
          class="w-20"
        />
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-primary">
          여유 마진 (각 변)
        </div>
        <UButtonGroup size="xs">
          <UButton
            v-for="m in MARGIN_PRESETS"
            :key="m"
            :label="marginLabel(m)"
            :color="marginRatio === m ? 'primary' : 'neutral'"
            :variant="marginRatio === m ? 'solid' : 'outline'"
            @click="marginRatio = m"
          />
        </UButtonGroup>
      </div>

      <div>
        <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          기준 px/CD <span class="text-amber-500">·잠정</span>
        </div>
        <UInput
          v-model.number="minPxPerCd"
          type="number"
          size="xs"
          class="w-20"
        />
      </div>
    </section>

    <p
      v-if="pitchError"
      class="rounded-(--sk-r-sidebar) bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400"
    >
      {{ pitchError }}
    </p>

    <p
      v-else-if="result?.pitchAssumed"
      class="font-mono text-[11px] text-(--sk-ink-muted)"
    >
      Pitch를 비워서 CD × 2 = {{ result.effectivePitchNm }} nm로 가정했습니다 ·
      기준 px/CD는 사내 기준 확정 전까지 잠정값입니다
    </p>

    <!-- 테이블 -->
    <section class="rounded-(--sk-r-sidebar) border border-(--sk-border) p-4">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
          {{ series }} SERIES · MAG × PIXEL
        </h2>
        <USwitch
          v-model="showWide"
          size="xs"
          label="2048 · 4096 표시"
        />
      </div>
      <MagpixelResultTable
        :rows="rows"
        :show-wide="showWide"
        :required-fov-nm="result?.requiredFovNm ?? null"
        :cd-nm="cdNm ?? 0"
        :min-px-per-cd="minPxPerCd"
        :recommended-mag="result?.mag ?? null"
        :recommended-pixels="result?.pixels ?? null"
      />
    </section>
  </div>
</template>
```

- [ ] **Step 5: 페이지가 뜨는지 확인한다**

Run: `npm --prefix front-dev-home run dev`
브라우저에서 `http://localhost:3000/mag-pixel`을 연다.

Expected:
- 헤더 우측에 자 모양 아이콘이 보이고 클릭하면 이동한다
- CD를 비워두면 표에 nm/px가 뜨고 판정색이 없다
- CD `40`, Pitch `90`을 넣으면 150K 행이 강조되고 512 칸이 `★ 22.8`이 된다
- 마진을 0%로 바꾸면 강조가 180K로 옮겨간다
- `2048 · 4096 표시` 스위치를 켜면 컬럼 2개가 늘어난다
- GT로 바꾸면 행이 28개가 되고 600K 이상에 `가정` 배지가 붙는다

- [ ] **Step 6: 린트**

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -10`
Expected: 오류 없음

- [ ] **Step 7: 커밋**

```bash
git add front-dev-home/app/pages/mag-pixel.vue \
        front-dev-home/app/components/magpixel/ResultTable.vue \
        front-dev-home/app/components/nav/AppHeader.vue \
        front-dev-home/app/components/nav/FeatureTabs.vue
git commit -m "feat(mag-pixel): add the /mag-pixel reference and setup page

Lands in the header-right info tier next to /endpoints -- the table is fab-,
tool- and period-independent, so it does not belong behind a [fab] route, and
it makes no API calls.

One table serves both modes rather than two. With no CD entered it is a plain
reference table of nm/px; entering a target overlays px/CD verdicts and the
recommended cell on the same grid. Splitting them would render the same
numbers twice and leave the user guessing how they differ.

2048 and 4096 are behind a toggle: real use is 512/1024, and the header keeps
the scan-time multiplier visible so the cost of stepping up is never hidden."
```

---

### Task 6: 모식도·시뮬레이션·추천 패널

**Files:**

- Create: `front-dev-home/app/components/magpixel/PatternSchematic.vue`
- Create: `front-dev-home/app/components/magpixel/SemSimulation.vue`
- Create: `front-dev-home/app/components/magpixel/RecommendationPanel.vue`
- Modify: `front-dev-home/app/pages/mag-pixel.vue` (테이블 섹션 위에 삽입)

**Interfaces:**

- Consumes: Task 3의 `Recommendation`, `marginSensitivity`, `pixelGuidance`, `MARGIN_PRESETS`
- Produces: 없음 (최종 태스크)

- [ ] **Step 1: 모식도 컴포넌트를 만든다**

`front-dev-home/app/components/magpixel/PatternSchematic.vue`를 새로 만든다.

```vue
<script setup lang="ts">
// 두 제약을 각각 담당하는 2단 구성이다.
//   ① 전체 FOV      — 패턴 N개 + 마진이 들어오는가 (FOV 제약)
//   ② Pitch 1개 확대 — CD에 픽셀이 몇 개 얹히는가 (픽셀 제약)
const props = defineProps<{
  cdNm: number
  pitchNm: number
  patternCount: number
  marginRatio: number
  fovNm: number
  nmPerPx: number
}>()

/** 패턴 밴드가 FOV에서 차지하는 비율. 나머지는 좌우 마진으로 나뉜다. */
const bandPct = computed(() => (1 - 2 * props.marginRatio) * 100)
const marginPct = computed(() => props.marginRatio * 100)
const marginNm = computed(() => Math.round(props.fovNm * props.marginRatio))
const spanNm = computed(() => Math.round(props.patternCount * props.pitchNm))

const barPct = computed(() => (props.cdNm / props.pitchNm) * 100)
const spacePct = computed(() => 100 - barPct.value)

/** 확대 뷰에서 pitch 하나에 걸치는 픽셀 수. */
const pxPerPitch = computed(() => props.pitchNm / props.nmPerPx)
const pxStepPct = computed(() => 100 / pxPerPitch.value)
const pxPerCdValue = computed(() => props.cdNm / props.nmPerPx)

const patterns = computed(() => Array.from({ length: props.patternCount }, (_, i) => i))
const unitPct = computed(() => 100 / props.patternCount)
const hatch = 'repeating-linear-gradient(45deg,rgba(99,102,241,.18) 0 4px,transparent 4px 8px)'
const barFill = 'linear-gradient(90deg,#e8eef7,#9aa8bd 55%,#e8eef7)'
</script>

<template>
  <div>
    <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
      ① 전체 FOV {{ Math.round(fovNm).toLocaleString() }} nm — 패턴 {{ patternCount }}개 · 마진 {{ marginNm }} nm
    </div>
    <div class="flex h-14 overflow-hidden rounded bg-slate-900">
      <div
        :style="{ width: `${marginPct}%`, background: hatch }"
        class="border-r border-dashed border-indigo-400/70"
      />
      <div
        class="flex"
        :style="{ width: `${bandPct}%` }"
      >
        <div
          v-for="i in patterns"
          :key="i"
          class="flex"
          :style="{ width: `${unitPct}%` }"
        >
          <div :style="{ width: `${barPct}%`, background: barFill }" />
          <div :style="{ width: `${spacePct}%` }" />
        </div>
      </div>
      <div
        :style="{ width: `${marginPct}%`, background: hatch }"
        class="border-l border-dashed border-indigo-400/70"
      />
    </div>
    <div class="mt-1.5 flex font-mono text-[10px]">
      <div
        class="text-center text-indigo-400"
        :style="{ width: `${marginPct}%` }"
      >
        {{ marginNm }}
      </div>
      <div
        class="text-center text-(--sk-ink-muted)"
        :style="{ width: `${bandPct}%` }"
      >
        패턴 {{ spanNm.toLocaleString() }} nm
      </div>
      <div
        class="text-center text-indigo-400"
        :style="{ width: `${marginPct}%` }"
      >
        {{ marginNm }}
      </div>
    </div>

    <div class="mb-1.5 mt-4 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
      ② Pitch {{ pitchNm }} nm 확대 — 픽셀 경계 {{ pxPerPitch.toFixed(1) }} px
    </div>
    <div class="relative h-16 overflow-hidden rounded bg-slate-900">
      <div class="absolute inset-0 flex">
        <div :style="{ width: `${barPct}%`, background: barFill }" />
        <div :style="{ width: `${spacePct}%` }" />
      </div>
      <div
        class="absolute inset-0"
        :style="{ background: `repeating-linear-gradient(90deg,rgba(239,68,68,.8) 0 1px,transparent 1px ${pxStepPct}%)` }"
      />
      <div
        class="absolute inset-y-0 left-0 border-r border-dashed border-indigo-400"
        :style="{ width: `${barPct}%` }"
      />
    </div>
    <div class="mt-1.5 flex font-mono text-[11px]">
      <div
        class="text-center text-indigo-400"
        :style="{ width: `${barPct}%` }"
      >
        CD {{ cdNm }} · <strong>{{ pxPerCdValue.toFixed(1) }} px</strong>
      </div>
      <div
        class="text-center text-(--sk-ink-muted)"
        :style="{ width: `${spacePct}%` }"
      >
        space {{ (pitchNm - cdNm).toFixed(0) }} nm
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 시뮬레이션 컴포넌트를 만든다**

`front-dev-home/app/components/magpixel/SemSimulation.vue`를 새로 만든다. 모식도 ①이 가로만 보여주는 데 비해, 여기는 **상하좌우 네 변** 마진을 그려 실제 촬영 구도를 보여준다.

```vue
<script setup lang="ts">
const props = defineProps<{
  cdNm: number
  pitchNm: number
  patternCount: number
  marginRatio: number
  pixels: number
  nmPerPx: number
}>()

const insetPct = computed(() => props.marginRatio * 100)
const bandPct = computed(() => (1 - 2 * props.marginRatio) * 100)
const unitPct = computed(() => 100 / props.patternCount)
const barPct = computed(() => (props.cdNm / props.pitchNm) * 100)
const spacePct = computed(() => 100 - barPct.value)
const patterns = computed(() => Array.from({ length: props.patternCount }, (_, i) => i))
const pxPerCdValue = computed(() => props.cdNm / props.nmPerPx)
const hatch = 'repeating-linear-gradient(45deg,rgba(99,102,241,.14) 0 4px,transparent 4px 8px)'
const barFill = 'linear-gradient(90deg,#f2f6fc,#93a3ba 55%,#f2f6fc)'
</script>

<template>
  <div class="flex flex-wrap items-start gap-4">
    <div>
      <div class="mb-1.5 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        {{ pixels }} px · {{ nmPerPx.toFixed(3) }} nm/px
      </div>
      <div class="relative h-52 w-52 overflow-hidden rounded bg-slate-950">
        <div
          class="absolute flex"
          :style="{ left: `${insetPct}%`, top: `${insetPct}%`, width: `${bandPct}%`, height: `${bandPct}%` }"
        >
          <div
            v-for="i in patterns"
            :key="i"
            class="flex h-full"
            :style="{ width: `${unitPct}%` }"
          >
            <div :style="{ width: `${barPct}%`, background: barFill }" />
            <div :style="{ width: `${spacePct}%` }" />
          </div>
        </div>
        <div
          class="absolute border border-dashed border-indigo-400/70"
          :style="{ left: `${insetPct}%`, top: `${insetPct}%`, width: `${bandPct}%`, height: `${bandPct}%` }"
        />
        <div
          class="absolute inset-x-0 top-0"
          :style="{ height: `${insetPct}%`, background: hatch }"
        />
        <div
          class="absolute inset-x-0 bottom-0"
          :style="{ height: `${insetPct}%`, background: hatch }"
        />
        <div
          class="absolute left-0"
          :style="{ top: `${insetPct}%`, height: `${bandPct}%`, width: `${insetPct}%`, background: hatch }"
        />
        <div
          class="absolute right-0"
          :style="{ top: `${insetPct}%`, height: `${bandPct}%`, width: `${insetPct}%`, background: hatch }"
        />
      </div>
      <div class="mt-1.5 font-mono text-[10px] text-indigo-400">
        빗금 = 여유 마진 (상하좌우 각 {{ Math.round(marginRatio * 100) }}%)
      </div>
    </div>

    <dl class="min-w-40 flex-1 font-mono text-[11.5px] leading-relaxed">
      <div class="flex justify-between">
        <dt class="text-(--sk-ink-muted)">
          픽셀 크기
        </dt>
        <dd>{{ nmPerPx.toFixed(3) }} nm</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-(--sk-ink-muted)">
          CD당 픽셀
        </dt>
        <dd>{{ pxPerCdValue.toFixed(1) }}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-(--sk-ink-muted)">
          스캔 시간
        </dt>
        <dd>×{{ (pixels / 512) ** 2 }}</dd>
      </div>
    </dl>
  </div>
</template>
```

- [ ] **Step 3: 추천 패널을 만든다**

`front-dev-home/app/components/magpixel/RecommendationPanel.vue`를 새로 만든다.

```vue
<script setup lang="ts">
import { fovNm, marginSensitivity, pixelGuidance, type CalcInput, type Recommendation } from '~/utils/magPixel'

const props = defineProps<{
  rec: Recommendation
  calc: CalcInput
}>()

const guidance = computed(() => pixelGuidance(props.rec, props.calc.minPxPerCd))
const sensitivity = computed(() => marginSensitivity(props.calc))
/** FOV는 fovNm()으로만 구한다 — 135000 상수를 컴포넌트에 복제하지 않는다. */
const recFovNm = computed(() => props.rec.mag === null ? null : fovNm(props.rec.mag))

const toneClass = computed(() => ({
  ok: 'bg-emerald-500/10 border-emerald-500',
  warn: 'bg-amber-500/10 border-amber-500',
  error: 'bg-red-500/10 border-red-500'
}[guidance.value.tone]))

const magLabel = (mag: number | null) => mag === null ? '—' : `${mag / 1000}K`
</script>

<template>
  <div class="flex flex-wrap gap-4">
    <div class="min-w-52 flex-1 rounded-(--sk-r-sidebar) border-2 p-4" :class="toneClass">
      <div class="mb-2 font-mono text-[10px] tracking-wide">
        ★ 추천 조합
      </div>
      <div class="font-mono text-2xl font-bold">
        {{ magLabel(rec.mag) }}
      </div>
      <div class="mb-3 font-mono text-[15px] font-bold opacity-80">
        {{ rec.pixels ?? '—' }} px
      </div>
      <dl class="font-mono text-[11.5px] leading-relaxed">
        <div class="flex justify-between">
          <dt>FOV</dt>
          <dd>{{ recFovNm !== null ? Math.round(recFovNm).toLocaleString() : '—' }} nm</dd>
        </div>
        <div class="flex justify-between opacity-60">
          <dt>필요</dt>
          <dd>{{ Math.round(rec.requiredFovNm).toLocaleString() }} nm</dd>
        </div>
        <div class="flex justify-between">
          <dt>nm/px</dt>
          <dd>{{ rec.nmPerPx?.toFixed(3) ?? '—' }}</dd>
        </div>
        <div class="flex justify-between font-semibold">
          <dt>px/CD</dt>
          <dd>{{ rec.pxPerCd?.toFixed(1) ?? '—' }}</dd>
        </div>
        <div class="mt-1 flex justify-between border-t border-(--sk-border) pt-1.5 font-semibold">
          <dt>스캔 시간</dt>
          <dd>×{{ rec.scanFactor ?? '—' }}</dd>
        </div>
      </dl>
      <div class="mt-3 rounded p-2 text-[11px] leading-relaxed" :class="toneClass">
        <strong>{{ guidance.headline }}</strong><br>
        {{ guidance.detail }}
      </div>
    </div>

    <div class="min-w-52 flex-1 rounded-(--sk-r-sidebar) border border-(--sk-border) p-4">
      <div class="mb-2 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        마진 민감도
      </div>
      <p class="mb-2 text-[11px] leading-relaxed text-(--sk-ink-muted)">
        배율이 이산값이라 마진이 연속적으로 반응하지 않습니다. 지금 마진에 여유가 얼마나 남았는지 보세요.
      </p>
      <table class="w-full font-mono text-[11.5px]">
        <tbody>
          <tr
            v-for="row in sensitivity"
            :key="row.marginRatio"
            :class="row.marginRatio === calc.marginRatio ? 'font-bold text-emerald-600 dark:text-emerald-400' : 'text-(--sk-ink-muted)'"
          >
            <td class="py-0.5">
              {{ Math.round(row.marginRatio * 100) }}%
            </td>
            <td class="py-0.5 text-right">
              {{ row.requiredFovNm ? Math.round(row.requiredFovNm).toLocaleString() : '—' }} nm
            </td>
            <td class="py-0.5 text-right">
              {{ magLabel(row.mag) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
```

- [ ] **Step 4: 페이지에 끼워 넣는다**

`mag-pixel.vue`의 import 문에 `fovNm`을 추가한다. 템플릿에서 FOV를 직접 계산하지 않고 이 함수를 쓴다 — 135,000 상수를 컴포넌트에 복제하지 않는다.

```ts
import {
  buildMagPixelTable, fovNm, recommend, MARGIN_PRESETS, DEFAULT_MARGIN,
  DEFAULT_MIN_PX_PER_CD, DEFAULT_PATTERN_COUNT, type MagSeries
} from '~/utils/magPixel'
```

같은 파일 `<script setup>` 끝에 계산 입력 객체와 시뮬레이션 토글을 추가한다.

```ts
const showSim = ref(false)

const calcInput = computed(() => ({
  series: series.value,
  cdNm: cdNm.value ?? 0,
  pitchNm: pitchNm.value,
  patternCount: patternCount.value,
  marginRatio: marginRatio.value,
  minPxPerCd: minPxPerCd.value
}))
```

같은 파일 템플릿에서 `<!-- 테이블 -->` 섹션 **바로 위**에 넣는다.

```vue
    <!-- 모식도 + 추천 -->
    <section
      v-if="result"
      class="flex flex-wrap items-start gap-4 rounded-(--sk-r-sidebar) border border-(--sk-border) p-4"
    >
      <div class="min-w-80 flex-1">
        <MagpixelPatternSchematic
          v-if="result.mag && result.nmPerPx"
          :cd-nm="calcInput.cdNm"
          :pitch-nm="result.effectivePitchNm"
          :pattern-count="patternCount"
          :margin-ratio="marginRatio"
          :fov-nm="fovNm(result.mag) ?? 0"
          :nm-per-px="result.nmPerPx"
        />

        <UButton
          class="mt-3"
          size="xs"
          color="neutral"
          variant="outline"
          :icon="showSim ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
          label="SEM 이미지 미리보기"
          @click="showSim = !showSim"
        />
        <div
          v-if="showSim && result.pixels && result.nmPerPx"
          class="mt-3"
        >
          <MagpixelSemSimulation
            :cd-nm="calcInput.cdNm"
            :pitch-nm="result.effectivePitchNm"
            :pattern-count="patternCount"
            :margin-ratio="marginRatio"
            :pixels="result.pixels"
            :nm-per-px="result.nmPerPx"
          />
        </div>
      </div>

      <MagpixelRecommendationPanel
        class="min-w-80 flex-1"
        :rec="result"
        :calc="calcInput"
      />
    </section>
```

- [ ] **Step 5: 화면을 확인한다**

Run: `npm --prefix front-dev-home run dev`
`http://localhost:3000/mag-pixel`에서 CD `40`, Pitch `90`, 패턴 `8`, 마진 `10%`를 넣는다.

Expected:
- 모식도 ①에 좌우 빗금 마진과 `90 / 패턴 720 nm / 90` 치수가 보인다
- 모식도 ②에 픽셀 경계선이 그려지고 `CD 40 · 22.8 px`가 뜬다
- 추천 카드가 `150K / 512 px`, `스캔 시간 ×1`, 초록 톤으로 `512로 충분합니다`를 보여준다
- 민감도 표가 `0% 720 180K / 5% 800 150K / 10% 900 150K / 15% 1,029 120K / 20% 1,200 100K`이고 10% 행이 강조된다
- `SEM 이미지 미리보기`를 펼치면 정사각 프레임에 **상하좌우 네 변** 빗금이 보인다
- 마진을 0%로 바꾸면 추천이 180K로 옮겨가고 모식도의 빗금이 사라진다

- [ ] **Step 6: 전체 검증**

Run: `npm --prefix front-dev-home test 2>&1 | tail -5`
Expected: 전체 PASS

Run: `npm --prefix front-dev-home run lint 2>&1 | tail -10`
Expected: 오류 없음

Run: `npm run lint:md 2>&1 | grep -E "cdsem-mag-pixel" || echo "md ok"`
Expected: `md ok`

- [ ] **Step 7: 커밋**

```bash
git add front-dev-home/app/components/magpixel/PatternSchematic.vue \
        front-dev-home/app/components/magpixel/SemSimulation.vue \
        front-dev-home/app/components/magpixel/RecommendationPanel.vue \
        front-dev-home/app/pages/mag-pixel.vue
git commit -m "feat(mag-pixel): draw the pattern, the pixels and the margin

The two constraints pull against each other, so the schematic splits them:
the top strip shows whether the patterns plus margin fit the field of view,
the zoomed pitch below shows how many pixels land on one CD. The SEM preview
folds out to show all four margins at once -- the framing an operator
actually sees -- and stays collapsed by default because it is tall.

The sensitivity table is always visible. Magnifications are discrete, so
margin does not move the answer smoothly: 5% and 10% both land on 150K while
15% drops to 120K. Showing the staircase tells the user how much room the
current margin still has."
```

---

## Self-Review

**1. Spec coverage**

| 스펙 요구 | 태스크 |
| --- | --- |
| 물리 모델 `FOV = 135000/Mag` | 1 |
| 원본 문서 정정 2건 (µm, 5000) | 1 |
| null 규율 · 픽셀 문자열 파싱 | 1 |
| CG/GT 범위 · 접두사 판정 · `가정` 배지 | 2 |
| 스캔 시간 `(N/512)²` | 1 (함수) · 2 (표) · 5 (헤더) |
| 여유 마진 프리셋 · 민감도 | 3 (계산) · 5 (입력) · 6 (표) |
| 추천 알고리즘 | 3 |
| 512 vs 1024 안내 4분기 | 3 (`pixelGuidance`) · 6 (렌더) |
| `/mag-pixel` · 헤더 · `INFO_PATHS` | 5 |
| 통합 테이블 2모드 · 2048/4096 토글 | 5 |
| 모식도 ①② · SEM 시뮬레이션 토글 | 6 |
| 갤러리 인라인 파생값 | 4 |
| 테스트 전 항목 | 1·2·3·4 |

누락 없음.

**2. Placeholder scan**

Task 4 Step 1의 테스트만 `buildGallery` 호출 형태를 기존 파일에서 확인하라는 지시를 남겼다. `gallery.test.ts`의 기존 팩토리 이름과 시그니처를 계획 작성 시점에 열어보지 않았으므로, 그것을 지어내는 것보다 실제 파일을 읽고 맞추라고 지시하는 편이 안전하다. 나머지 스텝은 모두 실제 코드를 담고 있다.

**3. Type consistency**

- `MagSeries`, `MagPixelRow`, `MagPixelCell`, `CalcInput`, `Recommendation`, `CellVerdict`, `PixelGuidance`, `MarginSensitivityRow`, `PixelDims` — 정의(1·2·3)와 사용(4·5·6)이 일치한다.
- `recommend()`는 `Recommendation | null`을 돌려주고, 페이지는 `result`가 null이면 판정 모드를 끈다. `ResultTable`의 `requiredFovNm: number | null`이 이 신호를 그대로 받는다.
- `pixelSizeNm(mag, pixels)` 인자 순서가 Task 1 정의와 Task 4 사용에서 동일하다.
- 컴포넌트 자동 임포트 이름(`MagpixelResultTable`, `MagpixelPatternSchematic`, `MagpixelSemSimulation`, `MagpixelRecommendationPanel`)이 `app/components/magpixel/` 경로 규칙과 일치한다.
