// Skewvoir set-scope FDC: the run × channel status matrix.
//
// One column per RUN (=MSR) in the curated set, one row per FDC channel, and at
// each intersection that run's raw channel mean coloured by a peer-relative
// status computed WITHIN that channel. It is the
// set-scope counterpart to the single-MSR sparkline matrix (paramMatrix.ts) and
// answers a different question: not "how does this channel move across a
// measurement" but "which channels were off, and on which runs".
//
// GRAIN — why this view needs no reduction, and therefore distorts nothing.
// `fdc_params` is ALREADY one summary per MSR: the backend emits exactly one
// FdcParamSummary per channel per msr_file response, so a cell here is a whole
// run's summary against the same channel in peer runs. Channel names are the
// comparison boundary: Contrast never shares a centre or scale with Brightness
// or Stigma. Nothing is pooled or folded ACROSS channels. The sequence-grain
// sibling `dynamic_fdc` is DELIBERATELY
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
import type { FdcCategory, FdcParamSummary } from '~/composables/useMsrFileApi'
import { peerVerdicts } from '../anomaly/peer.ts'
import {
  DEFAULT_METHOD_CONFIG,
  DEFAULT_STDDEV,
  PEER_MIN_N,
  type MethodConfig
} from '../anomaly/types.ts'
import { fdcCategoryLabels } from './paramMatrix.ts'

export type FdcSetStatus = 'ok' | 'warning' | 'bad' | 'insufficient'

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
  insufficient: number
  /** Channels present SOMEWHERE in the set but not in this run. */
  missing: number
}

/** One (run, channel) intersection. A discriminated union rather than three
 * loose nullables: `present: false` means THIS run's response carried no such
 * channel, and making the absent case its own variant is what stops a later
 * edit from reading a `rawValue` that is only nominally there — the blank
 * cell can never quietly become a 0. */
export type FdcSetCell
  = | {
    present: true
    status: FdcSetStatus
    /** Raw per-run mean in this channel's own unit. */
    rawValue: number
    /** Signed leave-one-out score. Null for insufficient or zero-spread peers. */
    peerSigma: number | null
    reason: string
  }
  | { present: false, status: null, rawValue: null, peerSigma: null, reason: null }

export interface FdcSetChannel {
  name: string
  category: FdcCategory
  unit: string
  /** Aligned one-per-run to `FdcSetMatrix.runs`, in that order. */
  cells: FdcSetCell[]
  /** Worst status across the runs that CARRY this channel; null when none do. */
  worstStatus: FdcSetStatus | null
  /** Largest absolute peer-relative score; null when none are evaluable. */
  maxAbsPeerSigma: number | null
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

const ABSENT: FdcSetCell = {
  present: false,
  status: null,
  rawValue: null,
  peerSigma: null,
  reason: null
}

export const FDC_SET_POLICY = Object.freeze({
  minMeasurements: PEER_MIN_N.stddev,
  watchSigma: DEFAULT_STDDEV.watchK,
  abnormalSigma: DEFAULT_STDDEV.abnormalK
})

const FDC_PEER_CONFIG: MethodConfig = {
  ...DEFAULT_METHOD_CONFIG,
  method: 'stddev',
  stddev: {
    watchK: FDC_SET_POLICY.watchSigma,
    abnormalK: FDC_SET_POLICY.abnormalSigma
  }
}

const STATUS_BY_SEVERITY = {
  normal: 'ok',
  watch: 'warning',
  abnormal: 'bad'
} as const

/** Severity order. An absent channel ranks below `ok`: "we never saw it" is
 * weaker evidence than "we saw it and it was fine", and must not outrank it. */
const SEVERITY: Record<FdcSetStatus, number> = { insufficient: 0, ok: 1, warning: 2, bad: 3 }
const severityOf = (status: FdcSetStatus | null): number => (status ? SEVERITY[status] : 0)

/** Strongest evidence first — the same reading order the single-scope matrix
 * uses for its 검토 근거 ranking (paramMatrix.ts `byCdRelation`), with severity
 * standing in for |r|. Name is the stable tie-break so identical channels never
 * swap places between renders. */
const byEvidence = (a: FdcSetChannel, b: FdcSetChannel): number => {
  const sa = severityOf(a.worstStatus), sb = severityOf(b.worstStatus)
  if (sa !== sb) return sb - sa
  const da = a.maxAbsPeerSigma ?? -1, db = b.maxAbsPeerSigma ?? -1
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
    const summaries = runs.map(r => entry.byMsr.get(r.msr))
    const values = summaries.map(summary => summary?.mean ?? Number.NaN)
    const verdicts = peerVerdicts(values, {
      config: FDC_PEER_CONFIG,
      metric: name,
      tag: name,
      minN: FDC_SET_POLICY.minMeasurements
    })
    const cells = summaries.map<FdcSetCell>((p, i) => {
      if (!p) return ABSENT
      const verdict = verdicts[i]!
      if (verdict.status === 'insufficient' || (verdict.peerStd === 0 && verdict.score !== 0)) {
        return {
          present: true,
          status: 'insufficient',
          rawValue: p.mean,
          peerSigma: null,
          reason: verdict.status === 'insufficient'
            ? verdict.reason
            : `${name} 나머지 측정의 표준편차가 0이라 상대 σ를 계산할 수 없습니다.`
        }
      }
      return {
        present: true,
        status: STATUS_BY_SEVERITY[verdict.severity],
        rawValue: p.mean,
        peerSigma: verdict.score,
        reason: verdict.reason
      }
    })
    const peerScores = cells.flatMap(c => (c.present && c.peerSigma != null ? [Math.abs(c.peerSigma)] : []))
    group.channels.push({
      name,
      category: entry.category,
      unit: entry.unit,
      cells,
      worstStatus: cells.reduce<FdcSetStatus | null>((worst, cell) => {
        if (!cell.present) return worst
        if (worst == null) return cell.status
        return severityOf(cell.status) > severityOf(worst) ? cell.status : worst
      }, null),
      maxAbsPeerSigma: peerScores.length ? Math.max(...peerScores) : null
    })
    groups.set(entry.category, group)
  }

  for (const group of groups.values()) group.channels.sort(byEvidence)

  const channels = [...groups.values()].flatMap(g => g.channels)

  return {
    runs: runs.map((r, i) => {
      const column: FdcSetRunColumn = {
        msr: r.msr,
        label: r.label,
        bad: 0,
        warning: 0,
        ok: 0,
        insufficient: 0,
        missing: 0
      }
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
