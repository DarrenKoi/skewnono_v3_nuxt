<template>
  <div>
    <p class="mb-1.5 sk-label">
      RECIPE
    </p>
    <!-- Searchable, not a plain <select>: R3 alone answers with 50,000 recipe
         names, and rendering that many <option> nodes locks the page. Search is
         the only way to reach one, so the list is filtered and capped. -->
    <USelectMenu
      v-model:search-term="recipeTerm"
      :model-value="recipeId ?? ALL_RECIPES"
      ignore-filter
      :items="recipeItems"
      :search-input="{ placeholder: 'recipe 이름 검색 — 비우면 전체' }"
      :loading="recipesPending"
      icon="i-lucide-search"
      color="neutral"
      variant="outline"
      class="w-full"
      @update:model-value="onRecipe($event === ALL_RECIPES ? '' : String($event))"
    />
    <p class="mt-1.5 sk-field-label">
      <template v-if="recipesOverflowed">
        {{ recipeMatchCount.toLocaleString() }}건 중 {{ RECIPE_LIMIT }}건만 표시합니다 — 더 좁혀서 검색하십시오.
      </template>
      <template v-else>
        {{ recipeNames.length.toLocaleString() }}건 · recipe 를 고르면 그 recipe 만으로 다시 계산합니다.
      </template>
    </p>

    <p class="mt-3.5 mb-1.5 sk-label">
      PARAMETER
    </p>
    <!-- Disabled rather than hidden while no recipe is picked: the control has
         to be visible for the two-step (recipe → parameter) to read as one
         choice, and the caption below says why it cannot be used yet. A
         parameter name is recipe-local, so there is nothing to list until a
         recipe narrows it. -->
    <USelectMenu
      v-model:search-term="parameterTerm"
      :model-value="parameter ?? ALL_PARAMETERS"
      ignore-filter
      :items="parameterItems"
      :disabled="!recipeId"
      :search-input="parameterNames.length > 8 ? { placeholder: 'parameter 검색…' } : false"
      :loading="parametersPending"
      icon="i-lucide-crosshair"
      color="neutral"
      variant="outline"
      class="w-full"
      @update:model-value="onParameter($event === ALL_PARAMETERS ? '' : String($event))"
    />
    <p class="mt-1.5 sk-field-label leading-relaxed">
      <template v-if="!recipeId">
        recipe 를 먼저 고르십시오 — parameter 이름은 recipe 안에서만 뜻이 있습니다.
      </template>
      <template v-else-if="parametersPending">
        parameter 목록을 불러오는 중입니다.
      </template>
      <template v-else-if="!parameterNames.length">
        이 recipe 에서 측정 parameter 를 찾지 못했습니다.
      </template>
      <template v-else-if="parametersOverflowed">
        {{ parameterMatchCount.toLocaleString() }}건 중 {{ PARAMETER_LIMIT }}건만 표시합니다.
      </template>
      <template v-else>
        {{ parameterNames.length.toLocaleString() }}개 · 하나를 고르면 그 측정 항목만으로 장비간 스큐를 다시 계산해
        같은 그룹인지 판정합니다.
      </template>
    </p>
  </div>
</template>

<script setup lang="ts">
import { filterByTerm } from '~/utils/hardwareCompare'

// Sentinels for "no filter". A plain '' cannot be a USelectMenu item, and null
// would render as an empty row rather than as a readable choice.
const ALL_RECIPES = '전체 (서버 기본)'
const ALL_PARAMETERS = '전체 (모든 측정 항목)'
// The recipe catalogue is ~50,000 names per fab; this many rows is already more
// than anyone scrolls, and the caption says how many matched so the cap never
// hides the fact that it capped.
const RECIPE_LIMIT = 100
// A recipe holds tens of parameters, not thousands — this cap exists so a
// pathological recipe cannot lock the page, not because it is expected to bind.
const PARAMETER_LIMIT = 200

const props = defineProps<{
  recipeId: string | null
  recipeNames: string[]
  recipesPending: boolean
  /** One measured feature of `recipeId`; null folds every feature together. */
  parameter: string | null
  /** Distinct parameter names of the picked recipe. Empty until one is picked. */
  parameterNames: string[]
  parametersPending: boolean
}>()

const emit = defineEmits<{
  (e: 'update:recipeId' | 'update:parameter', value: string | null): void
}>()

const onRecipe = (value: string) => emit('update:recipeId', value || null)
const onParameter = (value: string) => emit('update:parameter', value || null)

const recipeTerm = ref('')
const recipeMatched = computed(() => filterByTerm(props.recipeNames, recipeTerm.value, name => name))
const recipeMatchCount = computed(() => recipeMatched.value.length)
const recipesOverflowed = computed(() => recipeMatchCount.value > RECIPE_LIMIT)
// The sentinel stays at the top so clearing the filter is always one click away,
// even when the search box is narrowing 50,000 names down to a hundred.
const recipeItems = computed(() => [ALL_RECIPES, ...recipeMatched.value.slice(0, RECIPE_LIMIT)])

const parameterTerm = ref('')
const parameterMatched = computed(() =>
  filterByTerm(props.parameterNames, parameterTerm.value, name => name)
)
const parameterMatchCount = computed(() => parameterMatched.value.length)
const parametersOverflowed = computed(() => parameterMatchCount.value > PARAMETER_LIMIT)
const parameterItems = computed(() =>
  [ALL_PARAMETERS, ...parameterMatched.value.slice(0, PARAMETER_LIMIT)]
)

// The search box keeps its term across openings, so a term typed against the
// PREVIOUS recipe's parameters would silently filter the new recipe's list down
// to nothing — the menu would read as "this recipe has no parameters".
watch(() => props.recipeId, () => {
  parameterTerm.value = ''
})
</script>
