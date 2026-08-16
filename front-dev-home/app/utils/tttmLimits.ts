// The two thresholds the TTTM screens draw, and what each one actually is.
//
// They are NOT the same kind of number, and the screen was wrong for a while
// because it treated the smaller one as an action limit:
//
//   PM_BM_ACTION_LIMIT_NM  a rule about ONE tool against the fleet consensus.
//                          Cross it and the tool goes to PM/BM. This is fab
//                          policy, not a property of the measurement.
//   MEASUREMENT_FLOOR_NM   how repeatable the ABBA test itself is. Below this
//                          two tools are not distinguishable, so a difference
//                          smaller than it is noise, not a finding.
//
// The tolerance knob is a THIRD quantity again — a pairwise limit used for
// N배화 grouping — and lives in the payload's `tolerance_range`, not here,
// because the server owns it and the user moves it.
//
// Note two in-spec tools can still sit 2 × PM_BM_ACTION_LIMIT_NM apart (one at
// +0.15, one at −0.15), so passing the per-tool rule does not imply any two
// tools match each other.

/**
 * The fab's tool-management rule, as a FRACTION OF CD.
 *
 * user-confirmed 2026-08-16, in two parts:
 *   - "we manage the tools running inside +-0.15nm from median. If a tool
 *     bigger than that, should go through the PM/BM."
 *   - "모니터 wafer는 15nm에서 +-0.15를 기준으로 함."
 *
 * 0.15 nm at a 15 nm CD is exactly 1%, and the same conversation established
 * that the limit scales with pattern size. So the ratio is the rule and the
 * 0.15 nm figure is just its value on the monitor wafer.
 *
 * This matters because the scaling is large: at 50 nm the limit is 0.50 nm and
 * at 100 nm it is 1.0 nm, both far outside the tolerance knob's 0.01–0.20 nm
 * range. A screen that applies 0.15 nm everywhere is wrong by the CD ratio.
 */
export const PM_BM_ACTION_LIMIT_RATIO = 0.01

/** The CD the ±0.15 nm figure was quoted at (the monitor wafer). */
export const MONITOR_WAFER_CD_NM = 15

/**
 * The action limit in nm for a given nominal CD.
 *
 * `PM_BM_ACTION_LIMIT_RATIO * MONITOR_WAFER_CD_NM` reproduces the familiar
 * 0.15 nm, which is the check to run when this looks wrong.
 */
export const actionLimitNm = (nominalCdNm: number) =>
  PM_BM_ACTION_LIMIT_RATIO * nominalCdNm

/** A CD to draw limits against, and whether it was measured or assumed. */
export interface NominalCd {
  nm: number
  /** true = no CD in the payload, so MONITOR_WAFER_CD_NM stood in for it. */
  assumed: boolean
}

/**
 * Resolve the CD a limit should be drawn against.
 *
 * `median_cd_nm` is nullable across the whole contract — an office adapter
 * with no CD alongside its skew statistics returns null rather than inventing
 * one — so every screen needs the same fallback, and every screen needs to say
 * it fell back. Returning `assumed` rather than just a number is what stops a
 * caller from rendering the monitor wafer's 0.15 nm as if it had been measured.
 *
 * A non-positive CD is treated as missing: the contract forbids it (see
 * `test_fleet_today_median_cd_is_positive_when_present`), and dividing by 1%
 * of zero would silently pass every tool instead of failing loudly.
 */
export const resolveNominalCd = (medianCdNm: number | null | undefined): NominalCd =>
  typeof medianCdNm === 'number' && medianCdNm > 0
    ? { nm: medianCdNm, assumed: false }
    : { nm: MONITOR_WAFER_CD_NM, assumed: true }

/**
 * A skew expressed as a fraction of its own cell's action limit — 1.0 sits
 * exactly on the limit.
 *
 * This is the index that makes recipes at different pattern sizes comparable:
 * 0.24 nm is alarming at a 15 nm CD (1.6x the limit) and unremarkable at 68 nm
 * (0.35x), so raw nanometres cannot be ranked across recipes at all. Combining
 * several recipes means taking the WORST fraction, not the largest nm.
 *
 * Caveat worth keeping in view: the 1% ratio is fab policy for ONE TOOL against
 * consensus. Applying it to a pairwise skew is our extension — which is why
 * this returns an index to rank by, and the screens do not paint a pair red for
 * crossing 1.0 the way FleetStatus does for a single tool.
 *
 * That caveat is a naming rule too. Pairwise surfaces say "CD 대비 N×" and must
 * NOT say 한계 (limit): PairMatrix said 한계 for one commit, which asserted a
 * pairwise threshold the fab never stated. 한계 belongs to FleetStatus alone,
 * where the rule really is one tool against consensus.
 */
export const fractionOfLimit = (skewNm: number, nominalCdNm: number) =>
  skewNm / actionLimitNm(nominalCdNm)

/**
 * The worst pair in a skew matrix, as a CD-normalised index. `null` when the
 * matrix has no measured pair at all.
 *
 * This is the ranking key. A cell's severity is its WORST pair, not its
 * average: a group is only as matched as its loosest member, so averaging
 * would let one bad pair hide behind four good ones.
 *
 * The same reduction is what combines several recipes later — each recipe
 * reduces to its worst normalised pair, then the recipes reduce by max. That
 * is why this takes a matrix rather than living inside the component: the
 * recipe-level version is this function applied one level up.
 *
 * Reads the upper triangle only. The matrix is symmetric by contract, so
 * scanning both halves would double the work to reach the same maximum.
 */
export const worstFractionOfLimit = (
  values: (number | null)[][],
  nominalCdNm: number
): number | null => {
  let worst: number | null = null
  for (let row = 0; row < values.length; row++) {
    for (let col = row + 1; col < (values[row]?.length ?? 0); col++) {
      const skew = values[row]?.[col]
      if (typeof skew !== 'number') continue // null = pair not TTTM-able
      const index = fractionOfLimit(skew, nominalCdNm)
      if (worst === null || index > worst) worst = index
    }
  }
  return worst
}

/**
 * ±0.05 nm — the self-ABBA measurement uncertainty reported by Kawada 2009,
 * whose authors are our tool vendor (Hitachi High-Tech).
 *
 * A floor, never an action line. It was the red threshold in FleetStatus until
 * 2026-08-16, which painted a tool as needing attention at a third of the real
 * limit.
 */
export const MEASUREMENT_FLOOR_NM = 0.05
