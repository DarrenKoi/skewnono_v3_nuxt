// Symbol sizing for click-to-select trend charts.
//
// The symbol is the click target — ECharts only fires a series 'click' on a hit
// against the rendered element — so dots want to be as large as the pointer
// needs. What stops them is neighbours: a quarter of BSM docs (180+) in one of
// BsmPanel's side-by-side panes leaves ~4px per point, and a 9px dot there
// fuses the series into a solid band that hides the line.
//
// Point count alone cannot decide this: 120 points is roomy across a full-width
// panel and cramped in a half-width one. Spacing knows about both.

// Below this, dots stop reading as marks and start reading as line thickness.
const MIN_SYMBOL = 5
// Above this, a sparse series turns into balloons.
const MAX_SYMBOL = 11
// Used until a ResizeObserver has measured the host.
export const UNMEASURED_SYMBOL = 6

// `plotWidth` is the grid's inner width in CSS px (host width minus grid
// margins), `count` the number of points drawn across it. Returns the largest
// dot that still leaves the line visible between neighbours.
export const trendSymbolSize = (plotWidth: number, count: number): number => {
  if (count <= 0 || plotWidth <= 0) return UNMEASURED_SYMBOL
  // 0.9 of the per-point share: neighbours touch at worst, never overlap.
  const fitted = (plotWidth / count) * 0.9
  return Math.round(Math.min(MAX_SYMBOL, Math.max(MIN_SYMBOL, fitted)))
}
