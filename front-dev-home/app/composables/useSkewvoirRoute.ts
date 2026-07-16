import type { LocationQueryRaw } from 'vue-router'
import type { MeasHistToolType } from '~/composables/useMeasHistApi'
import type { SkewvoirSelection, SkewvoirViewKind } from '~/composables/useSkewvoirWorkspace'
import type { AnalysisScope } from '~/utils/skewvoirAnalysis/types'

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

  // Analysis scope — held in the URL SEPARATELY from the selection count so a
  // single-focus screen can still be an explicit `set` (comparison-ready) and a
  // multi-msr link can be forced back to `single`. Normalisation: an explicit
  // `scope=single|set` always wins; when ABSENT (every link authored before this
  // param existed) it is DERIVED from the set size so old links keep working.
  const scope = computed<AnalysisScope>(() => {
    const explicit = qstr(route.query.scope)
    if (explicit === 'single' || explicit === 'set') return explicit
    return msrList.value.length > 1 ? 'set' : 'single'
  })

  // New shareable params — Task 3 only PARSES/NORMALISES/PRESERVES them; their
  // consumers are later tasks. `site` = focused canonical site key; `ref` =
  // reference-MSR override; the rest are opaque passthrough strings for now.
  const siteParam = computed<string | undefined>(() => qstr(route.query.site))
  const refParam = computed<string | undefined>(() => qstr(route.query.ref))
  const metricParam = computed<string | undefined>(() => qstr(route.query.metric))
  const grainParam = computed<string | undefined>(() => qstr(route.query.grain))
  const xParam = computed<string | undefined>(() => qstr(route.query.x))
  const yParam = computed<string | undefined>(() => qstr(route.query.y))
  // Gallery review-queue filter preset (e.g. 'priority' — the 이상·실패 우선
  // hand-off from the overview). Same opaque-passthrough treatment as
  // site/ref/metric/grain above.
  const filterParam = computed<string | undefined>(() => qstr(route.query.filter))

  // Serialize a selection (+ view + explicit set) into an analysis-link query.
  // `msrs` defaults to the focus alone; pass a curated list for the trend set.
  const toQuery = (
    sel: SkewvoirSelection,
    v: SkewvoirViewKind = DEFAULT_VIEW,
    msrs?: string[],
    scopeValue?: AnalysisScope
  ) => ({
    lot: sel.lot,
    recipe: sel.recipe,
    eq: sel.eq,
    mp: sel.mp,
    msr: sel.msr,
    msrs: (msrs && msrs.length ? msrs : [sel.msr]).filter(Boolean).join(','),
    cap: sel.capturedAt,
    view: v,
    ...(scopeValue ? { scope: scopeValue } : {})
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
  ) => navigateTo({ path: analysisPath, query: toQuery(focus, v, msrs, 'set') })

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

  // Low-level in-place query patch (same replace/no-history pattern as the
  // setters above). Three-valued per key:
  //   • string    → write the value
  //   • null       → CLEAR the param from the URL (e.g. removing `site`)
  //   • undefined  → leave the existing value UNTOUCHED (so a deep-link focus
  //                  with no meas_hist row keeps its lot/eq/cap)
  const patchQuery = (patch: Record<string, string | null | undefined>) => {
    const cleared = new Set(
      Object.entries(patch).filter(([, v]) => v === null).map(([k]) => k)
    )
    const next: LocationQueryRaw = {}
    for (const [key, value] of Object.entries(route.query)) {
      if (!cleared.has(key)) next[key] = value
    }
    for (const [key, value] of Object.entries(patch)) {
      if (typeof value === 'string') next[key] = value
    }
    router.replace({ path: analysisPath, query: next })
  }

  // Move the focus MSR in place — rewrites `msr` and the focus identity fields
  // `lot`/`eq`/`cap`, while PRESERVING `msrs`/`view`/`mp` (and everything else).
  // A no-history replace, so Back still returns to search. Identity fields that
  // are absent (deep-link MSR with no meas_hist row) are left untouched so we
  // never blank a still-correct lot/eq/cap.
  const setFocus = (focus: { msr: string, lot?: string, eq?: string, cap?: string }) =>
    patchQuery({ msr: focus.msr, lot: focus.lot, eq: focus.eq, cap: focus.cap })

  // Setters for the new shareable params (consumed by later tasks). `null`
  // clears the param from the URL.
  const setSite = (siteKey: string | null) => patchQuery({ site: siteKey })
  const setRef = (msr: string | null) => patchQuery({ ref: msr })
  const setMetric = (metric: string | null) => patchQuery({ metric })
  const setGrain = (grain: string | null) => patchQuery({ grain })
  const setXY = (x: string | null, y: string | null) => patchQuery({ x, y })
  const setFilter = (filter: string | null) => patchQuery({ filter })

  const goSearch = () => navigateTo(basePath)

  // The canonical shareable link for the current screen.
  const shareUrl = () => (import.meta.client ? window.location.href : analysisPath)

  return {
    basePath,
    analysisPath,
    selection,
    view,
    msrList,
    scope,
    siteParam,
    refParam,
    metricParam,
    grainParam,
    xParam,
    yParam,
    filterParam,
    openAnalysis,
    openAnalysisSet,
    setView,
    setMsrs,
    setParam,
    patchQuery,
    setFocus,
    setSite,
    setRef,
    setMetric,
    setGrain,
    setXY,
    setFilter,
    goSearch,
    shareUrl
  }
}
