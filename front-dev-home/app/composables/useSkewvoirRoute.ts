import type { MeasHistToolType } from '~/composables/useMeasHistApi'
import type { SkewvoirSelection, SkewvoirViewKind } from '~/composables/useSkewvoirWorkspace'
import type { AnalysisScope } from '~/utils/skewvoirAnalysis/types'
import {
  DEFAULT_VIEW,
  applyQueryPatch,
  encodeParam,
  parseMsrList,
  parseScope,
  parseSelection,
  parseView,
  qstr,
  toAnalysisQuery,
  type FocusIdentity,
  type QueryPatch
} from '~/utils/skewvoirAnalysis/routeQuery'

// URL <-> analysis-state bridge. The analysis workspace keeps no private copy
// of "what am I looking at" — the URL query is the single source of truth, which
// is exactly what makes an analysis screen shareable: paste the link, get the
// same screen (live re-query, not a frozen snapshot).
//
// Every parsing / serialisation / patching rule lives in
// utils/skewvoirAnalysis/routeQuery.ts (pure, unit-tested); this composable only
// binds those rules to the router.

export const useSkewvoirRoute = (toolType: MeasHistToolType) => {
  const route = useRoute()
  const router = useRouter()

  const tool = toolType === 'hv-sem' ? 'hv-sem' : 'cd-sem'
  const basePath = `/ebeam/${tool}/skewvoir`
  const analysisPath = `${basePath}/analysis`

  const selection = computed<SkewvoirSelection | null>(() => parseSelection(route.query))

  const view = computed<SkewvoirViewKind>(() => parseView(route.query.view))

  // The Time-Series comparison set — an EXPLICIT, user-curated list of msr ids
  // carried in the URL (?msrs=a,b,c).
  const msrList = computed<string[]>(() => parseMsrList(route.query))

  // Analysis scope (single | set), normalised from the URL.
  const scope = computed<AnalysisScope>(() => parseScope(route.query))

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

  // Navigate from search into analysis for a single picked measurement.
  const openAnalysis = (sel: SkewvoirSelection, v: SkewvoirViewKind = DEFAULT_VIEW) =>
    navigateTo({ path: analysisPath, query: toAnalysisQuery(sel, v) })

  // Navigate from search into analysis with a curated comparison set (focus +
  // the explicit msr list); defaults to the Time-Series view.
  const openAnalysisSet = (
    focus: SkewvoirSelection,
    msrs: string[],
    v: SkewvoirViewKind = 'time-series'
  ) => navigateTo({ path: analysisPath, query: toAnalysisQuery(focus, v, msrs, 'set') })

  // Switch the active view without losing the rest of the selection. replace()
  // keeps view changes out of the back-stack so Back returns to search.
  const setView = (v: SkewvoirViewKind) =>
    router.replace({ path: analysisPath, query: { ...route.query, view: v } })

  // Rewrite the curated comparison set in place (used by the Time-Series picker).
  const setMsrs = (list: string[]) =>
    router.replace({ path: analysisPath, query: { ...route.query, msrs: list.filter(Boolean).join(',') } })

  // Change the active parameter (URL `mp`) in place. encodeParam so the unnamed
  // dummy MP is selectable too — its empty name would otherwise write a blank
  // `mp` that reads straight back as absent.
  const setParam = (mp: string) =>
    router.replace({ path: analysisPath, query: { ...route.query, mp: encodeParam(mp) } })

  // Low-level in-place query patch (same replace/no-history pattern as the
  // setters above). Three-valued per key — see QueryPatch.
  const patchQuery = (patch: QueryPatch) =>
    router.replace({ path: analysisPath, query: applyQueryPatch(route.query, patch) })

  // Move the focus MSR in place — rewrites `msr` and the focus identity fields
  // `lot`/`eq`/`cap`, while PRESERVING `msrs`/`view`/`mp` (and everything else).
  // A no-history replace, so Back still returns to search. Identity fields that
  // are absent (deep-link MSR with no meas_hist row) are left untouched so we
  // never blank a still-correct lot/eq/cap.
  const setFocus = (focus: FocusIdentity) => patchQuery(focus)

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
