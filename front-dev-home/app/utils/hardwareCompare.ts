// Pure: shared helpers for the MDC/SCE multi-tool comparison picker. A picked
// tool must read the SAME color across the SCE table accent, coefficient curve,
// MDC boxplot marker, and 시계열 overlay — color IS the tool's identity in a
// multi-series view — so color assignment lives here as one deterministic source.

// Fallback ramp when the active ECharts theme exposes no (or a 1-entry) palette:
// hue-distant, mid-saturation tones that stay legible on both surfaces.
const FALLBACK_COMPARE_COLORS = [
  '#2F5D8A', '#B7791F', '#4C956C', '#A64253',
  '#6D6875', '#0F766E', '#9A6D3F', '#5B6C8F'
]

const cycle = (keys: readonly string[], ramp: readonly string[]): Record<string, string> => {
  const out: Record<string, string> = {}
  keys.forEach((key, i) => {
    out[key] = ramp[i % ramp.length]!
  })
  return out
}

// palette[0] is reserved for the selected (primary) tool everywhere, so picked
// tools cycle palette[1..]; if the theme has < 2 entries, fall back to the ramp.
export const assignCompareColors = (
  ids: readonly string[],
  palette: readonly string[]
): Record<string, string> =>
  cycle(ids, palette.length > 1 ? palette.slice(1) : FALLBACK_COMPARE_COLORS)

// Same deterministic cycling, but starting at palette[0]. For series whose
// identity is NOT a tool — SCE collection dates, say — nothing is competing for
// palette[0], so withholding it would only cost a distinct hue.
export const assignSeriesColors = (
  keys: readonly string[],
  palette: readonly string[]
): Record<string, string> =>
  cycle(keys, palette.length > 0 ? palette : FALLBACK_COMPARE_COLORS)

// Both hardware pickers filter their own list rather than letting USelectMenu
// do it, so their bulk-action buttons act on exactly the rows on screen -- one
// filter is the only way the visible set and the bulk-action target cannot
// drift apart. Nuxt UI's own matcher is not a public composable, so mirroring
// it would mean importing from dist/runtime; a substring match over the field
// it would have used is equivalent for this data.
//
// `text` picks that field, because the two callers disagree on it: tool ids are
// their own label, while an SCE revision's label ("2026-07-10~2026-07-17 · 3회")
// is not its value (a bare date key). Matching the label is what USelectMenu
// does by default (filterFields = [labelKey]), so this preserves its behaviour.
// A blank term needs no special case: every string contains ''.
export const filterByTerm = <T>(
  items: readonly T[],
  term: string,
  text: (item: T) => string
): T[] => {
  const needle = term.trim().toLowerCase()
  return items.filter(item => text(item).toLowerCase().includes(needle))
}

const toNum = (v: unknown): number | null => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

export interface CompareBoxSeries {
  id: string
  // [conditionIndex, value] pairs — ready for an ECharts scatter series aligned
  // to the same category axis as the fleet boxplot.
  values: [number, number][]
}

// Map each picked tool to its per-condition snapshot values, indexed to match
// the boxplot's `conditions` category axis. Conditions the tool lacks are
// simply omitted (no null holes), so a tool with fewer modes plots fewer points.
export const compareBoxPoints = (
  settings: Record<string, Record<string, unknown>>,
  compareIds: readonly string[],
  conditions: readonly string[]
): CompareBoxSeries[] =>
  compareIds.map((id) => {
    const toolSettings = settings[id] ?? {}
    const values: [number, number][] = []
    conditions.forEach((cond, condIdx) => {
      const v = toNum(toolSettings[cond])
      if (v !== null) values.push([condIdx, v])
    })
    return { id, values }
  })
