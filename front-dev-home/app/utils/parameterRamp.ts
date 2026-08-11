import type { EchartThemeName } from './echartsThemes.ts'
import type { ParaKey } from './paraTrendSeries.ts'

export const PARAMETER_RAMP_ANCHORS = {
  vintage: ['#61a0a8', '#d87c7c'],
  dark: ['#4992ff', '#ff6e76'],
  macarons: ['#5ab1ef', '#c05050'],
  infographic: ['#60C0DD', '#C1232B'],
  shine: ['#0098d9', '#c12e34'],
  roma: ['#6699FF', '#E01F54'],
  matlab: ['#0072BD', '#A2142F']
} as const satisfies Record<EchartThemeName, readonly [string, string]>

const parseHex = (value: string): [number, number, number] => {
  const hex = value.slice(1)
  return [
    Number.parseInt(hex.slice(0, 2), 16),
    Number.parseInt(hex.slice(2, 4), 16),
    Number.parseInt(hex.slice(4, 6), 16)
  ]
}

const mixHex = (low: string, high: string, position: number): string => {
  const from = parseHex(low)
  const to = parseHex(high)
  const channels = from.map((value, index) =>
    Math.round(value + (to[index]! - value) * position)
      .toString(16)
      .padStart(2, '0')
  )
  return `#${channels.join('')}`
}

export const buildParameterRamp = (themeName: EchartThemeName): Record<ParaKey, string> => {
  const [low, high] = PARAMETER_RAMP_ANCHORS[themeName]
  return {
    para_over_16: mixHex(low, high, 1),
    para_16: mixHex(low, high, 0.75),
    para_13: mixHex(low, high, 0.5),
    para_9: mixHex(low, high, 0.25),
    para_5: mixHex(low, high, 0)
  }
}
