// front-dev-home/app/utils/chartPalette.test.ts
// Covers the split between theme-driven presentation color and the fixed
// data-encoding/semantic color, and the dark-mode property that motivated it.
// Run: cd front-dev-home && node --test app/utils/chartPalette.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { SK_SCALE, SK_STATE, buildChartPalette } from './chartPalette.ts'

const MATLAB = ['#0072BD', '#D95319', '#EDB120'] as const
const LIGHT = { ink: '#262626', surface: '#ffffff' }
const DARK = { ink: '#EEF1FA', surface: '#100C2A' }

const luminance = (hex: string) => {
  const h = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

test('series and brand come straight off the theme palette', () => {
  const sk = buildChartPalette(MATLAB, LIGHT.ink, LIGHT.surface)
  assert.equal(sk.series, '#0072BD')
  assert.equal(sk.brand, '#D95319')
  assert.equal(sk.ink, '#262626')
})

// The whole point of the refactor: these used to be frozen Paper Pro values, so
// switching the theme left the skewvoir charts unchanged.
test('switching the palette moves every presentation token', () => {
  const a = buildChartPalette(MATLAB, LIGHT.ink, LIGHT.surface)
  const b = buildChartPalette(['#d87c7c', '#919e8b'], '#3f3a34', '#fef8ef')
  for (const key of ['series', 'seriesSoft', 'brand', 'sand', 'muted', 'ink'] as const) {
    assert.notEqual(a[key], b[key], `${key} did not follow the theme`)
  }
})

// The bug this design exists to prevent: the old constants hardcoded near-black
// ink and a warm cream band, which are invisible on a dark card.
test('furniture tracks the surface, so dark themes stay legible', () => {
  const light = buildChartPalette(MATLAB, LIGHT.ink, LIGHT.surface)
  const dark = buildChartPalette(MATLAB, DARK.ink, DARK.surface)

  // On a light canvas the furniture must be darker than the canvas; on a dark
  // canvas it must be lighter. Anything else means it vanished.
  for (const key of ['sand', 'muted', 'ink'] as const) {
    assert.ok(luminance(light[key]) < luminance(LIGHT.surface), `light ${key} is not darker than its surface`)
    assert.ok(luminance(dark[key]) > luminance(DARK.surface), `dark ${key} is not lighter than its surface`)
  }
})

test('sand is a subtler wash than muted, which is subtler than ink', () => {
  const sk = buildChartPalette(MATLAB, LIGHT.ink, LIGHT.surface)
  // light surface ⇒ the more surface mixed in, the higher the luminance
  assert.ok(luminance(sk.sand) > luminance(sk.muted))
  assert.ok(luminance(sk.muted) > luminance(sk.ink))
})

test('seriesSoft is a softened series, not a different hue', () => {
  const sk = buildChartPalette(MATLAB, LIGHT.ink, LIGHT.surface)
  assert.notEqual(sk.seriesSoft, sk.series)
  // #0072BD is blue-dominant; softening toward white must not change that
  const h = sk.seriesSoft.replace('#', '')
  const [r, g, b] = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)) as [number, number, number]
  assert.ok(b > r && b > g, 'seriesSoft drifted off the series hue')
  assert.ok(luminance(sk.seriesSoft) > luminance(sk.series), 'seriesSoft is not softer')
})

test('an empty palette still yields usable color rather than undefined', () => {
  const sk = buildChartPalette([], LIGHT.ink, LIGHT.surface)
  for (const key of ['series', 'seriesSoft', 'brand', 'sand', 'muted', 'ink'] as const) {
    assert.match(sk[key], /^#[0-9a-fA-F]{6}$/, `${key} is not a hex color`)
  }
})

// Data encoding and semantics are deliberately NOT part of buildChartPalette:
// a low→high ramp must stay comparable across screenshots and "bad" must stay
// red, whichever theme is active.
test('scale and state are fixed and carry no theme input', () => {
  assert.equal(SK_SCALE.length, 5)
  assert.deepEqual([...SK_SCALE], ['#5C86AE', '#9BB6CD', '#E4D9C4', '#DB9A6B', '#C75A3C'])
  assert.deepEqual(SK_STATE, { ok: '#3E8E5E', warn: '#C98A2E', bad: '#C4453B' })
})
