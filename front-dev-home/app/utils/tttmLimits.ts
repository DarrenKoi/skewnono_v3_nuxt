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
 * ±0.15 nm from the fleet median. Beyond this the tool is sent to PM/BM.
 *
 * user-confirmed 2026-08-16: "in the fab, we manage the tools running inside
 * +-0.15nm from median. If a tool bigger than that, should go through the
 * PM/BM."
 *
 * OFFICE-VERIFY: whether this limit is fixed in nm or scales with the measured
 * pattern's CD. The same conversation raised that a larger pattern should
 * tolerate a larger skew, which would make this a ratio rather than a constant.
 * Treat the value as the absolute limit for the current monitor pattern until
 * that is settled.
 */
export const PM_BM_ACTION_LIMIT_NM = 0.15

/**
 * ±0.05 nm — the self-ABBA measurement uncertainty reported by Kawada 2009,
 * whose authors are our tool vendor (Hitachi High-Tech).
 *
 * A floor, never an action line. It was the red threshold in FleetStatus until
 * 2026-08-16, which painted a tool as needing attention at a third of the real
 * limit.
 */
export const MEASUREMENT_FLOOR_NM = 0.05
