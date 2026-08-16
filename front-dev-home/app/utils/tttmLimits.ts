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

/**
 * ±0.05 nm — the self-ABBA measurement uncertainty reported by Kawada 2009,
 * whose authors are our tool vendor (Hitachi High-Tech).
 *
 * A floor, never an action line. It was the red threshold in FleetStatus until
 * 2026-08-16, which painted a tool as needing attention at a third of the real
 * limit.
 */
export const MEASUREMENT_FLOOR_NM = 0.05
