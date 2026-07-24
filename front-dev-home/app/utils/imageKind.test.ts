// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isTiffName } from './imageKind.ts'

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
