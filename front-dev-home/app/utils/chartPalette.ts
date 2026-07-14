/**
 * Chart palette benchmarked from the "Paper Pro" (1a) design study.
 *
 * The charts previously mixed Tailwind's cool defaults (#2563eb, #dc2626, ...)
 * into a warm paper/walnut shell, so they read as pasted-in. These tones are the
 * study's: one cool anchor, a cream mid, and the brand terracotta at the hot end.
 *
 * ECharts renders to canvas and cannot resolve CSS custom properties, so this is
 * the source of truth for chart color and the --sk-chart-* tokens in main.css
 * mirror it for the SVG/DOM bits (legend swatches, wafer tiles).
 */
export const SK_CHART = {
  /** 5-stop diverging ramp, cool → paper → warm. Wafer heat, histograms, any low→high scale. */
  scale: ['#5C86AE', '#9BB6CD', '#E4D9C4', '#DB9A6B', '#C75A3C'],
  /** Primary series: lines, bars, scatter points. */
  series: '#5C86AE',
  /** Secondary series: area fills, de-emphasized points. */
  seriesSoft: '#9BB6CD',
  /** Paper mid-tone — histogram bodies, neutral bands. */
  sand: '#E4D9C4',
  /** Brand terracotta: fit lines, trend overlays, the one thing the eye should land on. */
  brand: '#C75A3C',
  /** Axis/grid furniture. */
  grid: '#E4DCCC',
  muted: '#9A8E7C',
  ink: '#15110D',
  /** Semantic states — outliers, spec limits, severity. */
  ok: '#3E8E5E',
  warn: '#C98A2E',
  bad: '#C4453B'
} as const
