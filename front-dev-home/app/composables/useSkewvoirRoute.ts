import type { MeasHistToolType } from '~/composables/useMeasHistApi'
import type { SkewvoirSelection, SkewvoirViewKind } from '~/composables/useSkewvoirWorkspace'

// URL <-> analysis-state bridge. The analysis workspace keeps no private copy
// of "what am I looking at" — the URL query is the single source of truth, which
// is exactly what makes an analysis screen shareable: paste the link, get the
// same screen (live re-query, not a frozen snapshot).

const DEFAULT_VIEW: SkewvoirViewKind = 'dashboard'
const VIEW_KINDS: readonly SkewvoirViewKind[] = [
  'dashboard',
  'position-stack',
  'time-series',
  'correlation',
  'gallery'
]

// A LocationQueryValue may be string | string[] | null; collapse to a usable string.
const qstr = (v: unknown): string | undefined => {
  const first = Array.isArray(v) ? v[0] : v
  return typeof first === 'string' && first.length > 0 ? first : undefined
}

export const useSkewvoirRoute = (toolType: MeasHistToolType) => {
  const route = useRoute()
  const router = useRouter()

  const tool = toolType === 'hv-sem' ? 'hv-sem' : 'cd-sem'
  const basePath = `/ebeam/${tool}/skewvoir`
  const analysisPath = `${basePath}/analysis`

  // Rebuild the selection from the query. No lot => no selection (empty state).
  const selection = computed<SkewvoirSelection | null>(() => {
    const lot = qstr(route.query.lot)
    if (!lot) return null
    return {
      lot,
      recipe: qstr(route.query.recipe) ?? '',
      eq: qstr(route.query.eq) ?? '',
      mp: qstr(route.query.mp) ?? 'WAFER',
      msr: qstr(route.query.msr) ?? '',
      capturedAt: qstr(route.query.cap) ?? '—'
    }
  })

  const view = computed<SkewvoirViewKind>(() => {
    const v = qstr(route.query.view) as SkewvoirViewKind | undefined
    return v && VIEW_KINDS.includes(v) ? v : DEFAULT_VIEW
  })

  // The Time-Series comparison set — an EXPLICIT, user-curated list of msr ids
  // carried in the URL (?msrs=a,b,c). The focus `msr` is always a member; an
  // empty list falls back to just the focus so a single-pick still renders.
  const msrList = computed<string[]>(() => {
    const raw = qstr(route.query.msrs)
    const ids = raw ? raw.split(',').map(s => s.trim()).filter(Boolean) : []
    const fallback = qstr(route.query.msr)
    return ids.length ? ids : (fallback ? [fallback] : [])
  })

  // Serialize a selection (+ view + explicit set) into an analysis-link query.
  // `msrs` defaults to the focus alone; pass a curated list for the trend set.
  const toQuery = (
    sel: SkewvoirSelection,
    v: SkewvoirViewKind = DEFAULT_VIEW,
    msrs?: string[]
  ) => ({
    lot: sel.lot,
    recipe: sel.recipe,
    eq: sel.eq,
    mp: sel.mp,
    msr: sel.msr,
    msrs: (msrs && msrs.length ? msrs : [sel.msr]).filter(Boolean).join(','),
    cap: sel.capturedAt,
    view: v
  })

  // Navigate from search into analysis for a single picked measurement.
  const openAnalysis = (sel: SkewvoirSelection, v: SkewvoirViewKind = DEFAULT_VIEW) =>
    navigateTo({ path: analysisPath, query: toQuery(sel, v) })

  // Navigate from search into analysis with a curated comparison set (focus +
  // the explicit msr list); defaults to the Time-Series view.
  const openAnalysisSet = (
    focus: SkewvoirSelection,
    msrs: string[],
    v: SkewvoirViewKind = 'time-series'
  ) => navigateTo({ path: analysisPath, query: toQuery(focus, v, msrs) })

  // Switch the active view without losing the rest of the selection. replace()
  // keeps view changes out of the back-stack so Back returns to search.
  const setView = (v: SkewvoirViewKind) =>
    router.replace({ path: analysisPath, query: { ...route.query, view: v } })

  // Rewrite the curated comparison set in place (used by the Time-Series picker).
  const setMsrs = (list: string[]) =>
    router.replace({ path: analysisPath, query: { ...route.query, msrs: list.filter(Boolean).join(',') } })

  // Change the active parameter (URL `mp`) in place.
  const setParam = (mp: string) =>
    router.replace({ path: analysisPath, query: { ...route.query, mp } })

  const goSearch = () => navigateTo(basePath)

  // The canonical shareable link for the current screen.
  const shareUrl = () => (import.meta.client ? window.location.href : analysisPath)

  return {
    basePath,
    analysisPath,
    selection,
    view,
    msrList,
    toQuery,
    openAnalysis,
    openAnalysisSet,
    setView,
    setMsrs,
    setParam,
    goSearch,
    shareUrl
  }
}
