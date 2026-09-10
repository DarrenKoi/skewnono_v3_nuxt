import type { MeasHistRow } from '~/composables/useMeasHistApi'
import type { ParsedQuery } from '~/utils/measHistQuery'

export interface SearchScopeItem {
  label: string
  value: string
}

export interface SelectionCoverage {
  measurements: number
  recipes: number
  lots: number
  equipment: number
}

interface SearchScopeInput {
  parsed: ParsedQuery
  range?: { start?: string, end?: string }
  retentionDays?: number
  searched: boolean
  total: number
  capped: boolean
}

const QUERY_LABELS: { field: keyof ParsedQuery, label: string }[] = [
  { field: 'eq', label: 'EQ' },
  { field: 'lot', label: 'LOT' },
  { field: 'recipe', label: 'RECIPE' },
  { field: 'msr', label: 'MSR' },
  { field: 'date', label: 'DATE' },
  { field: 'q', label: 'ANY' },
  { field: 'unknown', label: '?' }
]

export const buildSearchScopeSummary = ({
  parsed,
  range,
  retentionDays,
  searched,
  total,
  capped
}: SearchScopeInput): SearchScopeItem[] => {
  const queryItems = QUERY_LABELS.flatMap(({ field, label }) => {
    const values = parsed[field]
    return values.length ? [{ label, value: values.join(', ') }] : []
  })
  const items: SearchScopeItem[] = [...queryItems]

  if (range?.start && range.end) {
    items.push({ label: 'RANGE', value: `${range.start} → ${range.end}` })
  }
  if (retentionDays) {
    items.push({ label: 'RETENTION', value: `${retentionDays}일` })
  }
  if (searched) {
    items.push({ label: 'HITS', value: `${total}${capped ? '+' : ''}` })
  }

  return items
}

export const summarizeSelectionCoverage = (rows: MeasHistRow[]): SelectionCoverage => ({
  measurements: new Set(rows.map(row => row.msr)).size,
  recipes: new Set(rows.map(row => row.recipe_name)).size,
  lots: new Set(rows.map(row => row.lot_id)).size,
  equipment: new Set(rows.map(row => row.eqp_id)).size
})

export const summarizeRecentValues = (values: string[]): string => {
  const unique = [...new Set(values.filter(Boolean))]
  if (!unique.length) return '—'
  if (unique.length <= 2) return unique.join(', ')
  return `${unique[0]} 외 ${unique.length - 1}`
}
