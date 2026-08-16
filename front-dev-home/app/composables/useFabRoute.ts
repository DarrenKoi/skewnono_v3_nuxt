import type { ToolType } from '~/stores/navigation'
import { DEFAULT_FAB, fabSegment, parseFabSegment } from '~/utils/fab'
import { isSingleFabFeature, matchFeatureFromPath } from '~/utils/features'

// Every [fab] page's shared boilerplate: parse the (possibly multi) URL segment,
// seed the store, and keep it synced. Replaces the copy-pasted
// `String(route.params.fab).toUpperCase()` + setFab + watch block, which would
// corrupt the store with a raw "R3,M16B" string once segments can be lists.
export const useFabRoute = (toolType: ToolType) => {
  const route = useRoute()
  const router = useRouter()
  const { setToolType, setFabs } = useNavigation()

  const parsed = computed(() => parseFabSegment(route.params.fab as string | string[] | undefined))

  // Single-fab pages (tttm, pm-tune) collapse a multi-fab segment to the
  // primary: the URL is normalized (replace, so Back does not bounce through
  // the multi form) and the store keeps only the fab the page actually shows.
  // The sidebar already refuses to BUILD multi-fab URLs on these pages
  // (useNavigation.singleFabPage); this is the safety net for hand-typed URLs
  // and links carried over from multi-fab pages.
  const singleFab = computed(() => {
    const feature = matchFeatureFromPath(route.path)
    return feature !== '' && isSingleFabFeature(feature)
  })
  const fabs = computed(() => (singleFab.value ? parsed.value.slice(0, 1) : parsed.value))
  const primaryFab = computed(() => fabs.value[0] ?? DEFAULT_FAB)
  const fabsKey = computed(() => fabs.value.join(','))

  const normalizeUrl = () => {
    if (!singleFab.value || parsed.value.length <= 1) return
    const raw = route.params.fab
    const segment = Array.isArray(raw) ? raw.join(',') : String(raw ?? '')
    if (!segment) return
    router.replace({
      path: route.path.replace(`/${segment}/`, `/${fabSegment(primaryFab.value)}/`),
      query: route.query
    })
  }

  setToolType(toolType)
  setFabs(fabs.value)
  normalizeUrl()

  // Guard on the raw param: on leave-navigation the param empties, and syncing
  // that would clobber the remembered selection with the R3 fallback.
  watch(() => route.params.fab, (next) => {
    if (next == null || next === '') return
    setFabs(fabs.value)
    normalizeUrl()
  })

  return { fabs, primaryFab, fabsKey }
}
