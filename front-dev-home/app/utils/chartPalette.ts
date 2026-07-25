/**
 * Chart color, split by why each token exists.
 *
 * Two kinds of color end up in a chart and they answer to different masters:
 *
 *   - What a color MEANS is fixed. A low→high ramp and a spec violation encode
 *     data, so they must not shift when someone picks a different theme — a
 *     wafer map has to stay comparable across screenshots, and "bad" has to
 *     stay red. Those live here, as constants.
 *   - What a color LOOKS LIKE is presentation. Series lines, fit overlays and
 *     axis furniture carry no meaning beyond "this is series one, that is
 *     series two", so they follow the active ECharts theme. Those come from
 *     buildChartPalette() below, via the useChartPalette() composable.
 *
 * Before this split the whole set was one frozen "Paper Pro" object, so the
 * skewvoir charts stayed warm-paper blue/terracotta no matter which theme was
 * selected. ECharts renders to canvas and cannot resolve CSS custom properties,
 * which is why this is TS and not :root variables.
 */

/** 5-stop diverging ramp, cool → paper → warm. Wafer heat, histograms, any low→high scale. */
export const SK_SCALE = ['#5C86AE', '#9BB6CD', '#E4D9C4', '#DB9A6B', '#C75A3C'] as const

/** Semantic states — outliers, spec limits, severity. Never theme-driven. */
export const SK_STATE = {
  ok: '#3E8E5E',
  warn: '#C98A2E',
  bad: '#C4453B'
} as const

/**
 * Identity palette for multi-selected measurement points. Like SK_SCALE and
 * SK_STATE this is a FIXED constant, not theme-driven: a selected point's color
 * IS its identity across the wafer map, radius plot, distribution and points
 * table, so it must stay stable across themes and screenshots. Ordered
 * cool-first so the earliest picks sit farthest from the heat ramp's warm end
 * and the semantic red (SK_STATE.bad) — an identity halo must never read as
 * severity. Capped: a selection past this length falls back to a neutral tone.
 */
export const SK_SITE = [
  '#0E7C86', // teal
  '#2F6DB5', // blue
  '#7A5EC4', // violet
  '#3E8E5E', // green
  '#B2568B', // magenta
  '#5B6C8F', // slate
  '#1F9E8F', // sea green
  '#8A6D3F', // brown
  '#C98A2E', // amber
  '#B0413A' // brick (warm — last slot, only reached with many picks)
] as const

export interface ChartPalette {
  /** Primary series: lines, bars, scatter points. */
  series: string
  /** Secondary series: area fills, de-emphasized points. Same hue as `series`, softened. */
  seriesSoft: string
  /** The one thing the eye should land on — fit lines, trend overlays. */
  brand: string
  /** Neutral band/box fill sitting behind a series. */
  sand: string
  /** De-emphasized furniture: axis labels, reference lines, wafer outline. */
  muted: string
  /** Primary text drawn onto the canvas. */
  ink: string
}

const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n)))

const parse = (hex: string): [number, number, number] => {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map(c => c + c).join('') : h
  return [
    parseInt(full.slice(0, 2), 16) || 0,
    parseInt(full.slice(2, 4), 16) || 0,
    parseInt(full.slice(4, 6), 16) || 0
  ]
}

/** t=0 yields `a`, t=1 yields `b`. */
const mix = (a: string, b: string, t: number): string => {
  const [ar, ag, ab] = parse(a)
  const [br, bg, bb] = parse(b)
  const ch = (x: number, y: number) => clamp(x + (y - x) * t).toString(16).padStart(2, '0')
  return `#${ch(ar, br)}${ch(ag, bg)}${ch(ab, bb)}`
}

/**
 * Derive the presentation tokens from a theme's series palette, text color and
 * canvas tone.
 *
 * `ink` and `surface` are what make this safe in dark mode. The old constants
 * hardcoded near-black ink (#15110D) and a warm cream band, both of which
 * disappear against a dark card — the tokens are mixed toward the theme's own
 * surface instead of toward white, so they track the background either way.
 *
 * `brand` takes palette[1] rather than a fixed accent: it only has to contrast
 * with `series`, and index 1 is the color a theme itself considers most
 * distinct from index 0.
 */
export const buildChartPalette = (
  palette: readonly string[],
  ink: string,
  surface: string
): ChartPalette => {
  const series = palette[0] ?? SK_SCALE[0]
  return {
    series,
    seriesSoft: mix(series, surface, 0.42),
    brand: palette[1] ?? mix(series, ink, 0.35),
    sand: mix(ink, surface, 0.88),
    muted: mix(ink, surface, 0.55),
    ink
  }
}
