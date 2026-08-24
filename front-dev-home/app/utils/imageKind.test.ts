// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { imageVariantLabel, imageVariantLabels, isTiffName, variantLabelBase } from './imageKind.ts'

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

// ── imageVariantLabels ───────────────────────────────────────────────────────

test('labels stay bare when every sub-position appears once', () => {
  assert.deepEqual(
    imageVariantLabels(['S04-U.jpeg', 'S04-T.jpeg', 'S04-M.tif', 'S04-L.jpeg']),
    ['U', 'T', 'M', 'L']
  )
})

test('a sub-position listed under two extensions gets rendition-tagged labels', () => {
  // The office 4-image case (user-confirmed 2026-08-24): same suffix as a JPEG
  // preview AND a TIFF original. Per-name labels collide (U, U, L, L), which
  // rendered duplicated chips and made the second of each pair unselectable.
  assert.deepEqual(
    imageVariantLabels(['S04_M0004-01MP-U.jpeg', 'S04_M0004-01MP-U.TIF', 'S04_M0004-01MP-L.jpeg', 'S04_M0004-01MP-L.TIF']),
    ['U·JPG', 'U·TIF', 'L·JPG', 'L·TIF']
  )
})

test('rendition tags collapse spelling variants, any case', () => {
  assert.deepEqual(imageVariantLabels(['a-U.jpg', 'a-U.TIFF']), ['U·JPG', 'U·TIF'])
})

test('labels are pairwise distinct even when suffix AND rendition collide', () => {
  const labels = imageVariantLabels(['a-U.tif', 'a-U.TIF', 'a-U.jpeg'])
  assert.equal(new Set(labels).size, labels.length)
  assert.deepEqual(labels, ['U·TIF', 'U·TIF·2', 'U·JPG'])
})

test('only the colliding sub-position grows a tag; its siblings stay bare', () => {
  assert.deepEqual(
    imageVariantLabels(['a-U.jpeg', 'a-U.TIF', 'a-T.jpeg']),
    ['U·JPG', 'U·TIF', 'T']
  )
})

test('variantLabelBase strips the rendition half and passes bare labels through', () => {
  assert.equal(variantLabelBase('U·TIF'), 'U')
  assert.equal(variantLabelBase('U·TIF·2'), 'U')
  assert.equal(variantLabelBase('U'), 'U')
  assert.equal(variantLabelBase('2'), '2')
})
