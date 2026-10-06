// Pure: shared helpers for the MDC/SCE multi-tool comparison picker. A picked
// tool must read the SAME color across the SCE table accent, coefficient curve,
// MDC boxplot marker, and 시계열 overlay — color IS the tool's identity in a
// multi-series view — so color assignment lives here as one deterministic source.

// Fallback ramp when the active ECharts theme exposes no (or a 1-entry) palette:
// hue-distant, mid-saturation tones that stay legible on both surfaces.
import { boxStats, type BoxStats } from './boxplotStats.ts'

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

// The service payload's `settings` map is the whole fab, every model in it.
// Narrow it to the tools the page's model gate admits — the comparison picker
// and the 비교 distribution both read their cohort off these keys, and a value
// compared across models says nothing. The selected tool always stays: it is
// the subject, and the gate already vouches for it. `allowedIds` holds
// toolIdKey() values: the settings map and the roster are written by different
// collectors, so ids are matched ignoring case and stray whitespace, as the
// office adapter matches them.
export const toolIdKey = (id: string) => id.trim().toUpperCase()

export const scopeSettings = <T>(
  settings: Record<string, T>,
  allowedIds: ReadonlySet<string>,
  selectedEqp: string
): Record<string, T> =>
  Object.fromEntries(Object.entries(settings).filter(([id]) => id === selectedEqp || allowedIds.has(toolIdKey(id))))

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

export interface ConditionToolRow {
  eqpId: string
  value: number
  // Signed gap to the fleet median for this condition — the boxplot's centre
  // line, so the table and the box it explains agree on "typical".
  delta: number
}

// Every tool's value for one beam condition, highest first — the 비교 tab's
// detail table for a clicked box. Tools lacking the condition (or holding a
// non-numeric value) are omitted, exactly as the boxplot omits them.
export const conditionToolRows = (
  settings: Record<string, Record<string, unknown>>,
  cond: string,
  median: number
): ConditionToolRow[] =>
  Object.entries(settings)
    .map(([eqpId, s]) => ({ eqpId, value: toNum(s?.[cond]) }))
    .filter((r): r is { eqpId: string, value: number } => r.value !== null)
    .map(r => ({ ...r, delta: r.value - median }))
    .sort((a, b) => b.value - a.value || a.eqpId.localeCompare(b.eqpId))

export interface ConditionBoxRow {
  cond: string
  // Tools with a numeric value for this condition — conditions differ in who
  // carries them, so every per-condition figure needs its own n.
  n: number
  stats: BoxStats | null
  mine: number | null
}

// The one pass over the fleet per beam condition, in axis order. The boxplot,
// the summary table and the detail table's median all read these rows, so
// they cannot disagree on which values count or where the median is.
export const conditionBoxRows = (
  settings: Record<string, Record<string, unknown>>,
  selectedEqp: string,
  conditions: readonly string[]
): ConditionBoxRow[] =>
  conditions.map((cond) => {
    const values = Object.values(settings).map(s => toNum(s?.[cond])).filter((v): v is number => v !== null)
    return { cond, n: values.length, stats: boxStats(values), mine: toNum(settings[selectedEqp]?.[cond]) }
  })

export interface ConditionSummary {
  cond: string
  n: number
  // Selected tool's gap to the fleet median, in ppm (null: it lacks the mode).
  minePpm: number | null
  // Fleet max − min relative to the median, in ppm.
  spreadPpm: number
}

// The 비교 tab's "where to look first" table: conditions where the selected
// tool sits furthest from the fleet median come first; conditions it lacks go
// last, widest fleet spread first. The median includes the selected tool, and
// with 4-6 tools this ranks, it does not judge.
export const conditionSummary = (rows: readonly ConditionBoxRow[]): ConditionSummary[] =>
  rows
    .flatMap(({ cond, n, stats, mine }) => stats
      ? [{
          cond,
          n,
          minePpm: mine === null ? null : (mine / stats.median - 1) * 1e6,
          spreadPpm: (stats.max - stats.min) / stats.median * 1e6
        }]
      : [])
    .sort((a, b) =>
      (a.minePpm === null ? 1 : 0) - (b.minePpm === null ? 1 : 0)
      || Math.abs(b.minePpm ?? 0) - Math.abs(a.minePpm ?? 0)
      || b.spreadPpm - a.spreadPpm)
