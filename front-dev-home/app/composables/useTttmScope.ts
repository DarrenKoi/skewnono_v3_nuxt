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

  // Keyed on (toolType, fab) with the recipe WATCHED rather than baked into the
  // key — the same rule useTttmCheck follows, and for the same reason: a key
  // carrying the recipe accumulates one cache entry per recipe ever opened, and
  // a user searching a 50,000-name catalogue opens a lot of them.
  const { data: parameterList, pending: parametersPending } = useAsyncData(
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
    onSelectedTools,
    onRecipe,
    onParameter
  }
}
