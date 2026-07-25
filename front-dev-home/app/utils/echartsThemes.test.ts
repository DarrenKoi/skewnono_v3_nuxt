// front-dev-home/app/utils/echartsThemes.test.ts
// Verifies the per-theme export background matches each theme's canvas tone,
// and that each palette carries its full upstream length rather than a truncation.
// Run: cd front-dev-home && node --test app/utils/echartsThemes.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ECHART_THEME_OPTIONS,
  echartThemeId,
  getEchartThemePalette,
  getEchartThemeSurface,
  isEchartThemeSelection,
  registerEchartsThemes,
  resolveEchartThemeName
} from './echartsThemes.ts'

// Backdrop in each theme's NATIVE mode, which is what the old name-only
// getEchartThemeBackground returned before it became color-mode aware.
const nativeBackground = (name: Parameters<typeof getEchartThemeSurface>[0]) =>
  getEchartThemeSurface(name, name === 'dark' ? 'dark' : 'light').surface

test('vintage export background is warm paper', () => {
  assert.equal(nativeBackground('vintage'), '#fef8ef')
})

test('dark export background is deep navy', () => {
  assert.equal(nativeBackground('dark'), '#100C2A')
})

test('light alt-themes export on white', () => {
  assert.equal(nativeBackground('macarons'), '#ffffff')
  assert.equal(nativeBackground('infographic'), '#ffffff')
  assert.equal(nativeBackground('shine'), '#ffffff')
  assert.equal(nativeBackground('roma'), '#ffffff')
  assert.equal(nativeBackground('matlab'), '#ffffff')
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
// math.loyola.edu/~loberbro/matlab/html/colorsInMatlab.html. Sliced, because we
// append three of our own past index 6 -- but the head must stay verbatim, so a
// chart with <= 7 series is colored exactly as MATLAB would color it. This is
// the test that keeps the theme's name honest.
test('matlab palette opens with the R2014b default color order, verbatim', () => {
  assert.deepEqual(getEchartThemePalette('matlab').slice(0, 7), [
    '#0072BD',
    '#D95319',
    '#EDB120',
    '#7E2F8E',
    '#77AC30',
    '#4DBEEE',
    '#A2142F'
  ])
})

// assignCompareColors() withholds index 0 for the selected tool, so covering
// ten series takes ten colors, not nine.
test('matlab palette carries ten colors and no duplicates', () => {
  const palette = getEchartThemePalette('matlab')
  assert.equal(palette.length, 10)
  assert.equal(new Set(palette).size, 10)
  assert.deepEqual(palette.slice(7), ['#148F81', '#E72784', '#285D38'])
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
    assert.match(nativeBackground(name), /^#[0-9a-fA-F]{6}$/)
  }
})

test('matlab is both selectable and what the default selection resolves to', () => {
  assert.ok(isEchartThemeSelection('matlab'))
  assert.equal(resolveEchartThemeName('matlab', 'light'), 'matlab')
  assert.equal(resolveEchartThemeName('matlab', 'dark'), 'matlab')
  assert.equal(resolveEchartThemeName('default', 'light'), 'matlab')
})

// MATLAB's axis furniture is #262626 on an assumed white canvas, but themes
// render transparent over the card surface -- so the dark branch must not
// follow the light one over to matlab, or the axes vanish into the background.
test('the default selection stays on the dark theme in dark mode', () => {
  assert.equal(resolveEchartThemeName('default', 'dark'), 'dark')
})

// ---------------------------------------------------------------------------
// Color-mode furniture
//
// The picker and the color mode are independent, so any of the six light
// themes can be active while the app is dark (and `dark` while it is light).
// Charts draw on a transparent canvas over the app card, so furniture has to
// answer to the CARD; only the palette belongs to the theme.
// ---------------------------------------------------------------------------

test('a theme keeps its own tones in its native mode', () => {
  assert.deepEqual(getEchartThemeSurface('matlab', 'light'), { ink: '#262626', surface: '#ffffff' })
  assert.deepEqual(getEchartThemeSurface('vintage', 'light'), { ink: '#3f3a34', surface: '#fef8ef' })
  assert.deepEqual(getEchartThemeSurface('dark', 'dark'), { ink: '#EEF1FA', surface: '#100C2A' })
})

// The bug: MATLAB's #262626 ink on a dark card is black on black.
test('a light theme in dark mode takes dark furniture, not its own', () => {
  for (const name of ['matlab', 'vintage', 'macarons', 'infographic', 'shine', 'roma'] as const) {
    const { ink, surface } = getEchartThemeSurface(name, 'dark')
    assert.equal(ink, '#EEF1FA', `${name} kept a light ink on a dark card`)
    assert.equal(surface, '#100C2A', `${name} kept a light backdrop on a dark card`)
  }
})

// And the mirror case, which was equally broken: dark's #EEF1FA on white.
test('the dark theme in light mode takes light furniture', () => {
  const { ink, surface } = getEchartThemeSurface('dark', 'light')
  assert.equal(ink, '#1f2937')
  assert.equal(surface, '#ffffff')
})

test('the palette is mode-independent — only furniture flips', () => {
  for (const name of ['matlab', 'dark', 'vintage'] as const) {
    assert.deepEqual(getEchartThemePalette(name), getEchartThemePalette(name))
  }
  // matlab stays matlab-colored on a dark card; that is the point of the split.
  assert.equal(getEchartThemePalette('matlab')[0], '#0072BD')
})

test('theme id encodes both theme and mode, so one watch covers both', () => {
  assert.equal(echartThemeId('matlab', 'light'), 'matlab@light')
  assert.equal(echartThemeId('matlab', 'dark'), 'matlab@dark')
  assert.notEqual(echartThemeId('matlab', 'light'), echartThemeId('matlab', 'dark'))
  // anything not 'dark' is light — useColorMode also emits 'system'
  assert.equal(echartThemeId('matlab', 'system'), 'matlab@light')
})

test('every theme registers one variant per mode, and the overlay keeps the palette', () => {
  const seen = new Map<string, Record<string, unknown>>()
  registerEchartsThemes({ registerTheme: (n, t) => void seen.set(n, t as Record<string, unknown>) })

  assert.equal(seen.size, 14, 'expected 7 themes x 2 modes')

  const light = seen.get('matlab@light')!
  const dark = seen.get('matlab@dark')!
  // identity survives the overlay
  assert.deepEqual(light.color, dark.color)
  assert.deepEqual(dark.color, [...getEchartThemePalette('matlab')])
  // furniture does not
  assert.equal(dark.darkMode, true)
  assert.deepEqual((dark.title as { textStyle: { color: string } }).textStyle.color, '#EEF1FA')
  assert.deepEqual((light.title as { textStyle: { color: string } }).textStyle.color, '#262626')

  // deep merge must not drop sibling keys the overlay never mentions: matlab's
  // categoryAxis says splitLine.show=false, and the overlay only sets its color.
  const axis = dark.categoryAxis as { splitLine: { show?: boolean, lineStyle: { color: string } } }
  assert.equal(axis.splitLine.show, false, 'overlay clobbered a sibling key')
  assert.equal(axis.splitLine.lineStyle.color, '#484753')

  // and non-furniture identity settings survive untouched
  assert.deepEqual(dark.visualMap, light.visualMap)
  assert.deepEqual(dark.candlestick, light.candlestick)
})
