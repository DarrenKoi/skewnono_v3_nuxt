/** Which analyses get drawn — see LAB_PANELS for what each one carries. */
export type LabPanel = 'verdict' | 'map' | 'matrix' | 'trend'

export const LAB_PANELS = [
  { value: 'verdict', label: '그룹 판정', hint: '추천 N배화 그룹 · 제외 장비' },
  { value: 'map', label: '배치도', hint: '장비 그룹 배치도 · 튜닝 목표 · 기간 잔차' },
  { value: 'matrix', label: '장비쌍 행렬', hint: '셀별 pairwise 스큐' },
  { value: 'trend', label: '추세', hint: '잔차 트렌드 · MDC 타임라인' }
] as const satisfies readonly { value: LabPanel, label: string, hint: string }[]

const PANEL_VALUES = new Set<string>(LAB_PANELS.map(p => p.value))

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
