import { test } from 'node:test'
import assert from 'node:assert/strict'
import { inspectButtonHtml, pinnedTooltipPosition } from './chartInspectTooltip.ts'

const size = { contentSize: [100, 40] }

test('the tooltip stays pinned while the pointer moves down into it', () => {
  const position = pinnedTooltipPosition()
  const opened = position([200, 50], [{ name: 'a' }], null, null, size)
  assert.deepEqual(opened, [150, 56])
  // Travelling down inside the tooltip's width keeps the spot.
  assert.deepEqual(position([210, 80], [{ name: 'a' }], null, null, size), [150, 56])
})

test('another point, or the same point from elsewhere, re-opens under the pointer', () => {
  const position = pinnedTooltipPosition()
  position([200, 50], { name: 'a' }, null, null, size)
  assert.deepEqual(position([300, 50], { name: 'b' }, null, null, size), [250, 56])
  assert.deepEqual(position([500, 50], { name: 'b' }, null, null, size), [450, 56])
})

test('the button escapes its key and label', () => {
  const html = inspectButtonHtml('2026-09-30T01:02:03"<', '<b>')
  assert.match(html, /data-inspect-key="2026-09-30T01:02:03&quot;&lt;"/)
  assert.match(html, />&lt;b&gt;<\/button>$/)
})
