// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  fovUm, fovNm, parsePixelSetting, pixelSizeNm, pxPerCd, scanTimeFactor,
  seriesFromModel, magRange, isAssumedMag, buildMagPixelTable
} from './magPixel.ts'

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
