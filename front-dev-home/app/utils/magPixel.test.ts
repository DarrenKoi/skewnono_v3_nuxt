// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  fovUm, fovNm, parsePixelSetting, pixelSizeNm, pxPerCd, scanTimeFactor,
  seriesFromModel, magRange, buildMagPixelTable, SERIES_MODEL, magLabel,
  requiredFovNm, actualMarginNm, recommend, cellVerdict, marginSensitivity, pixelGuidance,
  MARGIN_PRESETS, DEFAULT_MARGIN, DEFAULT_MIN_PX_PER_CD,
  edgeIntensity, samplePixelNm, edgeWindowHalfNm, edgeStrip, edgeComparePair,
  SEM_EDGE_WIDTH_NM, SEM_LEVELS
} from './magPixel.ts'
import type { CalcInput } from './magPixel.ts'

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
  assert.equal(fovUm(Number.NEGATIVE_INFINITY), null)
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

test('parsePixelSetting keeps x and y distinct', () => {
  // symmetric fixtures would pass even if the parser transposed x and y;
  // FOV is a WIDTH, so callers depend on x being the first component
  assert.deepEqual(parsePixelSetting('640,480'), { x: 640, y: 480 })
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

/**
 * UI가 계열 칩에 'CG'가 아니라 'CG6300'을 찍는다. 그 레이블이 접두사 판정과
 * 어긋나면 화면은 CG6300이라 부르는데 시스템은 그 문자열을 CG로 못 읽는 상태가
 * 되므로, 레이블은 반드시 자기 계열로 되돌아와야 한다.
 */
test('SERIES_MODEL labels round-trip back through seriesFromModel', () => {
  for (const series of ['CG', 'GT'] as const) {
    assert.equal(seriesFromModel(SERIES_MODEL[series]), series)
  }
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

test('the GT tail above 500K is the confirmed 100K ladder', () => {
  // user-confirmed 2026-08-06: GT2000 really does step 600K..1000K by 100K.
  // This was once an assumption the UI badged as `가정`; the badge is gone, so
  // this test is now the only thing pinning the five values.
  assert.deepEqual(
    magRange('GT').filter(m => m > 500_000),
    [600_000, 700_000, 800_000, 900_000, 1_000_000]
  )
})

test('magLabel keeps every mag in K so one ladder has one name', () => {
  // 1M으로 접지 않는 것이 이 함수의 전부다 — GT 상단이 600K..900K로 이어지는데
  // 마지막 칸만 1M이면 캡션과 참조표가 같은 값을 다르게 부른다 (실제로 그랬다).
  assert.equal(magLabel(1_000_000), '1000K')
  assert.equal(magLabel(900_000), '900K')
  assert.equal(magLabel(450_000), '450K')
  assert.equal(magLabel(1000), '1K')
  assert.equal(magLabel(null), '—')
  // 계열 전 구간이 K 표기로 떨어진다 — 1000 미만 배율은 존재하지 않는다.
  for (const mag of magRange('GT')) assert.match(magLabel(mag), /^\d+K$/)
})

test('buildMagPixelTable emits one row per mag with all four pixel settings', () => {
  const rows = buildMagPixelTable('CG')
  assert.equal(rows.length, 23)
  const row = rows.find(r => r.mag === 180_000)
  assert.notEqual(row, undefined)
  near(row!.fovNm, 750)
  assert.equal(row!.cells.length, 4)
  assert.deepEqual(row!.cells.map(c => c.pixels), [512, 1024, 2048, 4096])
  near(row!.cells[0]!.nmPerPx, 1.46484375)
  assert.equal(row!.cells[1]!.scanFactor, 4)
})

test('buildMagPixelTable carries the GT tail through to the row data', () => {
  const rows = buildMagPixelTable('GT')
  assert.equal(rows.length, 28)
  const tail = rows.find(r => r.mag === 1_000_000)
  assert.notEqual(tail, undefined)
  near(tail!.fovNm, 135)
  assert.equal(tail!.cells.length, 4)
})

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

test('actualMarginNm derives the real margin from the chosen FOV, clamped at zero', () => {
  // 이산 배율이라 실제 FOV는 필요 FOV보다 넓다 → 실제 마진 > 요청 마진.
  assert.equal(actualMarginNm(1000, 800), 100)
  assert.equal(actualMarginNm(1000, 1000), 0)
  // span이 FOV를 넘는 성립 불가 조합에서도 음수 마진은 그릴 수 없다.
  assert.equal(actualMarginNm(800, 1000), 0)
})

test('actualMarginNm inverts requiredFovNm at the exact-fit boundary', () => {
  const span = 8 * 45
  const fov = requiredFovNm(8, 45, 0.10)!
  near(actualMarginNm(fov, span) / fov, 0.10)
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

// ── 경계 확대 뷰의 신호 모델 ────────────────────────────────────────────────

test('edgeIntensity is a specimen-side profile: peak at the edge, plateaus away from it', () => {
  const peak = edgeIntensity(0)
  assert.ok(peak > edgeIntensity(SEM_EDGE_WIDTH_NM), 'rim must be brighter than the bar interior')
  assert.ok(peak > edgeIntensity(-SEM_EDGE_WIDTH_NM), 'rim must be brighter than the space')
  near(edgeIntensity(-50), SEM_LEVELS.core, 1e-3)
  near(edgeIntensity(50), SEM_LEVELS.space, 1e-3)
  // 프로파일은 대칭 구간 밖에서 평평하다 — 창을 넓혀도 새 구조가 생기지 않는다.
  near(edgeIntensity(-50), edgeIntensity(-500), 1e-9)
})

test('samplePixelNm averages the peak away as the pixel grows', () => {
  const fine = samplePixelNm(0, 0.2)!
  const coarse = samplePixelNm(0, 4)!
  assert.ok(fine > coarse, `fine ${fine} must retain more peak than coarse ${coarse}`)
  near(samplePixelNm(0, 1e-6), edgeIntensity(0), 1e-6)
  assert.equal(samplePixelNm(0, 0), null)
  assert.equal(samplePixelNm(Number.NaN, 1), null)
})

test('edgeWindowHalfNm fixes the window in nm and clips at the neighbouring edge', () => {
  // 900 nm FOV / 512 px = 1.7578 nm/px -> 12 px 창
  near(edgeWindowHalfNm(45, 90, 900 / 512), 6 * (900 / 512))
  // CD가 좁으면 CD/2가 창을 자른다 — 옆 경계를 넘어가지 않게.
  near(edgeWindowHalfNm(4, 90, 900 / 512), 2)
  assert.equal(edgeWindowHalfNm(45, 45, 1.75), null, 'pitch <= CD leaves no space')
  assert.equal(edgeWindowHalfNm(45, 90, 0), null)
})

test('edgeStrip keeps cells at their true pixel width and never stretches them', () => {
  const half = edgeWindowHalfNm(45, 90, 900 / 512)!
  const strip = edgeStrip(512, 900 / 512, half)!
  assert.equal(strip.samples.length, 12)
  near(strip.nmPerPx, 900 / 512)
  near(strip.pxOnEdge, SEM_EDGE_WIDTH_NM / (900 / 512))
  assert.equal(edgeStrip(512, 0, half), null)
})

test('a finer pixel setting lands MORE samples on the same fixed edge', () => {
  // 회귀 테스트. 이전 구현은 번짐 폭을 픽셀 크기에서 유도해서(bloom = px × 1.5)
  // 경계에 걸리는 칸 수가 어떤 설정에서도 6으로 고정이었다 — 이 화면이 보여주려던
  // 바로 그 차이가 정의상 사라져 있었다. 물리 경계폭을 nm으로 고정한 지금은
  // 픽셀을 반으로 줄일 때마다 경계 위 샘플이 배가되어야 한다.
  const half = edgeWindowHalfNm(45, 90, 900 / 512)!
  const onEdge = (pixels: number) =>
    edgeStrip(pixels, 900 / pixels, half)!.samples.filter(v => v > 0.5).length
  assert.deepEqual([onEdge(512), onEdge(1024), onEdge(2048)], [2, 4, 8])

  // 큰 픽셀은 피크 자체도 평균으로 깎는다.
  const peak = (pixels: number) => Math.max(...edgeStrip(pixels, 900 / pixels, half)!.samples)
  assert.ok(peak(512) < peak(1024) && peak(1024) < peak(2048))
})

test('edgeComparePair pits the recommended setting against the next step up', () => {
  assert.deepEqual(edgeComparePair(512), [512, 1024])
  assert.deepEqual(edgeComparePair(2048), [2048, 4096])
  // 이미 최상단이면 위가 없으므로 한 단계 아래와 비교한다.
  assert.deepEqual(edgeComparePair(4096), [2048, 4096])
})
