// Pure-logic tests for chartZoom. Run: node --test app/utils/chartZoom.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { withPreservedZoom } from './chartZoom.ts'

test('live window replaces the declared one, index-matched', () => {
  const next = {
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, height: 16 }
    ]
  }
  const merged = withPreservedZoom(next, [{ start: 40, end: 60 }, { start: 40, end: 60 }])
  assert.deepEqual(merged.dataZoom, [
    { type: 'inside', start: 40, end: 60 },
    { type: 'slider', start: 40, end: 60, height: 16 }
  ])
})

test('the incoming option is never mutated (it comes from a computed)', () => {
  const zoom = { type: 'inside', start: 0, end: 100 }
  const next = { dataZoom: [zoom] }
  withPreservedZoom(next, [{ start: 25, end: 75 }])
  assert.deepEqual(zoom, { type: 'inside', start: 0, end: 100 })
  assert.deepEqual(next.dataZoom, [{ type: 'inside', start: 0, end: 100 }])
})

test('a chart with no dataZoom is returned untouched', () => {
  const next = { series: [] }
  assert.equal(withPreservedZoom(next, [{ start: 10, end: 20 }]), next)
})

test('no live zoom state (first render) keeps the declared window', () => {
  const next = { dataZoom: [{ type: 'inside', start: 0, end: 100 }] }
  assert.equal(withPreservedZoom(next, undefined), next)
  assert.equal(withPreservedZoom(next, []), next)
})

test('a declared entry with no live counterpart keeps its own window', () => {
  const next = {
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'inside', start: 0, end: 100, yAxisIndex: [0] }
    ]
  }
  const merged = withPreservedZoom(next, [{ start: 30, end: 70 }])
  assert.deepEqual(merged.dataZoom, [
    { type: 'inside', start: 30, end: 70 },
    { type: 'inside', start: 0, end: 100, yAxisIndex: [0] }
  ])
})

test('a partial live window (start only) is ignored rather than half-applied', () => {
  const next = { dataZoom: [{ type: 'inside', start: 0, end: 100 }] }
  assert.equal(withPreservedZoom(next, [{ start: 30 }]), next)
})

test('a fully zoomed-out chart still round-trips 0~100', () => {
  const next = { dataZoom: [{ type: 'slider' }] }
  const merged = withPreservedZoom(next, [{ start: 0, end: 100 }])
  assert.deepEqual(merged.dataZoom, [{ type: 'slider', start: 0, end: 100 }])
})
