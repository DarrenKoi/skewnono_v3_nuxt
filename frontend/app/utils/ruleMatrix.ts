// Presentation helpers for the rule matrix (D13). Pure, framework-free —
// turn ruleEngine RuleCell selectors into human row labels / column values.
import type { NameOverride, RuleCell } from '~/utils/ruleEngine'

// WAFER/LEVEL caps are fab-wide constants (13/4, never edited), so they render
// once as a fixed strip above the matrix. Only the axes that vary per cell
// stay as columns.
export const CAP_COLUMNS = [
  { key: 'EDGE', label: 'EDGE' },
  { key: 'EDGE_EX', label: 'EDGE_EX' },
  { key: '_other', label: '기타' }
] as const

export type CapColumn = (typeof CAP_COLUMNS)[number]
export type CapColumnKey = CapColumn['key']

const FIXED_CAP_KEYS = ['WAFER', 'LEVEL'] as const

export interface FixedCap { key: string, value: number }

/** Caps holding one value across every cell (WAFER 13 · LEVEL 4). A key that
 * ever diverges is dropped from the strip, so a future per-cell split cannot
 * be masked by a stale "fixed" label. */
export const fixedCaps = (cells: RuleCell[]): FixedCap[] => {
  const out: FixedCap[] = []
  for (const key of FIXED_CAP_KEYS) {
    const value = cells[0]?.caps?.[key]
    if (value === undefined) continue
    if (cells.every(cell => cell.caps?.[key] === value)) out.push({ key, value })
  }
  return out
}

const FAMILY_LABEL: Record<string, string> = {
  Core: 'Core',
  Pool: 'Pool',
  VG_RTC_Cubic: 'VG·RTC·Cubic'
}

export const familyLabel = (family?: string): string =>
  family ? (FAMILY_LABEL[family] ?? family) : ''

export interface VehicleLabel { main: string, hint?: string }

/** The secondary keying axis, collapsed for display: phase sets show as just
 * EV/TV ("EV 포함 이전" · "TV 포함 이후"); Pool keeps its yield split. */
export const vehicleLabel = (cell: RuleCell): VehicleLabel => {
  const s = cell.selector
  if (s.phase_in && s.phase_in.length > 0) {
    return s.phase_in.includes('TV') || s.phase_in.includes('PV')
      ? { main: 'TV', hint: '포함 이후' }
      : { main: 'EV', hint: '포함 이전' }
  }
  if (s.yield_check) return { main: s.yield_check === 'before' ? '수율 전' : '수율 후' }
  return { main: '' }
}

/** Cells whose EDGE/EDGE_EX caps open up beyond the EV baseline (TV 포함 이후,
 * Pool 수율 후) — the matrix highlights these, since that is the whole point
 * of the phase split. */
export const isExpandedCell = (cell: RuleCell): boolean => {
  const s = cell.selector
  if (s.phase_in?.some(p => p === 'TV' || p === 'PV')) return true
  return s.yield_check === 'after'
}

export const memoryOf = (cell: RuleCell): 'DRAM' | 'NAND' | null =>
  cell.selector.memory_class ?? null

/** caps[key] — number when the type applies to this cell, undefined when it doesn't
 * (also undefined if a malformed cell arrives without a caps object). */
export const capValue = (cell: RuleCell, key: CapColumnKey): number | undefined =>
  ((cell.caps ?? {}) as Record<string, number | undefined>)[key]

/** Every distinct name-override across a set of cells (by signature) —
 * robust if a group ever holds mixed overrides. */
export const collectOverrides = (cells: RuleCell[]): NameOverride[] => {
  const seen = new Set<string>()
  const out: NameOverride[] = []
  for (const cell of cells) {
    for (const ov of cell.name_overrides ?? []) {
      const sig = JSON.stringify(ov)
      if (seen.has(sig)) continue
      seen.add(sig)
      out.push(ov)
    }
  }
  return out
}

/** Compact human summary of a name-override (D9), e.g. "DSPT | WF | WAFER (contains) → 13". */
export const overrideLabel = (ov: NameOverride): string => {
  const patterns = ov.patterns.join(' | ')
  const target = ov.cap === null ? '면제' : `cap ${ov.cap}`
  return `${patterns} (${ov.match}) → ${target}`
}
