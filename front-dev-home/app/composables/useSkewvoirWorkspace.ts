import type { MeasHistToolType } from '~/composables/useMeasHistApi'

// The analysis workspace exposes 5 view modes in the left rail. Search is no
// longer one of them — it is a separate landing route. The active view is
// driven by the URL `view` query param via useSkewvoirRoute (single source of
// truth), so an analysis screen is fully reproducible from its link.
export type SkewvoirViewKind
  = | 'dashboard'
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

// A measurement selection. Carried entirely in the URL query so analysis links
// are shareable (live re-query: opening the link rebuilds this from the query).
export interface SkewvoirSelection {
  lot: string
  recipe: string
  eq: string
  mp: string
  // The measurement (msr) id — the stable detail-data key. Carried in the URL so
  // the analysis route can fetch the MsrFile directly and links stay self-sufficient.
  msr: string
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
  { kind: 'dashboard', index: 1, label: 'Dashboard', sub: 'Single Measurement', icon: 'i-lucide-layout-dashboard' },
  { kind: 'position-stack', index: 2, label: '위치 비교', sub: 'Position Stack', icon: 'i-lucide-layers' },
  { kind: 'time-series', index: 3, label: 'Time-Series', sub: 'Multi-measurement Trend', icon: 'i-lucide-trending-up' },
  { kind: 'correlation', index: 4, label: '상관 / 분포', sub: 'Correlation & Distribution', icon: 'i-lucide-scatter-chart' },
  { kind: 'gallery', index: 5, label: '이미지 갤러리', sub: 'SEM Gallery', icon: 'i-lucide-images' }
] as const

export const useSkewvoirWorkspace = (toolType: MeasHistToolType, toolLabel: string) => {
  const eqType = toolType === 'hv-sem' ? 'HV-CD-SEM' : 'CD-SEM'
  const skRoute = useSkewvoirRoute(toolType)

  // selection + active view both derive from the URL (via useSkewvoirRoute).
  const selection = skRoute.selection
  const activeKind = skRoute.view
  // Explicit curated comparison set for the Time-Series view (msr ids in URL).
  const msrList = skRoute.msrList

  // Pinned filters / health stay mock-seeded for this pass; the MP filter
  // mirrors the URL selection when present so the rail and the link agree.
  const pinnedFilters = useState<SkewvoirPinnedFilters>(`skewvoir-filters-${toolType}`, () => ({
    area: 'DRAM',
    fab: 'R3',
    eqType,
    period: '2026-05-01 → 11',
    mp: 'WAFER',
    flags: ['3σ > 0.5', 'outliers']
  }))

  const health = useState<SkewvoirHealth>(`skewvoir-health-${toolType}`, () => ({ scans: 24, outliers: 15 }))

  // Switching views just rewrites the `view` query param (keeps the rest).
  const openView = (kind: SkewvoirViewKind) => skRoute.setView(kind)
  const goSearch = () => skRoute.goSearch()

  return {
    toolType,
    toolLabel,
    eqType,
    viewModes: SKEWVOIR_VIEW_MODES,
    selection,
    activeKind,
    msrList,
    pinnedFilters,
    health,
    openView,
    goSearch,
    openAnalysis: skRoute.openAnalysis,
    openAnalysisSet: skRoute.openAnalysisSet,
    setMsrs: skRoute.setMsrs,
    setParam: skRoute.setParam,
    shareUrl: skRoute.shareUrl,
    analysisPath: skRoute.analysisPath,
    basePath: skRoute.basePath
  }
}

export type SkewvoirWorkspace = ReturnType<typeof useSkewvoirWorkspace>
