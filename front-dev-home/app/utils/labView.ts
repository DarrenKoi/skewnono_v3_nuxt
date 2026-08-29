// The two views of the 실험실 analysis page, and the words each one wears.
//
// One page since 2026-08-30, two routes. `/tttm` and `/pm-planning` used to be
// two components that shared a scope, a persisted entry, a request and 18 of
// their ~30 computeds, and documented the overlap in eight "same as TttmView"
// comments rather than removing it. They are now one component (`LabView.vue`)
// picking its results section by this slug.
//
// Both routes SURVIVED the merge on purpose. The slug is an identity, not a
// path: `_logging/feature_map.py` files activity under it, `utils/pageIdentity.ts`
// carries `/pm-tune` as an alias of `pm-planning`, `back_dev_home/` has a
// feature folder per slug, and 실험실 lists the two separately because they
// answer two different questions. Collapsing one into the other is the
// 2026-08-17 pm-tune rename, which cost a 47-file sweep to undo.
//
// The slugs ARE the route file names (`pages/ebeam/cd-sem/[fab]/<slug>.vue`),
// which is what lets the sub-tabs build their links by swapping the last path
// segment instead of knowing the route shape.

export type LabViewSlug = 'tttm' | 'pm-planning'

/** Tab order = reading order: measure the group, then plan against it. */
export const LAB_VIEWS = [
  { value: 'tttm', label: '장비간 스큐', icon: 'i-lucide-git-compare' },
  { value: 'pm-planning', label: 'PM 플래닝', icon: 'i-lucide-wrench' }
] as const satisfies readonly { value: LabViewSlug, label: string, icon: string }[]

export interface LabViewCopy {
  title: string
  subtitle: string
  loading: string
  /** No recipe picked — what THIS view would compute once there is one. */
  noScope: string
  /** The server answered `available: false`. */
  unavailableTitle: string
  /** Fewer than two tools in the basis — no pair, so no group. */
  tooFewTools: string
}

// Kept out of the template because every line here has a twin: side by side in
// one table, a change to one view's wording is read against the other's, which
// is how the two pages drifted into saying the same thing three different ways.
export const LAB_COPY: Record<LabViewSlug, LabViewCopy> = {
  'tttm': {
    title: '장비간 스큐 관리',
    subtitle: 'Recipe가 점유하는 셀에서 서로 잘 맞는(N배화) 측정 장비 조합을 추천합니다.',
    loading: '장비간 스큐 데이터를 불러오는 중입니다.',
    noScope: '위 비교 대상에서 recipe 를 고르면 그 recipe 가 점유한 셀로 장비간 스큐를 계산합니다.',
    unavailableTitle: '비교할 결과가 없습니다.',
    tooFewTools: '위 장비 모델 그룹에서 장비를 고르면 그 장비들 사이의 스큐를 계산합니다.'
  },
  'pm-planning': {
    title: 'PM 플래닝',
    subtitle: '하드웨어를 만질 기회는 PM 창뿐입니다 — 그때 N배화 그룹의 중심에 맞추도록 parameter 별 조정량을 제시합니다. N이 커질수록 서로 대체 측정할 수 있는 장비가 늘어납니다.',
    loading: 'Fleet 데이터를 불러오는 중입니다.',
    noScope: '위 비교 대상에서 recipe 를 고르면 그 recipe 기준으로 N배화 그룹과 튜닝 목표를 계산합니다.',
    unavailableTitle: '튜닝 목표를 낼 수 없습니다.',
    tooFewTools: '위 장비 모델 그룹에서 장비를 고르면 그 장비들로 N배화 그룹과 튜닝 목표를 계산합니다.'
  }
}
