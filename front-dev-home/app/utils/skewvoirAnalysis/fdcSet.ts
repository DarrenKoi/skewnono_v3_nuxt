// Skewvoir set-scope FDC: the run × channel status matrix.
//
// One column per RUN (=MSR) in the curated set, one row per FDC channel, and at
// each intersection that run's `drift_sigma` coloured by its `status`. It is the
// set-scope counterpart to the single-MSR sparkline matrix (paramMatrix.ts) and
// answers a different question: not "how does this channel move across a
// measurement" but "which channels were off, and on which runs".
//
// GRAIN — why this view needs no reduction, and therefore distorts nothing.
// `fdc_params` is ALREADY one summary per MSR: the backend emits exactly one
// FdcParamSummary per channel per msr_file response, so a cell here is a whole
// run's summary against a whole run's summary. Nothing is pooled, averaged or
// folded to build it. That is the entire reason this screen could be built on
// data already in hand. The sequence-grain sibling `dynamic_fdc` is DELIBERATELY
// not read: reducing it per run would mix sequence readings into an MSR-grain
// comparison, which is the distortion features.ts exists to prevent and which
// fdcSet.test.ts pins by source grep.
//
// The mock-only `health` scalar and placeholder `spm_dict` are banned from this
// judgment path (gallery.ts §0.5). Enforced structurally, not by discipline:
// FdcSetRunSource is a narrow subset of MsrFileResponse that does not carry
// them, so they are unreachable here rather than merely unread.
//
// Pure: no Vue, no ECharts. The component that consumes this only turns the
// model into markup — ordering, grouping, roll-ups and the absent-cell rule are
// all decided here. Runs under raw `node --test` (no Nuxt, no bundler), so
// sibling imports carry an explicit `.ts` extension.
import type { FdcCategory, FdcParamSummary, FdcStatus } from '~/composables/useMsrFileApi'
import { fdcCategoryLabels } from './paramMatrix.ts'

/** One measurement (=run) contributing a column. */
export interface FdcSetRunSource {
  msr: string
  label: string
  fdc_params: FdcParamSummary[]
}

export interface FdcSetRunColumn {
  msr: string
  label: string
  bad: number
  warning: number
  ok: number
  /** Channels present SOMEWHERE in the set but not in this run. */
  missing: number
}

/** One (run, channel) intersection. A discriminated union rather than three
 * loose nullables: `present: false` means THIS run's response carried no such
 * channel, and making the absent case its own variant is what stops a later
 * edit from reading a `driftSigma` that is only nominally there — the blank
 * cell can never quietly become a 0. */
export type FdcSetCell
  = | { present: true, status: FdcStatus, driftSigma: number }
    | { present: false, status: null, driftSigma: null }

export interface FdcSetChannel {
  name: string
  category: FdcCategory
  unit: string
  /** Aligned one-per-run to `FdcSetMatrix.runs`, in that order. */
  cells: FdcSetCell[]
  /** Worst status across the runs that CARRY this channel; null when none do. */
  worstStatus: FdcStatus | null
  /** Largest drift_sigma across those same runs; null when none. */
  maxDriftSigma: number | null
}

export interface FdcSetGroup {
  category: FdcCategory
  label: string
  channels: FdcSetChannel[]
}

export interface FdcSetMatrix {
  runs: FdcSetRunColumn[]
  groups: FdcSetGroup[]
  /** Distinct channels across the whole set. */
  channelCount: number
  /** How many of those at least one run does not carry — the number the view
   * must say out loud, because a blank cell is otherwise indistinguishable
   * from a rendering fault. */
  partialChannelCount: number
}

const ABSENT: FdcSetCell = { present: false, status: null, driftSigma: null }

/** Severity order. An absent channel ranks below `ok`: "we never saw it" is
 * weaker evidence than "we saw it and it was fine", and must not outrank it. */
const SEVERITY: Record<FdcStatus, number> = { ok: 1, warning: 2, bad: 3 }
const severityOf = (status: FdcStatus | null): number => (status ? SEVERITY[status] : 0)

/** Strongest evidence first — the same reading order the single-scope matrix
 * uses for its 검토 근거 ranking (paramMatrix.ts `byCdRelation`), with severity
 * standing in for |r|. Name is the stable tie-break so identical channels never
 * swap places between renders. */
const byEvidence = (a: FdcSetChannel, b: FdcSetChannel): number => {
  const sa = severityOf(a.worstStatus), sb = severityOf(b.worstStatus)
  if (sa !== sb) return sb - sa
  const da = a.maxDriftSigma ?? -1, db = b.maxDriftSigma ?? -1
  if (da !== db) return db - da
  return a.name.localeCompare(b.name)
}

export const buildFdcSetMatrix = (runs: FdcSetRunSource[]): FdcSetMatrix => {
  // channel name → its per-run summaries, keyed by msr.
  const byName = new Map<string, { category: FdcCategory, unit: string, byMsr: Map<string, FdcParamSummary> }>()
  for (const r of runs) {
    for (const p of r.fdc_params) {
      const entry = byName.get(p.name)
        ?? { category: p.category, unit: p.unit, byMsr: new Map<string, FdcParamSummary>() }
      entry.byMsr.set(r.msr, p)
      byName.set(p.name, entry)
    }
  }

  const labels = fdcCategoryLabels(runs.flatMap(r => r.fdc_params))

  const groups = new Map<FdcCategory, FdcSetGroup>()
  for (const [name, entry] of byName) {
    const group = groups.get(entry.category)
      ?? { category: entry.category, label: labels.get(entry.category) ?? entry.category, channels: [] }
    const cells = runs.map<FdcSetCell>((r) => {
      const p = entry.byMsr.get(r.msr)
      return p ? { present: true, status: p.status, driftSigma: p.drift_sigma } : ABSENT
    })
    const drifts = cells.flatMap(c => (c.present ? [c.driftSigma] : []))
    group.channels.push({
      name,
      category: entry.category,
      unit: entry.unit,
      cells,
      worstStatus: cells.reduce<FdcStatus | null>(
        (worst, c) => (severityOf(c.status) > severityOf(worst) ? c.status : worst), null
      ),
      maxDriftSigma: drifts.length ? Math.max(...drifts) : null
    })
    groups.set(entry.category, group)
  }

  for (const group of groups.values()) group.channels.sort(byEvidence)

  const channels = [...groups.values()].flatMap(g => g.channels)

  return {
    runs: runs.map((r, i) => {
      const column: FdcSetRunColumn = { msr: r.msr, label: r.label, bad: 0, warning: 0, ok: 0, missing: 0 }
      for (const channel of channels) {
        const cell = channel.cells[i]
        if (cell?.present) column[cell.status]++
        else column.missing++
      }
      return column
    }),
    groups: [...groups.values()],
    channelCount: byName.size,
    partialChannelCount: channels.filter(c => c.cells.some(cell => !cell.present)).length
  }
}
