import { useRecipeSearchApi } from '~/composables/useRecipeSearchApi'
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

  const { fetchRecipeList, fetchRecipeParameters } = useRecipeSearchApi()

  const { data: recipeList, pending: recipesPending } = useAsyncData(
    `tttm-recipes:${toolType}:${fabName}`,
    () => fetchRecipeList({ toolType: toolType as ToolType, fabNames: [fabName] })
  )
  const recipeNames = computed(() =>
    [...new Set((recipeList.value?.rows ?? []).map(row => row.recipe_name))].sort()
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
    recipesPending,
    parameterNames,
    parametersPending,
    onSelectedTools,
    onRecipe,
    onParameter
  }
}
