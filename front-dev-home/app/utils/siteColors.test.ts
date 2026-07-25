// Pure-logic tests — run with: npm --prefix front-dev-home test
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { assignSiteColors } from './siteColors.ts'

const RAMP = ['#a', '#b', '#c']

test('assignSiteColors: maps keys to the ramp in insertion order', () => {
  const colors = assignSiteColors(['P 1', 'P 2', 'P 3'], RAMP)
  assert.deepEqual(colors, { 'P 1': '#a', 'P 2': '#b', 'P 3': '#c' })
})

test('assignSiteColors: caps at ramp length — overflow keys get no entry', () => {
  const colors = assignSiteColors(['P 1', 'P 2', 'P 3', 'P 4'], RAMP)
  assert.equal(colors['P 4'], undefined)
  assert.equal(Object.keys(colors).length, 3)
})

test('assignSiteColors: order of keys determines the color', () => {
  const colors = assignSiteColors(['B 5', 'A 2'], RAMP)
  assert.equal(colors['B 5'], '#a')
  assert.equal(colors['A 2'], '#b')
})

test('assignSiteColors: empty input yields an empty map', () => {
  assert.deepEqual(assignSiteColors([], RAMP), {})
})
