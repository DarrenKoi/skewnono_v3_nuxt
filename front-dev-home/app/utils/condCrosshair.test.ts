// Pure-logic tests for condCrosshair. Run: node --test app/utils/condCrosshair.test.ts
//
// Mirrors back_dev_home/_core/tests/test_cond_cursor.py — the same worked
// example, so the two parsers cannot drift apart silently.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { condMarks } from './condCrosshair.ts'

const rows = (pixel: string, cursor: string, key = '!Cursor_info') => [
  { key: 'Magnification', value: '30000' },
  { key: 'Pixel', value: pixel },
  { key, value: cursor }
]

test('fractions divide by Pixel × 10, per axis', () => {
  const marks = condMarks(rows('512,512', '0,0,0,0,2097,2561,1600,1600,3520,3520'))
  assert.deepEqual(marks, {
    pixel: [512, 512],
    crosshair: [2097 / 5120, 2561 / 5120],
    box: [1600 / 5120, 1600 / 5120, 3520 / 5120, 3520 / 5120]
  })
  assert.deepEqual(
    condMarks(rows('1024,512', '0,0,0,0,5120,2560,-1,-1,-1,-1'))?.crosshair,
    [0.5, 0.5]
  )
})

test('key spelling varies between tools', () => {
  assert.ok(condMarks(rows('512,512', '0,0,0,0,1,1,-1,-1,-1,-1', '!Cursor_inf')))
  assert.ok(condMarks(rows('512,512', '0,0,0,0,1,1,-1,-1,-1,-1', 'Cursor_info')))
})

test('-1 means the mark was not drawn', () => {
  const noCross = condMarks(rows('512,512', '0,0,0,0,-1,-1,100,100,200,200'))
  assert.equal(noCross?.crosshair, null)
  assert.ok(noCross?.box)
  const noBox = condMarks(rows('512,512', '0,0,0,0,2560,2560,-1,-1,-1,-1'))
  assert.equal(noBox?.box, null)
  assert.equal(condMarks(rows('512,512', '0,0,0,0,-1,-1,-1,-1,-1,-1')), null)
})

test('unusable rows are null, never a throw', () => {
  assert.equal(condMarks(null), null)
  assert.equal(condMarks([]), null)
  assert.equal(condMarks([{ key: 'Pixel', value: '512,512' }]), null)
  assert.equal(condMarks(rows('0,512', '0,0,0,0,1,1,1,1,1,1')), null)
  assert.equal(condMarks(rows('512,512', '1,2,3')), null)
  assert.equal(condMarks(rows('512,512', 'a,b,c,d,e,f,g,h,i,j')), null)
})
