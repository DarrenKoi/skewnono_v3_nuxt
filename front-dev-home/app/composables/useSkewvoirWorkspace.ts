import type { MeasHistToolType } from '~/composables/useMeasHistApi'

// The 6 left-rail view modes. A tab is always one of these kinds; the search
// landing is the home view and is never closable.
export type SkewvoirViewKind
  = | 'search'
    | 'dashboard'
    | 'position-stack'
    | 'time-series'
    | 'correlation'
    | 'gallery'

export interface SkewvoirViewMode {
  kind: SkewvoirViewKind
  index: number
  label: string
  sub: string
  icon: string
}

export interface SkewvoirTab {
  id: string
  kind: SkewvoirViewKind
  label: string
  badge?: string
  closable: boolean
}

export interface SkewvoirSelection {
  lot: string
  recipe: string
  eq: string
  capturedAt: string
}

export interface SkewvoirPinnedFilters {
  area: string
  fab: string
  eqType: string
  period: string
  mp: string
  flags: string[]
}

export interface SkewvoirHealth {
  scans: number
  outliers: number
}

export const SKEWVOIR_VIEW_MODES: readonly SkewvoirViewMode[] = [
  { kind: 'search', index: 1, label: '검색', sub: 'Search / Landing', icon: 'i-lucide-search' },
  { kind: 'dashboard', index: 2, label: 'Dashboard', sub: 'Single Measurement', icon: 'i-lucide-layout-dashboard' },
  { kind: 'position-stack', index: 3, label: '위치 비교', sub: 'Position Stack', icon: 'i-lucide-layers' },
  { kind: 'time-series', index: 4, label: 'Time-Series', sub: 'Multi-measurement Trend', icon: 'i-lucide-trending-up' },
  { kind: 'correlation', index: 5, label: '상관 / 분포', sub: 'Correlation & Distribution', icon: 'i-lucide-scatter-chart' },
  { kind: 'gallery', index: 6, label: '이미지 갤러리', sub: 'SEM Gallery', icon: 'i-lucide-images' }
] as const

const labelForKind = (kind: SkewvoirViewKind): string =>
  SKEWVOIR_VIEW_MODES.find(mode => mode.kind === kind)?.label ?? kind

export const useSkewvoirWorkspace = (toolType: MeasHistToolType, toolLabel: string) => {
  const eqType = toolType === 'hv-sem' ? 'HV-CD-SEM' : 'CD-SEM'

  const tabs = useState<SkewvoirTab[]>(`skewvoir-tabs-${toolType}`, () => [
    { id: 'search', kind: 'search', label: '검색', closable: false },
    { id: 'dashboard-demo', kind: 'dashboard', label: 'RK2W016.13', badge: 'DRAM', closable: true },
    { id: 'position-demo', kind: 'position-stack', label: '위치 비교', closable: true },
    { id: 'time-series-demo', kind: 'time-series', label: 'Time-Series', closable: true }
  ])

  const activeTabId = useState<string>(`skewvoir-active-${toolType}`, () => 'search')

  const selection = useState<SkewvoirSelection | null>(`skewvoir-selection-${toolType}`, () => ({
    lot: 'RK2W016.13',
    recipe: 'RK2A_DSVTEOSETCLN',
    eq: 'MCD026',
    capturedAt: '05. 11. 오전 06:29'
  }))

  const pinnedFilters = useState<SkewvoirPinnedFilters>(`skewvoir-filters-${toolType}`, () => ({
    area: 'DRAM',
    fab: 'R3',
    eqType,
    period: '2026-05-01 → 11',
    mp: 'WAFER',
    flags: ['3σ > 0.5', 'outliers']
  }))

  const health = useState<SkewvoirHealth>(`skewvoir-health-${toolType}`, () => ({ scans: 24, outliers: 15 }))

  const activeTab = computed(() => tabs.value.find(tab => tab.id === activeTabId.value) ?? tabs.value[0])
  const activeKind = computed<SkewvoirViewKind>(() => activeTab.value?.kind ?? 'search')

  const activate = (id: string) => {
    if (tabs.value.some(tab => tab.id === id)) activeTabId.value = id
  }

  // Opening a view mode focuses its existing tab, or appends a fresh one.
  const openView = (kind: SkewvoirViewKind) => {
    const existing = tabs.value.find(tab => tab.kind === kind)
    if (existing) {
      activeTabId.value = existing.id
      return
    }
    const id = `${kind}-${Date.now()}`
    tabs.value.push({ id, kind, label: labelForKind(kind), closable: kind !== 'search' })
    activeTabId.value = id
  }

  const closeTab = (id: string) => {
    const index = tabs.value.findIndex(tab => tab.id === id)
    const tab = tabs.value[index]
    if (!tab || !tab.closable) return

    tabs.value = tabs.value.filter(t => t.id !== id)
    if (activeTabId.value === id) {
      const fallback = tabs.value[index - 1] ?? tabs.value[0]
      activeTabId.value = fallback?.id ?? 'search'
    }
  }

  const newTab = () => openView('search')

  return {
    toolType,
    toolLabel,
    eqType,
    viewModes: SKEWVOIR_VIEW_MODES,
    tabs,
    activeTabId,
    activeTab,
    activeKind,
    selection,
    pinnedFilters,
    health,
    activate,
    openView,
    closeTab,
    newTab
  }
}

export type SkewvoirWorkspace = ReturnType<typeof useSkewvoirWorkspace>
