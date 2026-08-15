// Skewvoir single-MSR spatial diagnosis.
//
// One wafer, one parameter. Everything here describes the SPATIAL structure of a
// SINGLE measurement — where on the wafer the CD sits high/low, whether it trends
// centre→edge, whether one sector runs hot. It deliberately does NOT compute any
// wafer-to-wafer or site-to-site σ: there is exactly one wafer in scope, so a
// cross-wafer spread is undefined and must never be fabricated (spatial.test.ts
// pins this). Every "spread" below is the WITHIN-wafer IQR of that bin/sector's
// own sites.
//
// REUSE, do not re-derive:
//   • utils/msrRows.ts    — isMeasuredRow / measuredRows (the measured↔failure gate)
//   • utils/waferChip.ts  — parseChipXY
//   • utils/waferGeometry — stagePosMm / siteRadiusMm (physical placement)
//   • utils/stats.ts      — quantileSorted (median + quartiles)
//   • utils/radialAnalysis— analyzeRadialProfile (the radial trend fit + residuals
//                            + radius bins), so the residual layer and the
//                            centre→edge trend come from the SAME fit the
//                            dashboard Radius Plot already uses.
//
// Runs under raw `node --test` (no Nuxt, no bundler) — sibling imports carry an
// explicit `.ts` extension.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { isMeasuredRow } from '../msrRows.ts'
import { parseChipXY } from '../waferChip.ts'
import { stagePosMm, type WaferGeometry } from '../waferGeometry.ts'
import { quantileSorted } from '../stats.ts'
import { analyzeRadialProfile, type RadialModel, type RadialSample } from '../radialAnalysis.ts'

// ── Public types ───────────────────────────────────────────────────────────

export type SpatialReadiness = 'ok' | 'unavailable'

/** The four map layers a caller can colour by. `failure` is a separate site list,
 * not a numeric layer, but shares the switcher. */
export type SpatialLayerKey = 'raw' | 'centered' | 'residual' | 'failure'

/** Wafer notch orientation. Phase-1 MsrFile metadata does NOT carry a notch
 * field, so the module falls back to a validated default (bottom) that matches
 * the notch WaferMap.vue renders at [0, -R]. `notchValidated` says whether the
 * orientation came from real metadata (false in Phase-1). */
export type NotchOrientation = 'bottom' | 'top' | 'left' | 'right'

export interface SpatialSite {
  sequence: number
  chip: string // chip_number ("col, row")
  chipXY: [number, number] | null
  posMm: [number, number] | null // stage position, mm from wafer centre
  radiusMm: number | null
  sector: string | null // compass key ('E'|'N'|'W'|'S'), null when unplaced
  raw: number // cd_value
  centered: number // raw − wafer median
  residual: number | null // raw − radial-trend prediction (null when no trend)
}

export interface SpatialFailureSite {
  sequence: number
  chip: string
  chipXY: [number, number] | null
  posMm: [number, number] | null
  /** Same notch-anchored compass sector the measured sites carry, so a caller
   * can ask WHERE the failures sit without re-deriving the wheel. null when the
   * stage coordinate did not parse. */
  sector: string | null
}

/** One radial bin, within-wafer. `spread` is the IQR (q3 − q1) of the bin's own
 * site values — NOT a cross-wafer sigma. */
export interface SpatialRadiusBin {
  radiusMm: number
  median: number
  q1: number
  q3: number
  spread: number
  count: number
}

export interface SpatialSector {
  key: string // 'E' | 'N' | 'W' | 'S'
  label: string // Korean label
  median: number
  q1: number
  q3: number
  spread: number // within-wafer IQR
  count: number
}

export interface SpatialSectorSummary {
  status: SpatialReadiness
  notch: NotchOrientation
  notchValidated: boolean
  sectors: SpatialSector[]
  reason: string | null
}

/** One answer-strip chip. Each is a SEPARATE piece of evidence — the strip never
 * merges them into a single score. */
export interface SpatialEvidence {
  key: string
  label: string
  status: SpatialReadiness
  value: number | null
  unit: string
  detail: string
}

export interface SpatialEvidenceStrip {
  centerEdgeDelta: SpatialEvidence
  directionContrast: SpatialEvidence
  largestLocalResidual: SpatialEvidence
  coverage: SpatialEvidence
}

export interface SpatialCoverage {
  measured: number
  failed: number
  total: number
  ratio: number
}

export interface SpatialResult {
  parameter: string
  unit: string
  readiness: {
    coordinates: SpatialReadiness // 'unavailable' when no measured site has a parseable stage coordinate
    radialTrend: SpatialReadiness // 'ok' only when analyzeRadialProfile actually fitted a trend
    reason: string | null
  }
  waferMedian: number
  sites: SpatialSite[]
  failures: SpatialFailureSite[]
  radiusBins: SpatialRadiusBin[]
  sectors: SpatialSectorSummary
  evidence: SpatialEvidenceStrip
  coverage: SpatialCoverage
  radialStatus: 'raw' | 'fitted' | 'insufficient'
}

export interface SpatialOptions {
  unit?: string
  model?: RadialModel
  notch?: NotchOrientation
}

// ── Helpers ──────────────────────────────────────────────────────────────

// Exported so anything that groups BY sector (the failure decomposition on the
// 측정 개요 card) prints the same Korean label the sector profile does, instead
// of a second translation table that can drift from this one.
export const SECTOR_LABEL: Record<string, string> = {
  E: '우측(E)',
  N: '상단(N)',
  W: '좌측(W)',
  S: '하단(S·노치)'
}

// Notch rotation offset (degrees, CCW) applied before binning into compass
// sectors, so the sector wheel is anchored to the notch. The validated default
// 'bottom' keeps the RadiusPlot convention (E at +x, S toward the notch) with a
// zero offset.
const NOTCH_OFFSET: Record<NotchOrientation, number> = {
  bottom: 0,
  right: 90,
  top: 180,
  left: 270
}

const sectorOf = (x: number, y: number, notch: NotchOrientation): string => {
  const angle = (Math.atan2(y, x) * 180 / Math.PI + 360 + NOTCH_OFFSET[notch]) % 360
  if (angle < 45 || angle >= 315) return 'E'
  if (angle < 135) return 'N'
  if (angle < 225) return 'W'
  return 'S'
}

const median = (values: number[]): number => {
  if (values.length === 0) return Number.NaN
  return quantileSorted([...values].sort((a, b) => a - b), 0.5)
}

// Within-wafer quartiles + IQR spread for a set of site values.
const spreadOf = (values: number[]): { median: number, q1: number, q3: number, spread: number } => {
  const sorted = [...values].sort((a, b) => a - b)
  const q1 = quantileSorted(sorted, 0.25)
  const q3 = quantileSorted(sorted, 0.75)
  return { median: quantileSorted(sorted, 0.5), q1, q3, spread: q3 - q1 }
}

const evidence = (
  key: string,
  label: string,
  unit: string,
  status: SpatialReadiness,
  value: number | null,
  detail: string
): SpatialEvidence => ({ key, label, status, value, unit, detail })

// ── Public API ───────────────────────────────────────────────────────────

/**
 * Diagnose the spatial structure of ONE measurement's active parameter.
 *
 * @param rows      raw MsrFileRows for the focus MSR (any parameters; filtered here)
 * @param parameter active parameter
 * @param geo       parsed wafer geometry (parseWaferGeometry of the focus file)
 */
export const analyzeSpatial = (
  rows: MsrFileRow[],
  parameter: string,
  geo: WaferGeometry,
  options: SpatialOptions = {}
): SpatialResult => {
  const unit = options.unit ?? ''
  const notch: NotchOrientation = options.notch ?? 'bottom'
  const model: RadialModel = options.model ?? 'linear'

  const forParam = rows.filter(r => r.parameter === parameter)
  const measured = forParam.filter(isMeasuredRow)
  const failedRows = forParam.filter(r => !isMeasuredRow(r))

  const total = measured.length + failedRows.length
  const coverage: SpatialCoverage = {
    measured: measured.length,
    failed: failedRows.length,
    total,
    ratio: total > 0 ? measured.length / total : Number.NaN
  }

  const waferMedian = median(measured.map(r => r.cd_value))

  // Radial samples — only the measured sites we can physically place. Sites with
  // an unparseable stage coordinate contribute to raw/centered layers and to
  // coverage, but not to any radius/sector/residual computation.
  const samples: RadialSample[] = []
  for (const r of measured) {
    const pos = stagePosMm(r.stage_coordinate, geo)
    if (!pos) continue
    const [x, y] = pos
    samples.push({
      sequence: r.sequence,
      radius: Math.hypot(x, y),
      value: r.cd_value,
      x,
      y,
      sector: sectorOf(x, y, notch)
    })
  }

  const coordinatesReady: SpatialReadiness = samples.length > 0 ? 'ok' : 'unavailable'

  // The radial trend fit — REUSED for the residual layer, the radius bins, the
  // centre→edge delta and the largest-local-residual evidence. When there aren't
  // enough placeable sites this returns status 'insufficient'/'raw' and we treat
  // the trend as unavailable rather than inventing residuals.
  const profile = analyzeRadialProfile(samples, { model })
  const radialTrendReady: SpatialReadiness = profile.status === 'fitted' ? 'ok' : 'unavailable'

  const residualBySeq = new Map<number, number | null>()
  for (const p of profile.points) residualBySeq.set(p.sequence, p.residual)

  // Per-site layers. posMm/radius/sector are null when the coordinate didn't
  // parse; raw + centered are always available.
  const sites: SpatialSite[] = measured.map((r) => {
    const pos = stagePosMm(r.stage_coordinate, geo)
    const radiusMm = pos ? Math.hypot(pos[0], pos[1]) : null
    return {
      sequence: r.sequence,
      chip: r.chip_number,
      chipXY: parseChipXY(r.chip_number),
      posMm: pos,
      radiusMm,
      sector: pos ? sectorOf(pos[0], pos[1], notch) : null,
      raw: r.cd_value,
      centered: r.cd_value - waferMedian,
      residual: radialTrendReady === 'ok' ? residualBySeq.get(r.sequence) ?? null : null
    }
  })

  const failures: SpatialFailureSite[] = failedRows.map((r) => {
    const pos = stagePosMm(r.stage_coordinate, geo)
    return {
      sequence: r.sequence,
      chip: r.chip_number,
      chipXY: parseChipXY(r.chip_number),
      posMm: pos,
      sector: pos ? sectorOf(pos[0], pos[1], notch) : null
    }
  })

  // Radius bins — reuse analyzeRadialProfile's own radial IQR bins (raw layer),
  // relabelled with an explicit within-wafer IQR spread.
  const radiusBins: SpatialRadiusBin[] = profile.bins.map(b => ({
    radiusMm: b.radius,
    median: b.median,
    q1: b.q1,
    q3: b.q3,
    spread: b.q3 - b.q1,
    count: b.count
  }))

  // Sector summary — grouped by notch-anchored compass sector.
  const sectorSummary = buildSectors(samples, notch, coordinatesReady)

  // Evidence strip — four SEPARATE values, never merged.
  const evidenceStrip = buildEvidence({
    profile,
    radialTrendReady,
    radiusBins,
    sectorSummary,
    coverage,
    unit
  })

  return {
    parameter,
    unit,
    readiness: {
      coordinates: coordinatesReady,
      radialTrend: radialTrendReady,
      reason: coordinatesReady === 'unavailable'
        ? '측정 site의 좌표(stage_coordinate) 정보가 없어 방사형/섹터 분석을 수행할 수 없습니다.'
        : radialTrendReady === 'unavailable'
          ? '방사형 추세를 적합하기에 측정 site가 부족합니다.'
          : null
    },
    waferMedian,
    sites,
    failures,
    radiusBins,
    sectors: sectorSummary,
    evidence: evidenceStrip,
    coverage,
    radialStatus: profile.status
  }
}

const buildSectors = (
  samples: RadialSample[],
  notch: NotchOrientation,
  coordinatesReady: SpatialReadiness
): SpatialSectorSummary => {
  if (coordinatesReady === 'unavailable') {
    return {
      status: 'unavailable',
      notch,
      notchValidated: false,
      sectors: [],
      reason: '평가 불가 — 좌표 정보가 없어 섹터를 나눌 수 없습니다.'
    }
  }

  const grouped = new Map<string, number[]>()
  for (const s of samples) {
    const key = s.sector ?? sectorOf(s.x ?? 0, s.y ?? 0, notch)
    const arr = grouped.get(key) ?? []
    arr.push(s.value)
    grouped.set(key, arr)
  }

  const order = ['E', 'N', 'W', 'S']
  const sectors: SpatialSector[] = order.flatMap((key) => {
    const values = grouped.get(key)
    if (!values || values.length === 0) return []
    const { median: m, q1, q3, spread } = spreadOf(values)
    return [{ key, label: SECTOR_LABEL[key] ?? key, median: m, q1, q3, spread, count: values.length }]
  })

  return {
    status: 'ok',
    notch,
    // Phase-1 metadata carries no notch orientation — this is the documented
    // validated default, not a measured value.
    notchValidated: false,
    sectors,
    reason: null
  }
}

interface EvidenceInput {
  profile: ReturnType<typeof analyzeRadialProfile>
  radialTrendReady: SpatialReadiness
  radiusBins: SpatialRadiusBin[]
  sectorSummary: SpatialSectorSummary
  coverage: SpatialCoverage
  unit: string
}

const buildEvidence = (input: EvidenceInput): SpatialEvidenceStrip => {
  const { profile, radialTrendReady, radiusBins, sectorSummary, coverage, unit } = input

  // Centre→edge delta: the fitted trend's total change across the measured span
  // when a trend exists; else the outer-minus-inner bin median as a raw fallback.
  const centerEdge = ((): SpatialEvidence => {
    if (radialTrendReady === 'ok' && profile.metrics.spanDelta != null) {
      return evidence(
        'centerEdgeDelta', '중심→외곽 변화량', unit, 'ok',
        profile.metrics.spanDelta,
        `방사형 추세: 최내측→최외측 ${profile.metrics.spanDelta >= 0 ? '+' : ''}${profile.metrics.spanDelta.toFixed(3)} ${unit}`
      )
    }
    if (radiusBins.length >= 2) {
      const delta = radiusBins[radiusBins.length - 1]!.median - radiusBins[0]!.median
      return evidence('centerEdgeDelta', '중심→외곽 변화량', unit, 'ok', delta,
        `bin median 차: ${delta >= 0 ? '+' : ''}${delta.toFixed(3)} ${unit}`)
    }
    return evidence('centerEdgeDelta', '중심→외곽 변화량', unit, 'unavailable', null, '좌표 부족 — 평가 불가')
  })()

  // Direction contrast: the larger opposing-sector median gap (E↔W vs N↔S).
  const directionContrast = ((): SpatialEvidence => {
    if (sectorSummary.status !== 'ok') {
      return evidence('directionContrast', '방향 대비', unit, 'unavailable', null, '좌표 부족 — 평가 불가')
    }
    const bySector = new Map(sectorSummary.sectors.map(s => [s.key, s.median]))
    const pairs: { label: string, diff: number }[] = []
    if (bySector.has('E') && bySector.has('W')) {
      pairs.push({ label: '우−좌(E−W)', diff: bySector.get('E')! - bySector.get('W')! })
    }
    if (bySector.has('N') && bySector.has('S')) {
      pairs.push({ label: '상−하(N−S)', diff: bySector.get('N')! - bySector.get('S')! })
    }
    if (pairs.length === 0) {
      return evidence('directionContrast', '방향 대비', unit, 'unavailable', null, '대향 섹터 부족 — 평가 불가')
    }
    const strongest = pairs.reduce((best, p) => Math.abs(p.diff) > Math.abs(best.diff) ? p : best)
    return evidence('directionContrast', '방향 대비', unit, 'ok', strongest.diff,
      `${strongest.label}: ${strongest.diff >= 0 ? '+' : ''}${strongest.diff.toFixed(3)} ${unit}`)
  })()

  // Largest local residual: the single site furthest from the radial trend.
  const largestResidual = ((): SpatialEvidence => {
    if (radialTrendReady === 'ok' && profile.metrics.maxAbsResidual != null) {
      const seq = profile.metrics.maxResidualSequence
      return evidence('largestLocalResidual', '최대 국소 잔차', unit, 'ok',
        profile.metrics.maxAbsResidual,
        `seq ${seq ?? '—'} 에서 |잔차| ${profile.metrics.maxAbsResidual.toFixed(3)} ${unit}`)
    }
    return evidence('largestLocalResidual', '최대 국소 잔차', unit, 'unavailable', null, '추세 없음 — 평가 불가')
  })()

  const coverageEvidence = evidence(
    'coverage', '측정 커버리지', 'ratio', 'ok', coverage.ratio,
    `${coverage.measured}/${coverage.total} 측정 (${coverage.failed} 실패)`
  )

  return {
    centerEdgeDelta: centerEdge,
    directionContrast,
    largestLocalResidual: largestResidual,
    coverage: coverageEvidence
  }
}
