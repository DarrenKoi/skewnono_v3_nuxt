// Skewvoir 측정 개요 — the one-line verdict above the panels.
//
// The 측정 개요 top block used to be four cards (측정 성공률 · 실패 원인 ·
// CDU 지표 · 측정 조건) that answered "can I trust this wafer" twice over. This
// module composes the single sentence that answers it once, plus the badge tone
// beside it.
//
// It states only what THIS wafer can prove about itself. There is no spec or
// target contract in the repo and no historical baseline loaded on this view, so
// absolute judgements — "산포가 넓다", "In Spec", Cp/Cpk — are impossible and are
// never written. What IS computable is a self-comparison: σ against
// σ(이상치 제외) is the same wafer measured two ways, so the share of σ that a
// handful of sites carry needs no outside reference.
//
// REUSE, do not re-derive:
//   • ./cdu.ts      — cduMetrics (level/spread), sectorClustering (where)
//   • ../overview.ts— outlierCount (siteVerdicts, the ONE outlier definition)
//
// Runs under raw `node --test` (no Nuxt, no bundler) — sibling imports carry an
// explicit `.ts` extension.
import type { CduMetrics, SectorClustering } from './cdu.ts'
import { formatFixed } from '../recipeView.ts'

export type VerdictTone = 'ok' | 'attention'

/** How the template renders a run of the sentence. `num` is mono + tabular
 * figures, `bad` is the --sk-bad phrase. Segments rather than a string with
 * markup in it: the sentence is composed here, painted there, and neither side
 * has to parse the other's output. */
export interface VerdictSegment {
  text: string
  kind?: 'num' | 'bad'
}

export interface VerdictInput {
  paramLabel: string
  unit: string
  metrics: CduMetrics
  /** Sites flagged abnormal/watch — utils/overview.ts's siteVerdicts, never a
   * second definition. Failures are NOT in here. */
  outlierCount: number
  /** How many of failureBreakdown's four causes came back failed. */
  failedCauses: number
  /** Sites of this parameter with no measurement. */
  missing: number
  measured: number
  total: number
  /** Clustering over 이상 ∪ 실패 sites. */
  clustering: SectorClustering
}

export interface MeasurementVerdict {
  tone: VerdictTone
  badge: string
  /** The headline, already assembled. */
  sentence: VerdictSegment[]
  /** 1 − σ(이상치 제외)/σ, in 0..1 — the share of σ a handful of sites carry.
   * null when there is no σ to divide (fewer than 2 measured sites, or every
   * site identical); a 0 there would read as "the outliers contribute nothing"
   * rather than "the question has no answer". */
  outlierShare: number | null
}

/** Above this ratio the two sigmas agree, so no single group of sites is doing
 * the inflating and the sentence does not claim one is. Mirrors the reading
 * guide the CDU card used to print in prose. */
const SHARE_CLAUSE_MAX_RATIO = 0.8

/**
 * 확인 필요 when anything went wrong — a failed cause or a flagged site.
 * Otherwise 정상. There is no third level: an "이상" tier would need a severity
 * scale this view cannot compute without a baseline.
 */
export const measurementVerdict = (input: VerdictInput): MeasurementVerdict => {
  const attention = input.failedCauses > 0 || input.outlierCount > 0
  const share = outlierShare(input.metrics)
  return {
    tone: attention ? 'attention' : 'ok',
    badge: attention ? '확인 필요' : '정상',
    sentence: sentenceOf(input, share),
    outlierShare: share
  }
}

/**
 * How much of σ the extreme sites carry.
 *
 * The flatness guard is `range`, not `std`. On a wafer whose sites all read the
 * same value, `mean` picks up float residue (29.4 × 3 ÷ 3 is 29.399999999999995),
 * so `std` lands around 3e-15 while the MAD is an exact 0 — and the ratio then
 * reports that outliers carry 100% of a σ that does not exist. `range` is a
 * subtraction of two of the observations, so on identical sites it is exactly 0
 * and the question is refused instead of answered wrongly.
 */
const outlierShare = (metrics: CduMetrics): number | null => {
  const spread = metrics.spread
  if (!spread || !(spread.range > 0)) return null
  return 1 - spread.madSigma / spread.std
}

/** `CD_TOP 29.58 nm` — the level, or the parameter alone when nothing measured. */
const head = (input: VerdictInput): VerdictSegment[] => {
  const level = input.metrics.level
  if (!level) return [{ text: `${input.paramLabel} ` }]
  return [
    { text: `${input.paramLabel} ` },
    { text: formatFixed(level.mean, 2), kind: 'num' },
    ...(input.unit ? [{ text: ` ${input.unit}` }] : [])
  ]
}

/** `, 그 site 들은 우측(E)에 몰려 있습니다.` — appended only on a clustered
 * verdict, so a scattered wafer is never described as having a hot spot. */
const clusterTail = (clustering: SectorClustering): VerdictSegment[] | null => {
  const top = clustering.sectors[0]
  if (clustering.verdict !== 'clustered' || !top) return null
  return [{ text: ', 그 site 들은 ' }, { text: top.label }, { text: '에 몰려 있습니다.' }]
}

const sentenceOf = (input: VerdictInput, share: number | null): VerdictSegment[] => {
  if (!input.metrics.level) {
    return [...head(input), { text: '— 측정된 site 가 없습니다.' }]
  }

  const cluster = clusterTail(input.clustering)

  if (input.outlierCount > 0) {
    const outliers: VerdictSegment = { text: `이상 ${input.outlierCount} site`, kind: 'bad' }
    // The σ-share clause is claimed only when the two sigmas actually disagree.
    // Where they agree the wafer is broadly spread, and saying "n% comes from
    // these sites" would credit them with a concentration that is not there.
    if (share !== null && share >= 1 - SHARE_CLAUSE_MAX_RATIO) {
      return [
        ...head(input),
        { text: ' · σ 의 ' },
        { text: `${Math.round(share * 100)}%`, kind: 'num' },
        { text: ' 가 ' },
        outliers,
        cluster ? { text: ' 에서 나오고' } : { text: ' 에서 나옵니다.' },
        ...(cluster ?? [])
      ]
    }
    return cluster
      ? [...head(input), { text: ' · ' }, outliers, ...cluster.slice(1)]
      : [...head(input), { text: ' · ' }, outliers, { text: ' 가 있고 σ 는 웨이퍼 전체에 퍼져 있습니다.' }]
  }

  if (input.missing > 0) {
    return [
      ...head(input),
      { text: ' · 이상 site 는 없고, ' },
      { text: `${input.missing} site`, kind: 'bad' },
      { text: ' 가 측정되지 않았습니다.' }
    ]
  }

  if (input.failedCauses > 0) {
    return [
      ...head(input),
      { text: ' · 이상 site 는 없지만 실패 원인 ' },
      { text: `${input.failedCauses}`, kind: 'bad' },
      { text: ' 건이 잡혀 있습니다.' }
    ]
  }

  return [
    ...head(input),
    { text: ' · ' },
    { text: `${input.total}`, kind: 'num' },
    { text: ' site 모두 측정되었고 이상 site 는 없습니다.' }
  ]
}
