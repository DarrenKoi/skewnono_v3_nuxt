// Skewvoir 검토 영수증 (S8) — what was compared against what, and the numbers
// found, as a file that outlives the measurements behind it.
//
// A shared link is a live re-query and the pickles it reads are deleted at 61
// days, so a link cannot keep a conclusion. The receipt carries the numbers
// themselves: 생성 시각 기준 수치.
//
// It records differences and sample sizes — never a judgement. No spec, no
// Cp/Cpk, no pass/fail: measurementVerdict's badge is deliberately not in here.
//
// Two steps on purpose. `buildReviewReceipt` returns the receipt OBJECT (the
// shape a later consumer reads); `receiptSheets` lays that object out as rows.
// Writing the .xlsx is utils/xlsx.ts's job — nothing here touches the DOM.
//
// REUSE, do not re-derive: every number below comes from the function that
// already owns it on screen (cduMetrics, overviewSites, baselineComparison,
// baselineDeltaMap, compositeSiteMap, acrossMsrAxes). A statistic that exists only inside a
// component is NOT copied here — it is left out of the receipt.
//
// Runs under raw `node --test` — sibling imports carry an explicit `.ts`.
import type { MeasHistRow } from '~/composables/useMeasHistApi'
import type { MsrFileResponse } from '~/composables/useMsrFileApi'
import type { SkewvoirSelection } from '~/composables/useSkewvoirWorkspace'
import type { WorkbookSheet } from '../xlsx.ts'
import type { MethodConfig, ScoringMethod } from '../anomaly/types.ts'
import type { SharedRadialModel } from './routeQuery.ts'
import type { AnalysisScope, ExclusionEntry, TsBaseline } from './types.ts'
import type { FeatureDefinition, MsrFeatureRow } from './features.ts'
import type { ToolSkewResult } from './timeSeries.ts'
import { overviewSites, type SiteKind } from '../overview.ts'
import { MODEL_LABEL } from '../radialAnalysis.ts'
import { formatRecipeTimestamp } from '../recipeView.ts'
import { safeFileNamePart } from '../tableExport.ts'
import { acrossMsrAxes, acrossMsrAxisValue, type AcrossMsrAxis } from './acrossMsr.ts'
import {
  baselineComparison, baselineDeltaMap, baselineSentence, compositeSiteMap,
  type BaselineComparison, type CompositeSite
} from './baselineCompare.ts'
import { cduMetrics, type CduMetrics } from './cdu.ts'
import { EXCLUSION_REASON_LABEL } from './compatibility.ts'
import { isSetPoolComplete } from './curatedSet.ts'

export const RECEIPT_CAUTION
  = '원본 파일은 61일 뒤 삭제됩니다. URL 은 다시 계산하는 주소이며 수치는 생성 시각 기준입니다.'

export interface ReceiptInput {
  generatedAt: Date
  toolLabel: string
  scope: AnalysisScope
  selection: Pick<SkewvoirSelection, 'msr' | 'lot' | 'recipe' | 'eq' | 'capturedAt'>
  /** The row-filter key (`activeParam`) and its display form. */
  parameter: string
  parameterLabel: string
  unit: string
  msrList: readonly string[]
  rowByMsr: ReadonlyMap<string, Pick<MeasHistRow, 'lot_id' | 'eqp_id' | 'timestamp' | 'recipe_name'>>
  focusFile: MsrFileResponse | null
  setFiles: ReadonlyMap<string, MsrFileResponse>
  /** `manifest.excluded`. */
  excluded: readonly ExclusionEntry[]
  /** `analysis.baselineGroups` — an empty `base` means no baseline was set. */
  baselineGroups: { base: readonly string[], target: readonly string[] }
  /** `analysis.siteDeltaReady` — false when the included measurements do not
   *  share a physical layout, so a chip index is not one site across them.
   *  Absent means comparable (a single measurement has nothing to pair). */
  siteDeltaReady?: boolean
  anomalyCfg: MethodConfig
  radialModel: SharedRadialModel
  tsBaseline: TsBaseline
  toolSkew: ToolSkewResult
  featureRows: readonly MsrFeatureRow[]
  featureRegistry: readonly FeatureDefinition[]
  shareUrl: string
  memo: string
}

export type ReceiptRole = '기준' | '대상' | '포함' | '제외'

export interface ReceiptMember {
  msr: string
  lot: string
  eqp: string
  /** As skewvoir displays it (formatRecipeTimestamp) — no time-zone conversion. */
  capturedAt: string
  recipe: string
  role: ReceiptRole
  /** Why a 제외 member is out; '' otherwise. */
  reason: string
  /** null for a 제외 member: its numbers took part in nothing. */
  metrics: CduMetrics | null
  /** Sites flagged 주의/이상 under `settings`; null when too few sites to judge. */
  outlierCount: number | null
}

export interface ReceiptFlaggedSite {
  msr: string
  sequence: number
  chip: string
  cd: number | null
  /** Signed deviation from the sibling sites, in the anomaly method's unit. */
  delta: number | null
  kind: string
}

export interface ReviewReceipt {
  /** `YYYY-MM-DD HH:mm`, the viewer's clock. */
  generatedAt: string
  selection: { toolType: string, recipe: string, parameter: string, unit: string, scope: AnalysisScope, focusMsr: string }
  settings: { anomalyMethod: ScoringMethod, watch: number, abnormal: number, radialModel: SharedRadialModel, tsBaseline: TsBaseline }
  members: ReceiptMember[]
  /** S7. null when no baseline is set — the receipt is still valid without it. */
  baseline: (BaselineComparison & {
    sentence: string
    /** Per chip site, target mean − baseline mean. */
    deltaSites: [number, number, number][]
    /** Sites only one of the two groups measured. */
    unpaired: number
    /** False when the layouts disagree: no per-site delta is recorded. */
    siteDeltaReady: boolean
  }) | null
  /** 위치 비교's set-scope composite maps, one row per chip. null in single
   *  scope; `ready: false` (and no sites) when the layouts are not known to agree. */
  position: { ready: boolean, sites: CompositeSite[] } | null
  flaggedSites: ReceiptFlaggedSite[]
  toolSkew: ToolSkewResult
  /** One row per loaded measurement, one value per across-MSR axis. */
  features: { axes: AcrossMsrAxis[], rows: { msr: string, values: (number | null)[] }[] }
  memo: string
  url: string
  caution: string
}

const KIND_LABEL: Record<SiteKind, string> = { abnormal: '이상', watch: '주의', failed: '측정 실패' }

const pad = (n: number) => String(n).padStart(2, '0')

export const buildReviewReceipt = (input: ReceiptInput): ReviewReceipt => {
  const { parameter, unit, anomalyCfg: cfg } = input
  const d = input.generatedAt

  // The focus file stands in where there is no set batch — single scope ONLY.
  // In set scope the screen computes over the set files alone (a focus the
  // 30-member cap dropped is not among them), and the receipt must not record a
  // comparison the screen could not show.
  const files = new Map(input.setFiles)
  if (input.scope === 'single' && input.focusFile) files.set(input.focusFile.msr, input.focusFile)

  const excluded = new Map(input.excluded.map(e => [e.msr, e.reasons]))
  const base = new Set(input.baselineGroups.base)
  const hasBaseline = base.size > 0

  const flaggedSites: ReceiptFlaggedSite[] = []
  const members = input.msrList.map((msr): ReceiptMember => {
    const row = input.rowByMsr.get(msr)
    const sel = msr === input.selection.msr ? input.selection : null
    const identity = {
      msr,
      lot: row?.lot_id ?? sel?.lot ?? '',
      eqp: row?.eqp_id ?? sel?.eq ?? '',
      capturedAt: row ? formatRecipeTimestamp(row.timestamp) : sel?.capturedAt ?? '',
      recipe: row?.recipe_name ?? sel?.recipe ?? ''
    }
    const file = files.get(msr)
    const reasons = excluded.get(msr)
    if (!file || reasons) {
      return {
        ...identity,
        role: '제외',
        reason: file ? reasons!.map(r => EXCLUSION_REASON_LABEL[r]).join(', ') : '파일을 불러오지 못했습니다',
        metrics: null,
        outlierCount: null
      }
    }
    const overview = overviewSites(file.rows, parameter, cfg)
    for (const s of overview.tableRows) {
      flaggedSites.push({ msr, sequence: s.sequence, chip: s.chip, cd: s.cd, delta: s.delta, kind: KIND_LABEL[s.kind] })
    }
    return {
      ...identity,
      role: hasBaseline ? (base.has(msr) ? '기준' : '대상') : '포함',
      reason: '',
      metrics: cduMetrics(file.rows, parameter, unit),
      outlierCount: overview.status === 'evaluated' ? overview.outlierCount : null
    }
  })

  const siteDeltaReady = input.siteDeltaReady ?? true
  let baseline: ReviewReceipt['baseline'] = null
  if (hasBaseline) {
    const { base: baseIds, target } = input.baselineGroups
    const result = baselineComparison(files, baseIds, target, parameter, unit)
    const delta = siteDeltaReady
      ? baselineDeltaMap(files, baseIds, target, parameter)
      : { points: [], unpaired: 0 }
    baseline = { ...result, sentence: baselineSentence(result), deltaSites: delta.points, unpaired: delta.unpaired, siteDeltaReady }
  }

  // Only the measurements that took part: a 제외 member's features must not
  // stand beside the others as if they were comparable.
  const compared = new Set(members.filter(m => m.role !== '제외').map(m => m.msr))
  const axes = acrossMsrAxes(input.featureRegistry)

  return {
    generatedAt: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`,
    selection: {
      toolType: input.toolLabel,
      recipe: input.selection.recipe,
      parameter: input.parameterLabel,
      unit,
      scope: input.scope,
      focusMsr: input.selection.msr
    },
    settings: {
      anomalyMethod: cfg.method,
      watch: cfg.method === 'range' ? cfg.range.watchPct : cfg.stddev.watchK,
      abnormal: cfg.method === 'range' ? cfg.range.abnormalPct : cfg.stddev.abnormalK,
      radialModel: input.radialModel,
      tsBaseline: input.tsBaseline
    },
    members,
    baseline,
    position: input.scope === 'set'
      ? { ready: siteDeltaReady, sites: siteDeltaReady ? compositeSiteMap(files, [...compared], parameter) : [] }
      : null,
    flaggedSites,
    toolSkew: input.toolSkew,
    features: {
      axes,
      rows: input.featureRows
        .filter(row => compared.has(row.msr))
        .map(row => ({ msr: row.msr, values: axes.map(a => acrossMsrAxisValue(row, a.id)?.value ?? null) }))
    },
    memo: input.memo.trim(),
    url: input.shareUrl,
    caution: RECEIPT_CAUTION
  }
}

// ── Sheets ───────────────────────────────────────────────────────────────

type Cell = string | number

/** Four decimals — one more than the screen shows, and no float residue. An
 *  absent number is an empty cell, never a 0. */
const num = (v: number | null | undefined): Cell =>
  v == null || !Number.isFinite(v) ? '' : Number(v.toFixed(4))

const TS_BASELINE_LABEL: Record<TsBaseline, string> = { raw: '측정값', resid: '잔차' }

export const receiptSheets = (r: ReviewReceipt): WorkbookSheet[] => {
  const u = r.selection.unit ? ` (${r.selection.unit})` : ''
  const range = r.settings.anomalyMethod === 'range'
  const threshold = (v: number) => (range ? `±${v}%` : `±${v}σ`)
  const identity = new Map(r.members.map(m => [m.msr, m]))

  const sheets: WorkbookSheet[] = [
    {
      name: '요약',
      rows: [
        ['항목', '값'],
        ['생성 시각', r.generatedAt],
        ['장비 타입', r.selection.toolType],
        ['Recipe', r.selection.recipe],
        ['파라미터', r.selection.parameter],
        ['단위', r.selection.unit],
        ['분석 범위', r.selection.scope === 'set' ? `세트 비교 · ${r.members.length}건` : '단일 측정'],
        ['Focus MSR', r.selection.focusMsr],
        ['이상 판정 방식', range ? '범위(%)' : '표준편차(σ)'],
        ['주의 기준', threshold(r.settings.watch)],
        ['이상 기준', threshold(r.settings.abnormal)],
        ['반경 fit 차수', MODEL_LABEL[r.settings.radialModel]],
        ['Time-Series 값 기준', TS_BASELINE_LABEL[r.settings.tsBaseline]],
        ...(r.baseline
          ? [['기준 대비', r.baseline.sentence], ['기준 성격', '이 세트 안에서 손으로 나눈 기준이며 공식 기준선이 아닙니다.']]
          : [['기준 대비', '기준을 지정하지 않았습니다.']]),
        ...(r.position && !r.position.ready
          ? [['위치 합성', '같은 위치임을 확인할 수 없어 site 단위로 합치지 않았습니다']]
          : []),
        ['메모', r.memo],
        ['주의', r.caution],
        ['분석 URL', r.url]
      ]
    },
    {
      name: '세트',
      rows: [
        ['MSR', 'Lot', '장비', '측정 시각', 'Recipe', '역할', '제외 사유', 'site', '미측정', '전체',
          `mean${u}`, `median${u}`, `std${u}`, `3σ${u}`, `MAD σ${u}`, `range${u}`, '주의·이상 site'],
        ...r.members.map((m): Cell[] => {
          const c = m.metrics
          return [
            m.msr, m.lot, m.eqp, m.capturedAt, m.recipe, m.role, m.reason,
            num(c?.n), num(c?.missing), num(c?.total),
            num(c?.level?.mean), num(c?.level?.median),
            num(c?.spread?.std), num(c?.spread?.threeSigma), num(c?.spread?.madSigma), num(c?.spread?.range),
            num(m.outlierCount)
          ]
        })
      ]
    }
  ]

  const b = r.baseline
  if (b) {
    const sideRow = (label: string, s: BaselineComparison['base']): Cell[] => [
      label, s.msrs.length, s.pooled.n,
      num(s.pooled.level?.mean), num(s.pooled.level?.median),
      num(s.pooled.spread?.threeSigma), num(s.pooled.spread?.range), num(s.dominance)
    ]
    const c = b.comparison
    sheets.push({
      name: '기준 대비',
      rows: [
        ['구분', '측정', 'site', `mean${u}`, `median${u}`, `3σ${u}`, `range${u}`, '최대 측정 비중'],
        sideRow('기준', b.base),
        sideRow('대상', b.target),
        ...(c
          ? [
              ['대상 − 기준', '', '', num(c.shift), '', '', num(c.rangeDelta), ''],
              ['기준 3σ 대비 평균 이동(배)', num(c.shiftInBaseSigma)],
              ['3σ 배율(대상/기준)', num(c.threeSigmaRatio)],
              b.siteDeltaReady
                ? ['공통 측정점이 없는 chip', b.unpaired]
                : ['site별 비교', '같은 위치임을 확인할 수 없어 site 단위로 비교하지 않았습니다']
            ]
          : [['평가 불가', b.reason ?? '']])
      ]
    })
    if (b.deltaSites.length) {
      sheets.push({ name: '기준 대비 site', rows: [['chip X', 'chip Y', `대상 − 기준${u}`], ...b.deltaSites] })
    }
  }

  if (r.position?.sites.length) {
    sheets.push({
      name: '위치 합성 site',
      rows: [
        ['chip X', 'chip Y', '측정점', 'wafer', `mean${u}`, `σ${u}`],
        ...r.position.sites.map(s => [s.x, s.y, s.mps, s.wafers, num(s.mean), num(s.sigma)])
      ]
    })
  }

  if (r.toolSkew.rows.length) {
    sheets.push({
      name: '장비 skew',
      rows: [
        ['장비', 'n', `평균${u}`, `${r.toolSkew.recipes > 1 ? 'recipe별 기준' : '세트 기준'} 대비${u}`, `σ${u}`],
        ...r.toolSkew.rows.map(t => [t.eqpId, t.n, num(t.mean), num(t.offset), num(t.sigma)])
      ]
    })
  }

  // One measurement is not an across-MSR table.
  if (r.features.rows.length > 1 && r.features.axes.length) {
    sheets.push({
      name: 'MSR별 지표',
      rows: [
        ['MSR', 'Lot', '장비', ...r.features.axes.map(a => (a.unit ? `${a.label} (${a.unit})` : a.label))],
        ...r.features.rows.map(f => [f.msr, identity.get(f.msr)?.lot ?? '', identity.get(f.msr)?.eqp ?? '', ...f.values.map(num)])
      ]
    })
  }

  if (r.flaggedSites.length) {
    sheets.push({
      name: '주의·이상·실패 site',
      rows: [
        ['MSR', 'SEQ', 'CHIP', `CD${u}`, `편차 (${range ? '%' : 'σ'})`, '구분'],
        ...r.flaggedSites.map(s => [s.msr, s.sequence, s.chip, num(s.cd), num(s.delta), s.kind])
      ]
    })
  }

  return sheets
}

export const receiptFilename = (r: ReviewReceipt): string =>
  `skewvoir-receipt-${safeFileNamePart(r.selection.focusMsr)}-${r.generatedAt.slice(0, 10).replaceAll('-', '')}.xlsx`

/** Whether every number the receipt would print is on hand.
 *
 *  A set receipt needs the whole set's files, and 측정 개요 deliberately never
 *  loads them (shouldLoadSet) — a receipt taken there would list every member
 *  but the focus as "not loaded". So it waits for a view that has the set. */
export const receiptReady = (s: {
  scope: AnalysisScope
  focusLoaded: boolean
  /** Set members that resolved to a history row (`setRows`). */
  setResolved: number
  setLoaded: number
  setPending: boolean
  /** The last set batch failed — the files on hand are the previous set's. */
  setError: boolean
  /** The set key the loaded files were fetched for / the screen is asking about. */
  loadedKey: string
  wantedKey: string
}): boolean =>
  s.focusLoaded && (s.scope === 'single' || (
    !s.setError && s.setResolved > 0
    && isSetPoolComplete({ pending: s.setPending, loadedKey: s.loadedKey, wantedKey: s.wantedKey, loaded: s.setLoaded, expected: s.setResolved })
  ))
