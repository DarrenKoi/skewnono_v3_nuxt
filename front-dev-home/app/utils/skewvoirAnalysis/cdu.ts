// Skewvoir 측정 개요 — CDU metrics and the failure decomposition behind them.
//
// Two questions, deliberately kept apart:
//
//   cduMetrics()       what did the MEASURED sites say (level / spread / shape)
//   failureBreakdown() what did NOT get measured, and why
//
// They are separate because a single success-rate number destroys the cause —
// `msr_check`, `align_fail`, image failures and a null `cd_value` are four
// different problems with four different owners, and averaging them into one
// health figure is exactly what wafer-analysis-method-research.md §4.1 forbids.
//
// Nothing here invents a number: an unmeasured site contributes to `missing`,
// never a 0 to the mean. Level/spread are null (평가 불가) rather than a
// placeholder when there aren't enough measured sites to define them.
//
// REUSE, do not re-derive:
//   • utils/msrRows.ts  — isMeasuredRow (the ONE measured↔missing gate)
//   • utils/stats.ts    — mean / median / sampleStd / medianAbsoluteDeviation
//   • ./spatial.ts      — analyzeSpatial's `failures` layer + centre→edge
//                         evidence; this module never re-places a site on the
//                         wafer, it only counts what spatial already placed.
//
// Runs under raw `node --test` (no Nuxt, no bundler) — sibling imports carry an
// explicit `.ts` extension.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import type { MeasHistRow } from '~/composables/useMeasHistApi'
import { isMeasuredRow } from '../msrRows.ts'
import { mean, median, sampleStd, medianAbsoluteDeviation, MAD_TO_SIGMA } from '../stats.ts'
import { SECTOR_LABEL, type SpatialFailureSite } from './spatial.ts'

// ── CDU metrics ──────────────────────────────────────────────────────────

export interface CduLevel {
  mean: number
  median: number
}

export interface CduSpread {
  std: number
  threeSigma: number
  /** MAD scaled by MAD_TO_SIGMA so it stands next to `std` on the same axis:
   * equal to sigma for clean data, far below it when a few extreme sites are
   * doing the inflating. That comparison IS the diagnostic. */
  madSigma: number
  range: number
}

export interface CduMetrics {
  parameter: string
  unit: string
  /** Valid N — measured sites only. Never render a spread without it. */
  n: number
  /** Sites of this parameter with no measurement (cd_value null / mp_number < 0). */
  missing: number
  total: number
  /** null when nothing was measured — 평가 불가, not 0. */
  level: CduLevel | null
  /** null below 2 measured sites: one point has no spread, and a 0 there would
   * read as perfect uniformity. */
  spread: CduSpread | null
}

export const cduMetrics = (rows: MsrFileRow[], parameter: string, unit = ''): CduMetrics => {
  const forParam = rows.filter(r => r.parameter === parameter)
  const values = forParam.filter(isMeasuredRow).map(r => r.cd_value)
  const n = values.length

  const std = sampleStd(values)
  return {
    parameter,
    unit,
    n,
    missing: forParam.length - n,
    total: forParam.length,
    level: n > 0 ? { mean: mean(values), median: median(values) } : null,
    spread: n > 1
      ? {
          std,
          threeSigma: 3 * std,
          madSigma: medianAbsoluteDeviation(values) * MAD_TO_SIGMA,
          range: Math.max(...values) - Math.min(...values)
        }
      : null
  }
}

// ── Failure decomposition ────────────────────────────────────────────────

export type FailureReasonKey = 'msr_check' | 'align_fail' | 'image' | 'cd_missing'

/** 'unknown' is a THIRD state, not a soft pass: the field is absent, or its
 * denominator is missing, so the question cannot be answered. Rendering it as a
 * pass is how a real failure disappears. */
export type FailureReasonStatus = 'pass' | 'fail' | 'unknown'

export interface FailureReason {
  key: FailureReasonKey
  label: string
  status: FailureReasonStatus
  /** Failing units — images, or sites. null when the source is a flag with no count behind it. */
  count: number | null
  total: number | null
  /** 0..100. For `image` this is meas-hist's own `fail_ratio`, which is ALREADY
   * a percent (4.57 means 4.57%) and is passed through untouched. */
  percent: number | null
  detail: string
}

export interface FailureBreakdown {
  /** Site counts for the ACTIVE parameter only — other parameters' rows are not
   * in this denominator. */
  sites: { total: number, measured: number, missing: number }
  reasons: FailureReason[]
  failedCount: number
  unknownCount: number
}

/** The meas-hist fields that carry an MSR-level failure cause. Typed as a subset
 * so a caller can pass a whole MeasHistRow (focusRow) without adaptation. */
export type FailureSource = Pick<
  MeasHistRow, 'msr_check' | 'align_fail' | 'total_images' | 'fail_images' | 'fail_ratio'
>

const UNKNOWN_DETAIL = '평가 불가 — meas-hist 행이 없습니다.'

const msrCheckReason = (src: FailureSource | null): FailureReason => {
  if (!src) return { key: 'msr_check', label: 'MSR 판정', status: 'unknown', count: null, total: null, percent: null, detail: UNKNOWN_DETAIL }
  const failed = src.msr_check === 'No'
  return {
    key: 'msr_check',
    label: 'MSR 판정',
    status: failed ? 'fail' : 'pass',
    count: null,
    total: null,
    percent: null,
    detail: failed ? 'msr_check=No — 측정 자체가 불합격 처리되었습니다.' : 'msr_check=Yes'
  }
}

// 'NA' is NOT a failure: alignment was not judged, so the answer is unknown.
// Counting it as a failure inflates every fleet whose tools do not report it.
const alignReason = (src: FailureSource | null): FailureReason => {
  if (!src) return { key: 'align_fail', label: 'Align', status: 'unknown', count: null, total: null, percent: null, detail: UNKNOWN_DETAIL }
  const status: FailureReasonStatus = src.align_fail === 'Fail' ? 'fail' : src.align_fail === 'Pass' ? 'pass' : 'unknown'
  return {
    key: 'align_fail',
    label: 'Align',
    status,
    count: null,
    total: null,
    percent: null,
    detail: status === 'unknown' ? 'align_fail=NA — 판정되지 않았습니다(실패 아님).' : `align_fail=${src.align_fail}`
  }
}

const imageReason = (src: FailureSource | null): FailureReason => {
  if (!src) return { key: 'image', label: '이미지', status: 'unknown', count: null, total: null, percent: null, detail: UNKNOWN_DETAIL }
  if (!(src.total_images > 0)) {
    return { key: 'image', label: '이미지', status: 'unknown', count: null, total: 0, percent: null, detail: '평가 불가 — 이미지 수(분모)가 없습니다.' }
  }
  const failed = src.fail_images > 0
  return {
    key: 'image',
    label: '이미지',
    status: failed ? 'fail' : 'pass',
    count: src.fail_images,
    total: src.total_images,
    // fail_ratio is a percent upstream — NEVER multiplied by 100 here.
    percent: src.fail_ratio,
    detail: `${src.fail_images}/${src.total_images} 이미지 실패 (fail_ratio ${src.fail_ratio.toFixed(2)}%)`
  }
}

const cdMissingReason = (measured: number, total: number): FailureReason => {
  const missing = total - measured
  if (total === 0) {
    return { key: 'cd_missing', label: 'CD 결측', status: 'unknown', count: null, total: 0, percent: null, detail: '평가 불가 — 이 파라미터의 site가 없습니다.' }
  }
  return {
    key: 'cd_missing',
    label: 'CD 결측',
    status: missing > 0 ? 'fail' : 'pass',
    count: missing,
    total,
    percent: (missing / total) * 100,
    detail: missing > 0
      ? `${missing}/${total} site 에 측정값이 없습니다 (cd_value null).`
      : `${total} site 모두 측정값이 있습니다.`
  }
}

/**
 * Four causes, kept apart. The three MSR-level ones come from meas-hist; the
 * site-level one is counted from the msr-file rows of the ACTIVE parameter, so
 * it stays answerable even when no meas-hist row is loaded.
 *
 * @param rows      raw MsrFileRows (any parameter; filtered here)
 * @param parameter active parameter
 * @param source    the focus MSR's meas-hist row, or null when it hasn't loaded
 */
export const failureBreakdown = (
  rows: MsrFileRow[],
  parameter: string,
  source: FailureSource | null
): FailureBreakdown => {
  const forParam = rows.filter(r => r.parameter === parameter)
  const measured = forParam.filter(isMeasuredRow).length
  const total = forParam.length

  const reasons: FailureReason[] = [
    msrCheckReason(source),
    alignReason(source),
    imageReason(source),
    cdMissingReason(measured, total)
  ]

  return {
    sites: { total, measured, missing: total - measured },
    reasons,
    failedCount: reasons.filter(r => r.status === 'fail').length,
    unknownCount: reasons.filter(r => r.status === 'unknown').length
  }
}

// ── Where the failures sit ───────────────────────────────────────────────

/** Below this many PLACED failures a sector share is noise — three points can
 * land in one quadrant by chance often enough that calling it a cluster would
 * be a coin flip presented as a finding. */
const MIN_PLACED_FOR_VERDICT = 3

/** A single sector holding at least this share of the placed failures is what we
 * call clustered. It is a display threshold, not a statistical test — which is
 * why the per-sector counts are returned alongside it, so the reader judges the
 * evidence rather than the verdict. */
const CLUSTER_SHARE = 0.6

export interface FailureSectorCount {
  key: string
  label: string
  count: number
}

export interface FailureClustering {
  status: 'ok' | 'unavailable'
  /** Failures with a parseable stage coordinate — the ONLY denominator here. */
  placed: number
  /** Failures we could not put on the wafer; excluded from every share below. */
  unplaced: number
  sectors: FailureSectorCount[]
  topShare: number | null
  verdict: 'clustered' | 'scattered' | null
  reason: string | null
}

/**
 * Are the failures piled into one part of the wafer, or spread over it?
 *
 * Takes analyzeSpatial()'s own `failures` layer — this function never places a
 * site itself, it only counts what spatial already placed and labelled.
 */
export const failureClustering = (failures: SpatialFailureSite[]): FailureClustering => {
  const placedSites = failures.filter(f => f.sector != null)
  const placed = placedSites.length
  const unplaced = failures.length - placed

  const counts = new Map<string, number>()
  for (const f of placedSites) counts.set(f.sector!, (counts.get(f.sector!) ?? 0) + 1)
  const sectors: FailureSectorCount[] = [...counts.entries()]
    .map(([key, count]) => ({ key, label: SECTOR_LABEL[key] ?? key, count }))
    .sort((a, b) => b.count - a.count)

  if (placed < MIN_PLACED_FOR_VERDICT) {
    return {
      status: 'unavailable',
      placed,
      unplaced,
      sectors,
      topShare: null,
      verdict: null,
      reason: placed === 0
        ? '좌표를 확인할 수 있는 실패 site 가 없습니다.'
        : `실패 site 가 ${placed}개뿐이라 공간 군집 여부를 판단하지 않습니다.`
    }
  }

  const topShare = sectors[0]!.count / placed
  return {
    status: 'ok',
    placed,
    unplaced,
    sectors,
    topShare,
    verdict: topShare >= CLUSTER_SHARE ? 'clustered' : 'scattered',
    reason: null
  }
}
