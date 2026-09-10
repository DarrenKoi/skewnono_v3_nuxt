// Builds the ECharts axis config for the wafer map. Pure (no ECharts import) so
// the grid/label logic is unit-tested.
//
// When grid is on, each tick is labelled with its die index via mmToDieIndex,
// and the ticks are placed EXPLICITLY on the die centres.
//
// `interval: pitchMm` is what this used to do, and it cannot work. ECharts drops
// its computed nice-extent the moment an interval arrives alongside min/max
// (scale/Interval.js setConfig: "use user-set extent") and then steps ticks from
// the extent START — here −radius·1.03, which is nowhere near the die lattice
// and cannot be phase-shifted onto it by any choice of interval. So the axis
// drew its own grid, out of phase with the die-boundary overlay's, and the wafer
// map showed two grids at once.
//
// Hence the split of duties: the boundary overlay owns the LINES whenever the
// pitch is known, and this axis contributes only NUMBERS. Split lines return
// only in the no-pitch fallback, where the overlay has nothing to draw and the
// labels degrade to rounded mm. The caller keeps the plot rect square (equal
// margins, containLabel:false) so the wafer stays circular even with labels on.
import { mmToDieIndex } from './waferGeometry.ts'
import { dieCentreTicks } from './waferDieGrid.ts'

export interface WaferAxisConfig {
  type: 'value'
  min: number
  max: number
  splitLine: { show: boolean, lineStyle?: { color: string, opacity: number } }
  axisLabel: {
    show: boolean
    color?: string
    fontSize?: number
    formatter?: (v: number) => string
    customValues?: number[]
  }
  axisLine: { show: boolean }
  // customValues here also drives splitLine, which resolves its positions through
  // the axisTick model (coord/axisTickLabelBuilder.js createAxisTicks) — so a
  // line this axis draws can never land off a tick.
  axisTick: { show: boolean, customValues?: number[] }
}

export const buildWaferAxis = (
  grid: boolean,
  axisMax: number,
  pitchMm: number,
  color: string,
  // Required, deliberately: an `= 0` default let the only production call site
  // omit the offset silently, so the axis indexed the unshifted grid while the
  // die-grid overlay drew the shifted one. Dropping the default makes that
  // omission a type error. (`nuxt typecheck` covers *.test.ts too, so the tests
  // pass 0 explicitly because they must, not merely by convention.)
  offsetMm: number
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
  // Empty when the pitch is unknown or degenerate — the same condition under
  // which the boundary overlay draws nothing, so the two can't both go blank
  // and leave "격자" showing no grid at all.
  const centres = dieCentreTicks(pitchMm, axisMax, offsetMm)
  const cfg: WaferAxisConfig = {
    type: 'value',
    min: -axisMax,
    max: axisMax,
    // Lines only when nobody else is drawing them; see the header note.
    splitLine: { show: centres.length === 0, lineStyle: { color, opacity: 0.22 } },
    axisLabel: {
      show: true,
      color,
      fontSize: 9,
      formatter: (v: number) => {
        const i = mmToDieIndex(v, pitchMm, offsetMm)
        return i == null ? String(Math.round(v)) : String(i)
      }
    },
    axisLine: { show: false },
    axisTick: { show: true }
  }
  if (centres.length > 0) {
    cfg.axisLabel.customValues = centres
    cfg.axisTick.customValues = centres
  }
  return cfg
}
