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

// ── 보기 (which analyses are drawn) ────────────────────────────────────────
//
// The two views hold the SAME analysis; what differed was which cards each drew
// of it. Those cards are now options, and the two routes are the presets that
// turn them on — which is what keeps the URL meaningful after the merge.
//
// Grouped rather than one option per card, because some cards only mean
// something together. `배치도` keeps the map with `제외 장비`'s companion the
// map annotates in red — split, the line has no caption and the caption has no
// line. `PM 튜닝` carries the 튜닝할 장비 bar with it because 튜닝 목표 and
// Up gate are both computed from that pick: a checkbox that silently needed
// another control would be a checkbox that lies.

export type LabPanel = 'verdict' | 'map' | 'matrix' | 'trend' | 'pm'

export const LAB_PANELS = [
  { value: 'verdict', label: '그룹 판정', hint: '추천 N배화 그룹 · 제외 장비' },
  { value: 'map', label: '배치도', hint: '장비 그룹 배치도 · consensus 잔차' },
  { value: 'matrix', label: '장비쌍 행렬', hint: '셀별 pairwise 스큐' },
  { value: 'trend', label: '추세', hint: '잔차 트렌드 · MDC 타임라인' },
  { value: 'pm', label: 'PM 튜닝', hint: '튜닝할 장비 · 튜닝 목표 · Up gate' }
] as const satisfies readonly { value: LabPanel, label: string, hint: string }[]

const PANEL_VALUES = new Set<string>(LAB_PANELS.map(p => p.value))

/**
 * What each route opens with. `장비간 스큐` is the whole comparison; PM 플래닝
 * keeps the 배치도 because the tuning target is defined as a position ON that
 * map — the table beside it is that map read as numbers.
 */
export const DEFAULT_PANELS: Record<LabViewSlug, LabPanel[]> = {
  'tttm': ['verdict', 'map', 'matrix', 'trend'],
  'pm-planning': ['map', 'pm']
}

/**
 * localStorage is user-writable, so a stored selection is untrusted input:
 * unknown names are dropped and the canonical ORDER is restored, because the
 * order the panels render in is editorial (the evidence reads top to bottom,
 * each fact once) and not the order they happened to be clicked in.
 *
 * An empty selection is legitimate — it is what unticking everything means, and
 * the view says so where the results would be. Only a non-array is refused.
 */
export const normalizePanels = (raw: unknown): LabPanel[] | null => {
  if (!Array.isArray(raw)) return null
  const picked = new Set(raw.filter((v): v is LabPanel => typeof v === 'string' && PANEL_VALUES.has(v)))
  return LAB_PANELS.filter(p => picked.has(p.value)).map(p => p.value)
}
