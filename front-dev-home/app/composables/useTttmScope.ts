import { recipeStillStands } from '~/utils/tttmRecipeScope'
import { useRecipeSearchApi } from '~/composables/useRecipeSearchApi'
import { useTttmApi } from '~/composables/useTttmApi'
import { useTttmSettings } from '~/composables/useTttmSettings'
import type { ToolType } from '~/utils/toolType'

/**
 * The (tools, recipe, parameter) scope both lab pages compare under, plus the
 * two catalogues their pickers need.
 *
 * Shared rather than written twice because the SCOPE is shared: TTTM and
 * pm-tune read and write one persisted entry per (toolType, fab), so a group
 * shown on one page is the same group on the other. Duplicating this wiring is
 * how the two would start to drift — one page clearing the parameter on a
 * recipe change and the other not is enough to make them disagree.
 *
 * Both catalogues are their own requests, so a slow catalogue never delays the
 * skew payload the pages are actually about.
 */
export const useTttmScope = (toolType: string, fabName: string) => {
  const settings = useTttmSettings()
  const scoped = computed(() => settings.read(toolType, fabName))
  const recipeId = computed(() => scoped.value.recipeId)
  const parameter = computed(() => scoped.value.parameter)

  const { fetchRecipeParameters } = useRecipeSearchApi()
  const { fetchTttmRecipes } = useTttmApi()

  // Sourced from measurement history, NOT recipe-search's Redis catalogue. The
  // catalogue lists every recipe that exists; here a recipe nobody ran carries
  // no information at all, so offering it can only waste a click on "no data".
  // The measured set is also far smaller, which is what makes this picker
  // usable where the 50,000-name catalogue needed a search box.
  const { data: recipeList, pending: recipesPending } = useAsyncData(
    `tttm-recipes:${toolType}:${fabName}`,
    () => fetchTttmRecipes(toolType, fabName)
  )
  // Already sorted by evidence server-side (tools, then runs), and that order
  // is kept: the recipes that can actually support a comparison come first.
  // Re-sorting alphabetically here would throw that away.
  const recipeNames = computed(() =>
    (recipeList.value?.rows ?? []).map(row => row.recipe_id)
  )
  /** Recipes only ONE tool measured — pickable, but they cannot yield a pair. */
  const recipesWithoutAPair = computed(() =>
    new Set(
      (recipeList.value?.rows ?? [])
        .filter(row => row.tools < 2)
        .map(row => row.recipe_id)
    )
  )

  // A stored recipe that the fab has not measured is DROPPED, silently, back to
  // 전체. It is not merely a pick that answers "no data": the parameter list is
  // resolved through recipe-open, which derives its .idp location from a
  // measurement, so an unmeasured recipe 502s that request at the office and
  // leaves the picker empty with no stated reason. See utils/tttmRecipeScope.
  //
  // `null` while the list is in flight or failed, so a slow or blipping
  // catalogue never throws away a working setup — the whole point of persisting
  // it. Clearing writes null, which reconciles to null, so this settles at once.
  watch(
    [recipeList, recipeId],
    () => {
      // `recipeNames` is the same mapping, already cached by Vue — but it folds
      // "no answer yet" into an empty array, and that distinction is the whole
      // guard here, so the null case is restored from `recipeList` itself.
      const measured = recipeList.value ? recipeNames.value : null
      if (!recipeStillStands(recipeId.value, measured)) {
        settings.setRecipe(toolType, fabName, null)
      }
    },
    { immediate: true }
  )

  // Keyed on (toolType, fab) with the recipe WATCHED rather than baked into the
  // key — the same rule useTttmCheck follows, and for the same reason: a key
  // carrying the recipe accumulates one cache entry per recipe ever opened, and
  // a user searching a 50,000-name catalogue opens a lot of them.
  // `error` is READ, not ignored: recipe-open is the one call here that reaches
  // the tool over FTP, so it fails for reasons that have nothing to do with the
  // user's pick — an unreachable tool, an incomplete meas_hist document. Left
  // unread, all of those render as "이 recipe 에서 측정 parameter 를 찾지
  // 못했습니다", which says the recipe is empty when the truth is we could not
  // look. The page must stay usable either way, so this only labels the caption.
  const { data: parameterList, pending: parametersPending, error: parametersError } = useAsyncData(
    `tttm-parameters:${toolType}:${fabName}`,
    () => recipeId.value
      ? fetchRecipeParameters({
          toolType: toolType as ToolType,
          fabName,
          recipeName: recipeId.value
        })
      : Promise.resolve(null),
    { watch: [recipeId] }
  )
  // Deduped: a row of idp_image_info is one image DEFINITION, so one parameter
  // occupies several rows — the raw row count is not a parameter list.
  const parameterNames = computed(() =>
    [...new Set((parameterList.value?.rows ?? []).map(row => row.Parameter).filter(Boolean))].sort()
  )

  // The PARAMETER goes stale the same way the recipe does, and was left
  // half-fixed: a recipe can survive an .idp revision that renames or drops one
  // of its features, and the stored parameter then names nothing. The office
  // filters its rows to that name, finds none, and answers "측정 이력이
  // 없습니다" — which blames the recipe while the stale half is the parameter.
  //
  // Same three-state rule as the recipe: `parameterList` is null while the
  // lookup is in flight OR failed, and a failed lookup must not erase a working
  // pick — that is exactly the recoverable FTP error `parametersError` labels.
  watch(
    [parameterList, parameter],
    () => {
      const known = parameterList.value ? parameterNames.value : null
      if (parameter.value && known && !known.includes(parameter.value)) {
        settings.setParameter(toolType, fabName, null)
      }
    },
    { immediate: true }
  )

  const onSelectedTools = (next: string[]) => settings.setTools(toolType, fabName, next)
  const onRecipe = (next: string | null) => settings.setRecipe(toolType, fabName, next)
  const onParameter = (next: string | null) => settings.setParameter(toolType, fabName, next)

  return {
    scoped,
    recipeId,
    parameter,
    recipeNames,
    recipesWithoutAPair,
    recipesPending,
    parameterNames,
    parametersPending,
    parametersError,
    onSelectedTools,
    onRecipe,
    onParameter
  }
}
