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
