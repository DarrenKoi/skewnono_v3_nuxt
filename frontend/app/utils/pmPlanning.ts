// The pm-planning payload's shared value types.
//
// Was also the page's focus-ranking logic (maxAxisSkew / rankFocusTargets),
// deleted with 다음 PM 후보 랭킹 on 2026-08-28: the 장비 그룹 배치도 already
// shows which tools sit outside the group, so a second ranked list of the same
// tools was one more place for the two answers to disagree. The payload's
// `defaults` block (focus_n / advisory_threshold) went with it on 2026-08-30.
export type BeamCondition = '500V' | '800V'
export type ScanAxis = 'X' | 'Y'

export interface CellSkew {
  beam: BeamCondition
  axis: ScanAxis
  skew: number
  current_value: number
  median: number
  gap: number
}
