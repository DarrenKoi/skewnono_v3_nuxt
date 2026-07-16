// front-dev-home/app/utils/echartsThemes.test.ts
// Verifies the per-theme export background matches each theme's canvas tone.
// Run: cd front-dev-home && node --test app/utils/echartsThemes.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { getEchartThemeBackground } from './echartsThemes.ts'

test('vintage export background is warm paper', () => {
  assert.equal(getEchartThemeBackground('vintage'), '#fef8ef')
})

test('dark export background is deep navy', () => {
  assert.equal(getEchartThemeBackground('dark'), '#100C2A')
})

test('light alt-themes export on white', () => {
  assert.equal(getEchartThemeBackground('macarons'), '#ffffff')
  assert.equal(getEchartThemeBackground('infographic'), '#ffffff')
  assert.equal(getEchartThemeBackground('shine'), '#ffffff')
  assert.equal(getEchartThemeBackground('roma'), '#ffffff')
})
