// The 실험실 analysis page: which analyses it can draw, and which it opens with.
//
// One page, ONE route since 2026-09-01. `/tttm` and `/pm-planning` used to be
// two components that shared a scope, a persisted entry, a request and 18 of
// their ~30 computeds; the 2026-08-30 merge made them one component
// (`LabView.vue`) addressed by two routes, and this change drops the second
// route as well. PM 튜닝 is a panel the reader ticks, not a screen to navigate
// to — ticking it brings the 튜닝할 장비 bar with it.
//
// The slug is an IDENTITY, not a path, so dropping the route drops neither:
// `pages/ebeam/cd-sem/[fab]/pm-planning.vue` stays as a redirect stub for old
// bookmarks, `back_dev_home/pm_planning/` still answers the pm panel's query,
// `_logging/feature_map.py` still files that activity under the `pm_planning`
// slug (it maps API paths, not page paths), and `utils/pageIdentity.ts` still
// carries `/pm-planning` and its `/pm-tune` alias so past activity keeps its
// label.

/** Which analyses get drawn — see LAB_PANELS for what each one carries. */
export type LabPanel = 'verdict' | 'map' | 'matrix' | 'trend' | 'pm'

// ── 보기 (which analyses are drawn) ────────────────────────────────────────
//
// Grouped rather than one option per card, because some cards only mean
// something together. `배치도` keeps the map with `제외 장비`'s companion the
// map annotates in red — split, the line has no caption and the caption has no
// line. `PM 튜닝` carries the 튜닝할 장비 bar with it because 튜닝 목표 and
// Up gate are both computed from that pick: a checkbox that silently needed
// another control would be a checkbox that lies.

export const LAB_PANELS = [
  { value: 'verdict', label: '그룹 판정', hint: '추천 N배화 그룹 · 제외 장비' },
  { value: 'map', label: '배치도', hint: '장비 그룹 배치도 · consensus 잔차' },
  { value: 'matrix', label: '장비쌍 행렬', hint: '셀별 pairwise 스큐' },
  { value: 'trend', label: '추세', hint: '잔차 트렌드 · MDC 타임라인' },
  { value: 'pm', label: 'PM 튜닝', hint: '튜닝할 장비 · 튜닝 목표 · Up gate' }
] as const satisfies readonly { value: LabPanel, label: string, hint: string }[]

const PANEL_VALUES = new Set<string>(LAB_PANELS.map(p => p.value))

/**
 * What the page draws before the reader has an opinion — the old /tttm preset.
 *
 * `pm` is deliberately OFF: the page answers "어느 장비끼리 맞는가" first, and
 * PM 튜닝 is the follow-up question asked ABOUT one tool. Turning it on is what
 * makes 튜닝할 장비 appear, so a default-on pm would open the page asking for a
 * pick nobody had a reason to make yet.
 */
export const DEFAULT_PANELS: LabPanel[] = ['verdict', 'map', 'matrix', 'trend']

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

/**
 * The stored 보기 selection, read.
 *
 * Until 2026-09-01 the value was keyed by route slug — `{"tttm": [...],
 * "pm-planning": [...]}` — because each route had its own preset. One route
 * now, so the `tttm` selection IS the selection and the `pm-planning` one is
 * dropped: it described a screen that no longer exists, and it always had pm
 * ticked, which would silently reopen the tuning bar for anyone whose last
 * visit happened to be the other tab.
 */
export const storedPanels = (raw: unknown): LabPanel[] => {
  const value = Array.isArray(raw) ? raw : (raw as { tttm?: unknown } | null)?.tttm
  return normalizePanels(value) ?? [...DEFAULT_PANELS]
}
