import assert from 'node:assert/strict'
import test from 'node:test'
import {
  ECHART_THEME_OPTIONS,
  getEchartThemePalette,
  resolveEchartThemeName,
  type EchartThemeName
} from './echartsThemes.ts'
import { PARA_KEYS } from './paraTrendSeries.ts'

const themeNames = ECHART_THEME_OPTIONS
  .map(option => option.value)
  .filter((value): value is EchartThemeName => value !== 'default')

const parameterRamp = async () => {
  const loaded = await import('./parameterRamp.ts').catch(() => null)
  assert.ok(loaded, 'parameter ramp module must exist')
  return loaded
}

test('every real theme has anchors taken from its own series palette', async () => {
  const { PARAMETER_RAMP_ANCHORS } = await parameterRamp()
  for (const name of themeNames) {
    const palette = getEchartThemePalette(name).map(color => color.toLowerCase())
    const [low, high] = PARAMETER_RAMP_ANCHORS[name]
    assert.ok(palette.includes(low.toLowerCase()), `${name} low anchor is outside its palette`)
    assert.ok(palette.includes(high.toLowerCase()), `${name} high anchor is outside its palette`)
  }
})

test('every ramp maps the cool end to para_5 and the warm end to para_over_16', async () => {
  const { buildParameterRamp, PARAMETER_RAMP_ANCHORS } = await parameterRamp()
  for (const name of themeNames) {
    const ramp = buildParameterRamp(name)
    const [low, high] = PARAMETER_RAMP_ANCHORS[name]
    assert.deepEqual(Object.keys(ramp).sort(), [...PARA_KEYS].sort())
    assert.equal(ramp.para_5, low.toLowerCase())
    assert.equal(ramp.para_over_16, high.toLowerCase())
    assert.equal(new Set(Object.values(ramp)).size, PARA_KEYS.length)
  }
})

test('MATLAB ramp uses deterministic 25 percent RGB steps', async () => {
  const { buildParameterRamp } = await parameterRamp()
  assert.deepEqual(buildParameterRamp('matlab'), {
    para_over_16: '#a2142f',
    para_16: '#7a2c53',
    para_13: '#514376',
    para_9: '#295b9a',
    para_5: '#0072bd'
  })
})

test('Default follows MATLAB in light mode and Dark in dark mode', async () => {
  const { buildParameterRamp } = await parameterRamp()
  assert.deepEqual(
    buildParameterRamp(resolveEchartThemeName('default', 'light')),
    buildParameterRamp('matlab')
  )
  assert.deepEqual(
    buildParameterRamp(resolveEchartThemeName('default', 'dark')),
    buildParameterRamp('dark')
  )
})
