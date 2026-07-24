// front-dev-home/app/utils/echartsThemes.test.ts
// Verifies the per-theme export background matches each theme's canvas tone,
// and that each palette carries its full upstream length rather than a truncation.
// Run: cd front-dev-home && node --test app/utils/echartsThemes.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ECHART_THEME_OPTIONS,
  getEchartThemeBackground,
  getEchartThemePalette,
  isEchartThemeSelection,
  resolveEchartThemeName
} from './echartsThemes.ts'

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
  assert.equal(getEchartThemeBackground('matlab'), '#ffffff')
})

// The palettes were once ported six-deep regardless of how long upstream was,
// so a chart with a seventh series silently wrapped back to color one. These
// lengths are the upstream files in app/assets/echarts-theme/.
test('palettes keep their full upstream length', () => {
  assert.equal(getEchartThemePalette('vintage').length, 10)
  assert.equal(getEchartThemePalette('dark').length, 9)
  assert.equal(getEchartThemePalette('macarons').length, 20)
  assert.equal(getEchartThemePalette('infographic').length, 15)
  assert.equal(getEchartThemePalette('shine').length, 8)
  assert.equal(getEchartThemePalette('roma').length, 20)
})

// Every entry is round(v * 255) of the R2014b-onward RGB triplets published at
// math.loyola.edu/~loberbro/matlab/html/colorsInMatlab.html.
test('matlab palette is the R2014b default color order', () => {
  assert.deepEqual(getEchartThemePalette('matlab'), [
    '#0072BD',
    '#D95319',
    '#EDB120',
    '#7E2F8E',
    '#77AC30',
    '#4DBEEE',
    '#A2142F'
  ])
})

test('the first six of a palette are unchanged by the length extension', () => {
  assert.deepEqual(getEchartThemePalette('vintage').slice(0, 6), [
    '#d87c7c',
    '#919e8b',
    '#d7ab82',
    '#6e7074',
    '#61a0a8',
    '#efa18d'
  ])
  assert.deepEqual(getEchartThemePalette('dark').slice(0, 6), [
    '#4992ff',
    '#7cffb2',
    '#fddd60',
    '#ff6e76',
    '#58d9f9',
    '#05c091'
  ])
})

// The picker paints one 16px dot per swatch entry on a fixed-width card, so a
// 20-color palette would run off the edge. Handing the full palette to the
// option metadata is the easy mistake; nothing but this test catches it.
test('picker swatches stay at six colors however long the palette is', () => {
  for (const option of ECHART_THEME_OPTIONS) {
    assert.ok(
      option.colors.length <= 6,
      `${option.value} would render ${option.colors.length} swatch dots`
    )
  }
})

test('every selectable theme has a palette and an export background', () => {
  for (const option of ECHART_THEME_OPTIONS) {
    assert.ok(isEchartThemeSelection(option.value))
    const name = resolveEchartThemeName(option.value, 'light')
    assert.ok(getEchartThemePalette(name).length > 0, `${option.value} has no palette`)
    assert.match(getEchartThemeBackground(name), /^#[0-9a-fA-F]{6}$/)
  }
})

test('matlab is selectable and never stands in for the default selection', () => {
  assert.ok(isEchartThemeSelection('matlab'))
  assert.equal(resolveEchartThemeName('matlab', 'light'), 'matlab')
  assert.equal(resolveEchartThemeName('matlab', 'dark'), 'matlab')
  assert.equal(resolveEchartThemeName('default', 'light'), 'vintage')
  assert.equal(resolveEchartThemeName('default', 'dark'), 'dark')
})
