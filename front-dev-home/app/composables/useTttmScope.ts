import { offeredParameters, pickStillStands } from '~/utils/tttmRecipeScope'
import { useTttmApi } from '~/composables/useTttmApi'
import { useTttmSettings } from '~/composables/useTttmSettings'

/**
 * The (tools, recipe, parameter) scope both lab pages compare under, the
 * recipe catalogue their picker needs, and the skew payload the scope selects.
 *
 * Shared rather than written twice because the SCOPE is shared: TTTM and
 * pm-tune read and write one persisted entry per (toolType, fab), so a group
 * shown on one page is the same group on the other. Duplicating this wiring is
 * how the two would start to drift — one page clearing the parameter on a
 * recipe change and the other not is enough to make them disagree.
 *
 * The payload lives here too, because the parameter catalogue is ON it: the
 * procedure is tools + recipe → the recipe's measurement rows → the parameters
 * those rows carry, and the payload is that second step. It used to come from
 * recipe-open's .idp over FTP — a request that failed for reasons unrelated to
 * the recipe and could name features nobody measured — which is why the
 * parameter picker had an error caption and the views each fetched the payload
 * themselves.
 *
 * The recipe catalogue is its own request, so a slow catalogue never delays
 * the skew payload the pages are actually about.
 */
export const useTttmScope = (toolType: string, fabName: string) => {
  const settings = useTttmSettings()
  const scoped = computed(() => settings.read(toolType, fabName))
  const recipeId = computed(() => scoped.value.recipeId)
  const parameter = computed(() => scoped.value.parameter)

  const { fetchTttmRecipes, useTttmCheck } = useTttmApi()

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
  // 전체. It is not merely a pick that answers "no data": at the office an
  // unmeasured recipe has no rows to answer with, and the stale pick is
  // invisible until someone opens the page on the company network. See
  // utils/tttmRecipeScope.
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
      if (!pickStillStands(recipeId.value, measured)) {
        settings.setRecipe(toolType, fabName, null)
      }
    },
    { immediate: true }
  )

  // The request still fires without a recipe, and must: the tool roster the
  // scope bar's model-group dropdowns are built from arrives on this payload,
  // so gating the FETCH would leave the user nothing to pick from. Only the
  // results are gated — the views own that empty state.
  const { data: payload, pending } = useTttmCheck(
    toolType,
    fabName,
    () => recipeId.value,
    () => parameter.value
  )

  // The picker's catalogue, as the payload states it. Empty until a recipe is
  // picked and its payload has landed — `offeredParameters` is the three-state
  // reading (no answer / answering another recipe / answer) and this folds the
  // first two into "nothing to list yet", which is all the picker shows.
  const parameterNames = computed(() =>
    offeredParameters(payload.value, recipeId.value) ?? []
  )

  // The PARAMETER goes stale the same way the recipe does: a recipe can
  // survive an .idp revision that renames or drops one of its features, and
  // the stored parameter then names nothing. The office filters its rows to
  // that name, finds none, and answers "측정 이력이 없습니다" — which blames the
  // recipe while the stale half is the parameter.
  //
  // Same three-state rule as the recipe, through `offeredParameters`: a payload
  // that is not an answer to THIS recipe must not erase a working pick.
  watch(
    [payload, parameter],
    () => {
      const offered = offeredParameters(payload.value, recipeId.value)
      if (!pickStillStands(parameter.value, offered)) {
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
    payload,
    pending,
    parameterNames,
    onSelectedTools,
    onRecipe,
    onParameter
  }
}
