// Health palette — warm-paper harmonized soft tints.
// Tailwind defaults (red-50 / amber-50 / green-50) clash with --sk-canvas cream,
// so we publish brand-correlated oklch tokens for lot rows + cards.

export type HealthLevel = 'red' | 'yellow' | 'green'

export interface HealthSwatch {
  tint: string
  tintDark: string
  ink: string
  inkDark: string
  edge: string
  edgeDark: string
  dot: string
}

export const healthSwatches: Record<HealthLevel, HealthSwatch> = {
  red: {
    tint: 'oklch(0.93 0.045 30)',
    tintDark: 'oklch(0.31 0.055 30)',
    ink: 'oklch(0.42 0.13 30)',
    inkDark: 'oklch(0.85 0.12 30)',
    edge: 'oklch(0.62 0.16 30)',
    edgeDark: 'oklch(0.72 0.17 30)',
    dot: 'oklch(0.60 0.18 28)'
  },
  yellow: {
    tint: 'oklch(0.94 0.055 80)',
    tintDark: 'oklch(0.32 0.05 75)',
    ink: 'oklch(0.46 0.10 70)',
    inkDark: 'oklch(0.86 0.10 80)',
    edge: 'oklch(0.66 0.13 75)',
    edgeDark: 'oklch(0.78 0.13 80)',
    dot: 'oklch(0.74 0.14 80)'
  },
  green: {
    tint: 'oklch(0.94 0.04 145)',
    tintDark: 'oklch(0.30 0.045 150)',
    ink: 'oklch(0.42 0.11 145)',
    inkDark: 'oklch(0.85 0.10 150)',
    edge: 'oklch(0.58 0.14 145)',
    edgeDark: 'oklch(0.74 0.13 150)',
    dot: 'oklch(0.62 0.13 145)'
  }
}

// Parameter category palette — an ORDINAL ramp, not four categorical hues.
// para_16 → para_5 is an ordered measurement-density scale, so a single warm
// hue (45°, the --sk-accent family) carries identity through lightness alone.
//
// The previous palette swept four hues (32/65/100/165) and was *declared* a
// "heaviest → lightest" gradient, but its lightness ran 0.62 → 0.72 → 0.66 →
// 0.62 — not monotone. That collision left para_13 and para_9 ΔE 10.2 apart in
// normal vision (the floor is 15) and ΔE 3.1 under protanopia, i.e. the same
// colour for a red-green reader. It matters most in the stacked area, where
// those two bands sit physically adjacent.
//
// Lightness is monotone here, so the ramp is colour-vision-safe by construction
// rather than by luck. Both steps pass every check in the dataviz palette
// validator (--ordinal) against --sk-surface in their respective modes.
// Keep the adjacent ΔL ≥ 0.06 if you retune — paraTrendSeries.test.ts asserts it.
export const paraColors = {
  para_16: 'oklch(0.40 0.115 45)', // darkest — most parameters
  para_13: 'oklch(0.52 0.135 45)',
  para_9: 'oklch(0.64 0.130 45)',
  para_5: 'oklch(0.76 0.100 45)' // lightest — fewest parameters
} as const

export const paraColorsDark = {
  para_16: 'oklch(0.52 0.135 45)',
  para_13: 'oklch(0.63 0.145 45)',
  para_9: 'oklch(0.74 0.115 45)',
  para_5: 'oklch(0.85 0.080 45)'
} as const

export const paraOrder = ['para_16', 'para_13', 'para_9', 'para_5'] as const

// Threshold buckets — provisional ratios from CONTEXT.md §lot-health-signal.
// Tweaked here once, consumed everywhere via classifyHealth().
export const healthThresholds = {
  yellow: 0.10,
  red: 0.20
} as const

export const classifyHealth = (violationRatio: number): HealthLevel => {
  if (violationRatio >= healthThresholds.red) return 'red'
  if (violationRatio >= healthThresholds.yellow) return 'yellow'
  return 'green'
}

export const healthOrder: Record<HealthLevel, number> = { red: 0, yellow: 1, green: 2 }
