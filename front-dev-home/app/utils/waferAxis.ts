// Builds the ECharts axis config for the wafer map. Pure (no ECharts import) so
// the grid/label logic is unit-tested.
//
// When grid is on we set `interval: pitchMm` so splitLines land on die-pitch
// multiples (through die centres), and label each tick with its die index via
// mmToDieIndex. When the pitch is unknown we omit the interval and fall back to
// rounded-mm labels. The caller keeps the plot rect square (equal margins,
// containLabel:false) so the wafer stays circular even with labels shown.
import { mmToDieIndex } from './waferGeometry.ts'

export interface WaferAxisConfig {
  type: 'value'
  min: number
  max: number
  interval?: number
  splitLine: { show: boolean, lineStyle?: { color: string, opacity: number } }
  axisLabel: { show: boolean, color?: string, fontSize?: number, formatter?: (v: number) => string }
  axisLine: { show: boolean }
  axisTick: { show: boolean }
}

export const buildWaferAxis = (
  grid: boolean,
  axisMax: number,
  pitchMm: number,
  color: string
): WaferAxisConfig => {
  if (!grid) {
    return {
      type: 'value',
      min: -axisMax,
      max: axisMax,
      splitLine: { show: false },
      axisLabel: { show: false },
      axisLine: { show: false },
      axisTick: { show: false }
    }
  }
  const cfg: WaferAxisConfig = {
    type: 'value',
    min: -axisMax,
    max: axisMax,
    splitLine: { show: true, lineStyle: { color, opacity: 0.22 } },
    axisLabel: {
      show: true,
      color,
      fontSize: 9,
      formatter: (v: number) => {
        const i = mmToDieIndex(v, pitchMm)
        return i == null ? String(Math.round(v)) : String(i)
      }
    },
    axisLine: { show: false },
    axisTick: { show: true }
  }
  if (pitchMm > 0) cfg.interval = pitchMm
  return cfg
}
