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

// Parameter category palette — earthy 4-step gradient that lives in the
// same warm-paper family as --sk-accent. Saturated enough to read at
// stacked-bar width 80px, restrained enough to never out-shout the brand.
export const paraColors = {
  para_16: 'oklch(0.62 0.16 32)', // terracotta (heaviest weight)
  para_13: 'oklch(0.72 0.14 65)', // amber
  para_9: 'oklch(0.66 0.10 100)', // olive
  para_5: 'oklch(0.62 0.08 165)' // dusty sage (lightest weight)
} as const

export const paraColorsDark = {
  para_16: 'oklch(0.72 0.17 32)',
  para_13: 'oklch(0.80 0.14 65)',
  para_9: 'oklch(0.76 0.10 100)',
  para_5: 'oklch(0.72 0.09 165)'
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
