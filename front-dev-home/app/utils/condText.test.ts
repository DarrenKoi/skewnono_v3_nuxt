// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseCondText } from './condText.ts'

test('parseCondText splits tab-separated key/value rows and skips the header', () => {
  const block = parseCondText(
    '# Observation condition\nScope\tSEM\nMagnification\t50000\n\nPixel\t512,512\n!Cursor_info\t-1,-1,-1,-1,2097,2561,-1,-1,-1,-1\n'
  )
  assert.equal(block.source, 'cond.txt')
  assert.deepEqual(block.rows, [
    { key: 'Scope', value: 'SEM' },
    { key: 'Magnification', value: '50000' },
    { key: 'Pixel', value: '512,512' },
    { key: '!Cursor_info', value: '-1,-1,-1,-1,2097,2561,-1,-1,-1,-1' }
  ])
})

test('parseCondText keeps units inside values and tolerates a value-less key', () => {
  const block = parseCondText('Accelerating_voltage   500 V\r\nField_Size\r\n')
  assert.deepEqual(block.rows, [
    { key: 'Accelerating_voltage', value: '500 V' },
    { key: 'Field_Size', value: '' }
  ])
})
