import type { ToolType } from '~/stores/navigation'
// Relative and WITH the .ts extension: that is what node's ESM resolver needs
// under `node --test`, and it is the form every runtime util-to-util import in
// this directory already uses (e.g. boxplotStats.ts -> './stats.ts').
import { classifyToolType } from './toolType.ts'

// Mirrors PendingToolRow in back_dev_home/sem_list/contracts.py. No
// `available` or `version`: both come from Redis keys a pending tool is not
// in yet, so there is no value the office could supply.
export interface PendingToolRow {
  fac_id: string
  eqp_id: string
  eqp_model_cd: string
  eqp_grp_id: string
  vendor_nm: string
  eqp_ip: string
  fab_name: string
  // The tool's first arrival at the fab, NOT a roster-update time.
  updt_dt: string
}

// Displayed in place of an empty fab_name. A roster entry can precede its fab
// assignment, and dropping those rows would hide tools from the one screen
// meant to surface them.
export const UNASSIGNED_FAB = '미배정'

// classifyToolType returns null for any prefix it does not know. A model the
// company installs next year will not be in that list, so this bucket is what
// stands between a new tool type and silent invisibility here.
export const UNCLASSIFIED = 'unclassified'

// A tool that arrived more than this long ago and is still unreachable is more
// likely decommissioned than awaiting a firewall exception. Weakly grounded —
// revisit once the screen has real use. Rows past it are de-emphasized, never
// hidden and never dropped from the IP list.
export const STALE_ARRIVAL_DAYS = 180

const MS_PER_DAY = 86_400_000

export type PendingToolGroup = ToolType | typeof UNCLASSIFIED

export interface PendingToolMatrix {
  fabs: string[]
  models: string[]
  // counts[fabIndex][modelIndex], aligned to `fabs` and `models`.
  counts: number[][]
  fabTotals: number[]
  modelTotals: number[]
  total: number
}

// Numeric collation so M9A sorts before M11A. A plain sort puts "M11A" first
// because "1" < "9" lexically, which reads as a bug in a fab column.
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

// Module-local, not exported: `app/utils/` is Nuxt auto-imported, and
// `pages/afm/[tool]/index.vue` already declares its own local `fabLabel` —
// exporting ours would put a colliding name into every component's implicit
// scope.
const fabLabel = (fabName: string): string => fabName.trim() || UNASSIGNED_FAB

export const groupOf = (row: PendingToolRow): PendingToolGroup =>
  classifyToolType(row.eqp_model_cd) ?? UNCLASSIFIED

export const countByGroup = (rows: PendingToolRow[]): Map<PendingToolGroup, number> => {
  const counts = new Map<PendingToolGroup, number>()
  for (const row of rows) {
    const group = groupOf(row)
    counts.set(group, (counts.get(group) ?? 0) + 1)
  }
  return counts
}

export const filterByGroup = (
  rows: PendingToolRow[],
  group: PendingToolGroup | 'all'
): PendingToolRow[] => (group === 'all' ? rows : rows.filter(row => groupOf(row) === group))

// 미배정 sorts last regardless of collation: it is a bucket, not a fab, and
// leaving it interleaved alphabetically makes it look like one.
const compareFabs = (left: string, right: string): number => {
  if (left === UNASSIGNED_FAB) return right === UNASSIGNED_FAB ? 0 : 1
  if (right === UNASSIGNED_FAB) return -1
  return collator.compare(left, right)
}

export const buildPendingToolMatrix = (rows: PendingToolRow[]): PendingToolMatrix => {
  const fabs = [...new Set(rows.map(row => fabLabel(row.fab_name)))].sort(compareFabs)
  const models = [...new Set(rows.map(row => row.eqp_model_cd))].sort((a, b) =>
    collator.compare(a, b)
  )

  const fabIndex = new Map(fabs.map((fab, index) => [fab, index]))
  const modelIndex = new Map(models.map((model, index) => [model, index]))

  const counts = fabs.map(() => models.map(() => 0))
  for (const row of rows) {
    const fabAt = fabIndex.get(fabLabel(row.fab_name))
    const modelAt = modelIndex.get(row.eqp_model_cd)
    if (fabAt === undefined || modelAt === undefined) continue
    counts[fabAt]![modelAt]! += 1
  }

  return {
    fabs,
    models,
    counts,
    fabTotals: counts.map(fabRow => fabRow.reduce((sum, n) => sum + n, 0)),
    modelTotals: models.map((_, at) => counts.reduce((sum, fabRow) => sum + fabRow[at]!, 0)),
    total: rows.length
  }
}

export const cellRows = (
  rows: PendingToolRow[],
  fab: string,
  model: string
): PendingToolRow[] =>
  rows.filter(row => fabLabel(row.fab_name) === fab && row.eqp_model_cd === model)

export const isStaleArrival = (updtDt: string, now: Date): boolean => {
  const arrived = Date.parse(updtDt)
  // An unparseable arrival is NOT stale. Marking it stale on a parse failure
  // would de-emphasize rows for a reason that has nothing to do with the tool.
  if (Number.isNaN(arrived)) return false
  return (now.getTime() - arrived) / MS_PER_DAY > STALE_ARRIVAL_DAYS
}

// Newline separated, which is the form a firewall request form takes. Deduped
// because two roster rows can share an ip, and IT should see each ip once.
export const ipList = (rows: PendingToolRow[]): string =>
  [...new Set(rows.map(row => row.eqp_ip.trim()).filter(ip => ip !== ''))].join('\n')

// Newest arrival first, for the drill-down table. Copies before sorting —
// callers hold the filtered `visibleRows` array and must not see it reordered
// out from under them. An unparseable updt_dt sorts last: we cannot claim it
// just arrived, and ranking unknown data ahead of a known-recent row would
// misrepresent it.
export const sortByArrivalDesc = (rows: PendingToolRow[]): PendingToolRow[] =>
  [...rows].sort((left, right) => {
    const leftAt = Date.parse(left.updt_dt)
    const rightAt = Date.parse(right.updt_dt)
    const leftKey = Number.isNaN(leftAt) ? -Infinity : leftAt
    const rightKey = Number.isNaN(rightAt) ? -Infinity : rightAt
    return rightKey - leftKey
  })
