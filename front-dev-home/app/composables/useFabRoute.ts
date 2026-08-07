import type { ToolType } from '~/stores/navigation'
import { DEFAULT_FAB, parseFabSegment } from '~/utils/fab'

// Every [fab] page's shared boilerplate: parse the (possibly multi) URL segment,
// seed the store, and keep it synced. Replaces the copy-pasted
// `String(route.params.fab).toUpperCase()` + setFab + watch block, which would
// corrupt the store with a raw "R3,M16B" string once segments can be lists.
export const useFabRoute = (toolType: ToolType) => {
  const route = useRoute()
  const { setToolType, setFabs } = useNavigation()

  const fabs = computed(() => parseFabSegment(route.params.fab as string | string[] | undefined))
  const primaryFab = computed(() => fabs.value[0] ?? DEFAULT_FAB)
  const fabsKey = computed(() => fabs.value.join(','))

  setToolType(toolType)
  setFabs(fabs.value)

  // Guard on the raw param: on leave-navigation the param empties, and syncing
  // that would clobber the remembered selection with the R3 fallback.
  watch(() => route.params.fab, (next) => {
    if (next == null || next === '') return
    setFabs(parseFabSegment(next as string | string[]))
  })

  return { fabs, primaryFab, fabsKey }
}
