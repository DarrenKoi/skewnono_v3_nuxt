// Presentation helpers for the rule matrix (D13). Pure, framework-free —
// turn ruleEngine RuleCell selectors into human row labels / column values.
import type { NameOverride, RuleCell } from '~/utils/ruleEngine'

export const CAP_COLUMNS = [
  { key: 'WAFER', label: 'WAFER' },
  { key: 'LEVEL', label: 'LEVEL' },
  { key: 'EDGE', label: 'EDGE' },
  { key: 'EDGE_EX', label: 'EDGE_EX' },
  { key: '_other', label: '기타' }
] as const

export type CapColumn = (typeof CAP_COLUMNS)[number]
export type CapColumnKey = CapColumn['key']

const FAMILY_LABEL: Record<string, string> = {
  Core: 'Core',
  Pool: 'Pool',
  VG_RTC_Cubic: 'VG·RTC·Cubic'
}

export const familyLabel = (family?: string): string =>
  family ? (FAMILY_LABEL[family] ?? family) : ''

/** The secondary keying axis as text — phase set (Core/VG) or yield state (Pool). */
export const secondaryLabel = (cell: RuleCell): string => {
  const s = cell.selector
  if (s.phase_in && s.phase_in.length > 0) return s.phase_in.join('·')
  if (s.yield_check) return s.yield_check === 'before' ? '수율 전' : '수율 후'
  return ''
}

export const memoryOf = (cell: RuleCell): 'DRAM' | 'NAND' | null =>
  cell.selector.memory_class ?? null

/** caps[key] — number when the type applies to this cell, undefined when it doesn't
 * (also undefined if a malformed cell arrives without a caps object). */
export const capValue = (cell: RuleCell, key: CapColumnKey): number | undefined =>
  ((cell.caps ?? {}) as Record<string, number | undefined>)[key]

/** Compact human summary of a name-override (D9), e.g. "DSPT | WF | WAFER (contains) → 13". */
export const overrideLabel = (ov: NameOverride): string => {
  const patterns = ov.patterns.join(' | ')
  const target = ov.cap === null ? '면제' : `cap ${ov.cap}`
  return `${patterns} (${ov.match}) → ${target}`
}
