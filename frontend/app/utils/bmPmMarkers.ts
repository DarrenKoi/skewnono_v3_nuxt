// Pure: turn BM/PM history rows into an ECharts markLine fragment — vertical
// dashed lines at each job start on any time-x-axis trend chart. BM/PM colors
// mirror the category chips on the BM/PM tab (rose = BM, emerald = PM).

export interface BmPmEvent {
  ts: string
  category: 'BM' | 'PM'
  jobEnd: string
  note: string
}

// The concrete fragment shape (structurally assignable to a line/scatter
// series `markLine` option) — concrete so tests can assert on fields.
export interface BmPmMarkLineData {
  xAxis: number
  name: 'BM' | 'PM'
  lineStyle: { color: string }
  label: { formatter: 'BM' | 'PM', color: string }
  tooltip: { formatter: string }
}

export interface BmPmMarkLine {
  silent: boolean
  symbol: 'none'
  animation: boolean
  lineStyle: { type: 'dashed', width: number }
  label: { show: boolean, position: 'end', fontSize: number, distance: number }
  data: BmPmMarkLineData[]
}

// rose-600 / emerald-600 on light, rose-400 / emerald-400 on dark.
const LINE_COLORS = {
  light: { BM: '#e11d48', PM: '#059669' },
  dark: { BM: '#fb7185', PM: '#34d399' }
} as const

interface TableSectionLike {
  key: string
  rows: Record<string, unknown>[]
}

export const parseBmPmEvents = (tables: TableSectionLike[]): BmPmEvent[] => {
  const past = tables.find(t => t.key === 'past_work')
  if (!past) return []
  const events: BmPmEvent[] = []
  for (const row of past.rows) {
    const category = row.category
    const ts = String(row.job_starts ?? '')
    if ((category !== 'BM' && category !== 'PM') || !ts) continue
    events.push({
      ts,
      category,
      jobEnd: String(row.job_end ?? ''),
      note: String(row.engr_note ?? '')
    })
  }
  return events
}

const toEpoch = (ts: string) => new Date(ts.replace(' ', 'T')).getTime()

const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

export const bmPmMarkLine = (
  events: BmPmEvent[],
  { dark = false }: { dark?: boolean } = {}
): BmPmMarkLine | undefined => {
  const colors = dark ? LINE_COLORS.dark : LINE_COLORS.light
  const data: BmPmMarkLineData[] = events
    .filter(e => Number.isFinite(toEpoch(e.ts)))
    .map(e => ({
      xAxis: toEpoch(e.ts),
      name: e.category,
      lineStyle: { color: colors[e.category] },
      label: { formatter: e.category, color: colors[e.category] },
      tooltip: {
        formatter: `<b>${e.category}</b> ${escapeHtml(e.ts)} ~ ${escapeHtml(e.jobEnd)}`
          + `<br/>${escapeHtml(e.note)}`
      }
    }))
  if (data.length === 0) return undefined
  return {
    silent: false,
    symbol: 'none',
    animation: false,
    lineStyle: { type: 'dashed', width: 1.2 },
    label: { show: true, position: 'end', fontSize: 9, distance: 2 },
    data
  }
}
