// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { imageVariantLabel, isTiffName } from './imageKind.ts'

test('isTiffName matches .tif and .tiff case-insensitively', () => {
  assert.equal(isTiffName('shot04.tif'), true)
  assert.equal(isTiffName('shot04.TIFF'), true)
  assert.equal(isTiffName('shot01.jpeg'), false)
  assert.equal(isTiffName('shot01.jpg'), false)
  assert.equal(isTiffName('archive.tif.jpeg'), false)
})

test('isTiffName is false for empty and missing names', () => {
  assert.equal(isTiffName(''), false)
  assert.equal(isTiffName(null), false)
  assert.equal(isTiffName(undefined), false)
})

test('imageVariantLabel reads the HV-SEM stem suffix', () => {
  assert.equal(imageVariantLabel('S04_M0004-01MP-U.jpeg', 0), 'U')
  assert.equal(imageVariantLabel('IMMS0001-T.jpeg', 1), 'T')
  assert.equal(imageVariantLabel('IMMS0001-M.tif', 2), 'M')
})

test('imageVariantLabel falls back to the 1-based position without a suffix', () => {
  assert.equal(imageVariantLabel('MSR_001_CD_TOP_1234.jpeg', 0), '1')
  assert.equal(imageVariantLabel('MSR_001_CD_TOP_1234.jpeg', 2), '3')
  // A long tail segment is a name part, not a variant suffix.
  assert.equal(imageVariantLabel('shot-final.jpeg', 1), '2')
})
