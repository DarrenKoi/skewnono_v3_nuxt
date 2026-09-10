import type { ToolType } from '~/stores/navigation'
import { readRecipeOwnerFabQuery } from '~/utils/recipeView'

/**
 * The six recipe detail pages' shared boilerplate (cd-sem/hv-sem ×
 * open/lateral/meas-hist): resolve which fab OWNS the recipe being viewed.
 * Detail links carry the owner in a `fab_name` query because the path's
 * [fab] segment keeps the full (possibly multi) sidebar selection; when the
 * query is absent — direct URL entry, pre-multi-fab bookmarks — fall back to
 * the selection's primary fab. Calls useFabRoute for its nav-store seeding
 * side effect, exactly as each page did individually.
 */
export const useRecipeDetailRouting = (toolType: ToolType) => {
  const { primaryFab } = useFabRoute(toolType)
  const route = useRoute()
  const ownerFab = computed(() => readRecipeOwnerFabQuery(route) || primaryFab.value)
  return { ownerFab }
}

/**
 * The detail VIEWS' counterpart: the route's OWN [fab] segment for back/nav
 * links, not the owner fab — a multi-fab sidebar selection ("r3,m16b") must
 * survive the trip back to recipe-search even though the recipe's data was
 * fetched from a single owner fab. The fallback (owner fab, lowercased) only
 * fires when the view is mounted without a [fab] route param.
 *
 * `ownerFab` is a getter, not a string, so the computed re-runs when the
 * caller's prop changes — passing `props.fab` by value would freeze it.
 */
export const useRouteFabSegment = (ownerFab: () => string) => {
  const route = useRoute()
  return computed(() => String(route.params.fab || ownerFab().toLowerCase()))
}
