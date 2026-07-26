// Skewvoir single-MSR visual-evidence review queue.
//
// ONE MSR, ONE parameter. This module turns the focus measurement's per-site
// image rows into a PRIORITY REVIEW QUEUE: one entry per measured/failed site,
// each tagged with the REASON it deserves a human's eyes, sorted so the most
// review-worthy evidence rises to the top.
//
// §0.5 — RESEARCH-INTEGRITY CONSTRAINT (critical):
//   The mock per-MSR `health` scalar and the placeholder `spm_dict` profile are
//   DEMO-ONLY (useMsrFileApi.ts). They carry no real judgment provenance, so they
//   must NEVER drive a classification or a verdict. This module deliberately
//   accepts only MsrFileRow[] — it structurally cannot read `health`/`spm_dict`,
//   which live on the parent MsrFileResponse, not on a row. A queue entry is only
//   ever tagged from EVIDENCE the row itself carries (the measured↔failed gate and
//   the spatial residual) plus, SEPARATELY, a vendor-score MONITORING badge that
//   is never a verdict reason. abnormal/watch verdicts are producible ONLY when a
//   caller supplies real verdict provenance (options.verdicts); in Phase-1 nothing
//   does, so that branch is unreachable here and no abnormal/watch tag is emitted.
//   gallery.test.ts pins all of this (source grep + classification assertions).
//
// REUSE, do not re-derive:
//   • utils/msrRows.ts               — isMeasuredRow (the measured↔failure gate)
//   • utils/skewvoirAnalysis/spatial — analyzeSpatial (per-site RESIDUALS; the
//                                       SAME residual layer the map/table show)
//   • utils/stats.ts                 — iqrFences (the residual/vendor outlier fence)
//
// Runs under raw `node --test` (no Nuxt, no bundler) — sibling imports carry an
// explicit `.ts` extension.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { parsePixelSetting, pixelSizeNm } from '../magPixel.ts'
import { isMeasuredRow } from '../msrRows.ts'
import { iqrFences } from '../stats.ts'
import type { WaferGeometry } from '../waferGeometry.ts'
import { analyzeSpatial, type SpatialReadiness } from './spatial.ts'

// ── Public types ─────────────────────────────────────────────────────────────

/** Why a site sits in the review queue. Only `failure` and `residual` are
 * EVIDENCE-BACKED (they gate the `이상·실패 우선` filter). `sequence` is the
 * baseline "here by measurement order, nothing flagged" reason. `abnormal`/
 * `watch` are producible ONLY when real verdict provenance is supplied — never
 * from mock data (§0.5). Vendor score is NOT a reason: it is a separate
 * monitoring badge. */
export type GalleryReason = 'failure' | 'abnormal' | 'watch' | 'residual' | 'sequence'

/** A verdict tag a caller may inject WITH REAL PROVENANCE. Phase-1 supplies none. */
export type SiteVerdict = 'abnormal' | 'watch'

/** Vendor acquisition-score monitoring badge — kept SEPARATE from `reasons` so a
 * low vendor score can never read as a measurement verdict. `low` is true when any
 * present score channel falls below its own within-wafer low fence. */
export interface VendorMonitor {
  measurementScore: number | null
  addressing1Score: number | null
  addressing2Score: number | null
  low: boolean
  channels: string[] // the channel labels that tripped the low fence (Korean)
  detail: string
}

/** One review-queue entry — one measured or failed site/image row. */
export interface ReviewEntry {
  sequence: number
  chip: string // chip_number ("col, row") — the canonical site key
  mp: number // mp_number
  parameter: string
  value: number | null // cd_value (null for a failed/unmeasured site)
  unit: string
  residual: number | null // spatial residual (null when unmeasured or no trend)
  reasons: GalleryReason[]
  image: string | null // mp_image_name_01 (null when absent — the row still stays)
  hasImage: boolean
  monitor: VendorMonitor | null // vendor-score monitoring badge, separate from reasons
  evidenceBacked: boolean // failure || residual — gates the `이상·실패 우선` filter
  // Acquisition metadata (viewer/drawer display only — never classification input).
  mag: number
  pixel: string
  vac: number
  // Physical scale derived from mag + pixel (utils/magPixel.ts). null for an
  // empty row (mag 0 / pixel "0,0") rather than Infinity.
  nmPerPx: number | null
}

export interface ReviewQueue {
  parameter: string
  unit: string
  entries: ReviewEntry[]
  readiness: {
    coordinates: SpatialReadiness
    residual: SpatialReadiness // 'ok' only when a radial trend produced residuals
    reason: string | null
  }
  counts: {
    total: number
    failure: number
    residual: number
    monitor: number // sites with a vendor low-score badge
    withImage: number
    withoutImage: number
    evidenceBacked: number
  }
}

export interface GalleryOptions {
  unit?: string
  /** Real per-sequence verdict provenance. Phase-1 passes nothing, so no
   * abnormal/watch tag is ever produced (§0.5). Keyed by sequence. */
  verdicts?: Record<number, SiteVerdict>
  /** Override the |residual| high fence (else the within-wafer 1.5·IQR fence). */
  residualFence?: number
}

/** Display metadata for each reason — Korean label + a semantic role the UI maps
 * to a colour. `evidence` marks the two reasons that gate the `이상·실패 우선`
 * filter. Kept beside the reason enum so every view labels reasons identically. */
export const REASON_META: Record<GalleryReason, { label: string, role: 'bad' | 'warn' | 'muted', evidence: boolean }> = {
  failure: { label: '측정 실패', role: 'bad', evidence: true },
  abnormal: { label: '이상 판정', role: 'bad', evidence: true },
  watch: { label: '주의 판정', role: 'warn', evidence: true },
  residual: { label: '국소 잔차', role: 'warn', evidence: true },
  sequence: { label: '측정 순서', role: 'muted', evidence: false }
}

/** The `이상·실패 우선` toggle's state, resolved from the reviewer's explicit
 * choice and the queue itself.
 *
 * The queue is PRE-ARMED: the gallery exists to work through 이상·실패 evidence,
 * so opening it filtered is the useful landing state — the reviewer sees the
 * sites that need eyes without a first click.
 *
 * `null` means the reviewer has not touched the toggle, so the default decides,
 * and the default checks there is actually evidence to show. On a clean wafer
 * (nothing evidence-backed — the common case for a healthy tool) arming would
 * land on "필터에 해당하는 항목이 없습니다" while every good site sits hidden
 * behind a filter the reviewer never set, so the default relaxes to the full
 * queue. Once the reviewer sets the toggle, that choice always wins.
 *
 * Pure, and takes the count rather than the queue, so the caller can resolve it
 * against a queue that is still loading (an empty queue reads as "no evidence
 * yet" and re-resolves the moment rows arrive). */
export const resolveEvidenceOnly = (
  choice: boolean | null,
  evidenceBackedCount: number
): boolean => choice ?? evidenceBackedCount > 0

/** Artifact-suspicion review TAGS — a SEPARATE axis from any pattern verdict. The
 * reviewer picks these by eye; Phase-1 provides no algorithmic backing for them,
 * so they are review prompts, never machine classifications. */
export const ARTIFACT_TAGS: { key: string, label: string }[] = [
  { key: 'charging', label: '차징/콘트라스트' },
  { key: 'focus', label: '포커스/비점수차' },
  { key: 'drift', label: '이미지 드리프트' },
  { key: 'contamination', label: '오염/반복 노광' },
  { key: 'edge-algo', label: '엣지 알고리즘' },
  { key: 'pixel-cal', label: '픽셀 보정' }
]

// ── Helpers ──────────────────────────────────────────────────────────────────

const VENDOR_CHANNELS: { key: 'measurement_score' | 'addressing1_score' | 'addressing2_score', label: string }[] = [
  { key: 'measurement_score', label: '측정 점수' },
  { key: 'addressing1_score', label: '어드레싱1' },
  { key: 'addressing2_score', label: '어드레싱2' }
]

// The rank of an entry's PRIMARY sort group: failures first, then (only with
// provenance) abnormal/watch, then everything else. Within a group the caller
// sorts by residual magnitude then sequence.
const groupRank = (reasons: GalleryReason[]): number => {
  if (reasons.includes('failure')) return 0
  if (reasons.includes('abnormal')) return 1
  if (reasons.includes('watch')) return 2
  return 3
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Build the priority review queue for ONE focus MSR + active parameter.
 *
 * @param rows      raw MsrFileRows for the focus MSR (any parameters; filtered here)
 * @param parameter active parameter
 * @param geo       parsed wafer geometry (parseWaferGeometry of the focus file)
 */
export const buildReviewQueue = (
  rows: MsrFileRow[],
  parameter: string,
  geo: WaferGeometry,
  options: GalleryOptions = {}
): ReviewQueue => {
  const unit = options.unit ?? ''

  // Reuse the SAME spatial diagnosis the map/table read — its per-site residuals
  // are the residual reason's only source. We never re-derive residuals here.
  const spatial = analyzeSpatial(rows, parameter, geo, { unit })
  const residualBySeq = new Map<number, number | null>()
  for (const s of spatial.sites) residualBySeq.set(s.sequence, s.residual)

  const residualReady: SpatialReadiness = spatial.readiness.radialTrend

  // Rows for this parameter, in measurement order — measured AND failed. Every
  // one becomes an entry; an absent image never removes the evidence row.
  const paramRows = rows
    .filter(r => r.parameter === parameter)
    .sort((a, b) => a.sequence - b.sequence)

  // Residual high fence — within-wafer 1.5·IQR of the |residual| distribution, so
  // "large residual" is relative to THIS wafer, not a magic constant. Only defined
  // when a radial trend actually produced residuals.
  const absResiduals = spatial.sites
    .map(s => s.residual)
    .filter((r): r is number => r != null)
    .map(Math.abs)
  const residualFence = options.residualFence
    ?? (residualReady === 'ok' ? iqrFences(absResiduals)?.upper ?? Infinity : Infinity)

  // Per-channel vendor low fences — within-wafer, monitoring only. A score below
  // its own lower fence trips the badge; scores are never fed into a verdict.
  const vendorFence: Record<string, number | null> = {}
  for (const { key } of VENDOR_CHANNELS) {
    const values = paramRows
      .map(r => r[key])
      .filter((v): v is number => v != null && Number.isFinite(v))
    vendorFence[key] = iqrFences(values)?.lower ?? null
  }

  const entries: ReviewEntry[] = paramRows.map((r) => {
    const measured = isMeasuredRow(r)
    const residual = measured ? residualBySeq.get(r.sequence) ?? null : null

    const reasons: GalleryReason[] = []
    if (!measured) reasons.push('failure')
    // abnormal/watch: ONLY with real verdict provenance (never in Phase-1 mock).
    const verdict = options.verdicts?.[r.sequence]
    if (measured && verdict === 'abnormal') reasons.push('abnormal')
    else if (measured && verdict === 'watch') reasons.push('watch')
    if (measured && residual != null && Math.abs(residual) > residualFence) reasons.push('residual')
    // Baseline reason so a plain in-order site still explains its presence.
    if (reasons.length === 0) reasons.push('sequence')

    // Vendor-score monitoring badge — separate from reasons.
    const monitor = buildMonitor(r, vendorFence)

    const image = r.mp_image_name_01 && r.mp_image_name_01.length > 0 ? r.mp_image_name_01 : null
    const evidenceBacked = reasons.includes('failure')
      || reasons.includes('residual')
      || reasons.includes('abnormal')
      || reasons.includes('watch')

    return {
      sequence: r.sequence,
      chip: r.chip_number,
      mp: r.mp_number,
      parameter,
      value: measured ? r.cd_value : null,
      unit,
      residual,
      reasons,
      image,
      hasImage: image != null,
      monitor,
      evidenceBacked,
      mag: r.meas_condition_mag,
      pixel: r.meas_condition_pixel,
      vac: r.meas_condition_vac,
      // FOV는 폭이므로 가로 픽셀 수(x)를 쓴다. 빈 row(mag 0 / "0,0")는 null.
      nmPerPx: pixelSizeNm(
        r.meas_condition_mag,
        parsePixelSetting(r.meas_condition_pixel)?.x ?? 0
      )
    }
  })

  // Default sort: failure → residual magnitude (desc) → sequence. abnormal/watch
  // slot in right after failure only when provenance produced them (unreachable
  // in Phase-1). Non-mutating: sort a copy.
  const sorted = [...entries].sort((a, b) => {
    const ga = groupRank(a.reasons)
    const gb = groupRank(b.reasons)
    if (ga !== gb) return ga - gb
    const ra = Math.abs(a.residual ?? 0)
    const rb = Math.abs(b.residual ?? 0)
    if (rb !== ra) return rb - ra
    return a.sequence - b.sequence
  })

  const counts = {
    total: sorted.length,
    failure: sorted.filter(e => e.reasons.includes('failure')).length,
    residual: sorted.filter(e => e.reasons.includes('residual')).length,
    monitor: sorted.filter(e => e.monitor?.low).length,
    withImage: sorted.filter(e => e.hasImage).length,
    withoutImage: sorted.filter(e => !e.hasImage).length,
    evidenceBacked: sorted.filter(e => e.evidenceBacked).length
  }

  return {
    parameter,
    unit,
    entries: sorted,
    readiness: {
      coordinates: spatial.readiness.coordinates,
      residual: residualReady,
      reason: residualReady === 'ok'
        ? null
        : spatial.readiness.coordinates === 'unavailable'
          ? '좌표 정보가 없어 잔차 근거를 계산할 수 없습니다. 실패 site만 근거로 표시됩니다.'
          : '방사형 추세를 적합하기에 측정 site가 부족해 잔차 근거를 사용할 수 없습니다.'
    },
    counts
  }
}

const buildMonitor = (
  r: MsrFileRow,
  fence: Record<string, number | null>
): VendorMonitor | null => {
  const channels: string[] = []
  for (const { key, label } of VENDOR_CHANNELS) {
    const v = r[key]
    const f = fence[key]
    if (v != null && Number.isFinite(v) && f != null && v < f) channels.push(label)
  }
  const measurementScore = r.measurement_score ?? null
  const addressing1Score = r.addressing1_score ?? null
  const addressing2Score = r.addressing2_score ?? null
  // A badge exists whenever the row carries any acquisition score; `low` says
  // whether any tripped its within-wafer floor.
  const hasAnyScore = measurementScore != null || addressing1Score != null || addressing2Score != null
  if (!hasAnyScore) return null
  return {
    measurementScore,
    addressing1Score,
    addressing2Score,
    low: channels.length > 0,
    channels,
    detail: channels.length > 0
      ? `${channels.join(', ')} 점수 낮음 — 취득 품질 모니터링(판정 아님)`
      : '취득 점수 정상'
  }
}
