<template>
  <div class="min-w-0">
    <p class="mb-1.5 sk-label">
      PARAMETER
    </p>
    <!-- The list is the payload's own `parameters` — the names measured under
         the picked recipe, read off the same rows the skew is computed from.
         So there is no "lookup failed" state to caption here any more: if the
         payload came, the list came with it. -->
    <USelectMenu
      v-model:search-term="term"
      :model-value="parameter ?? ALL_PARAMETERS"
      ignore-filter
      :items="items"
      :disabled="lock !== null"
      :search-input="parameterNames.length > 8 ? { placeholder: 'parameter 검색…' } : false"
      :loading="lock === null && pending && !parameterNames.length"
      icon="i-lucide-crosshair"
      color="neutral"
      variant="outline"
      class="w-full"
      :ui="POPPER_UI"
      @update:model-value="onParameter($event === ALL_PARAMETERS ? '' : String($event))"
    >
      <template #default>
        <span
          class="truncate font-mono text-[13px]"
          :title="parameter ?? ALL_PARAMETERS"
        >{{ parameter ?? ALL_PARAMETERS }}</span>
      </template>
    </USelectMenu>
    <p class="mt-1.5 sk-field-label leading-relaxed">
      <!-- Disabled rather than hidden while it cannot be used: the control has
           to be visible for the procedure (비교 대상 → 분석 조건) to read as
           two steps, and the caption says which step is missing. -->
      <template v-if="lock === 'no-recipe'">
        먼저 위에서 recipe 를 고르십시오 — parameter 는 그 recipe 의 측정 데이터에서 고릅니다.
      </template>
      <template v-else-if="lock === 'no-data'">
        이 비교 대상에는 계산할 측정 데이터가 없습니다 — 아래 안내를 보십시오.
      </template>
      <template v-else-if="pending && !parameterNames.length">
        비교 대상의 측정 데이터에서 parameter 를 읽는 중입니다.
      </template>
      <!-- An empty list is an ANSWER: the recipe's runs carried no named
           feature (stabilisation shots only). Folding is then the only view,
           and the caption says so instead of implying a pick is missing. -->
      <template v-else-if="!parameterNames.length">
        이 recipe 의 측정 데이터에 이름 있는 parameter 가 없습니다 — 측정 항목을 모두 합쳐 판정합니다.
      </template>
      <template v-else-if="overflowed">
        {{ matched.length.toLocaleString() }}건 중 {{ PARAMETER_LIMIT }}건만 표시합니다.
      </template>
      <template v-else>
        {{ parameterNames.length.toLocaleString() }}개 측정됨 · 비우면 측정 항목을 모두 합쳐 계산합니다.
      </template>
    </p>
  </div>
</template>

<script setup lang="ts">
import { filterByTerm } from '~/utils/hardwareCompare'

export type ParameterLock = 'no-recipe' | 'no-data' | null

// Sentinel for "no filter". A plain '' cannot be a USelectMenu item, and null
// would render as an empty row rather than as a readable choice.
const ALL_PARAMETERS = '전체 (모든 측정 항목)'
// A recipe holds tens of parameters, not thousands — this cap exists so a
// pathological recipe cannot lock the page, not because it is expected to bind.
const PARAMETER_LIMIT = 200

// NuxtUI pins the dropdown to the trigger (`w-(--reka-select-trigger-width)` in
// .nuxt/ui/select-menu.ts). Parameter names are short, but the rule is kept
// with the recipe picker's so the two menus behave alike; bounded by the
// viewport so a narrow window cannot push it off-screen.
const POPPER_UI = {
  content: 'w-auto min-w-full max-w-[min(48rem,calc(100vw-2rem))]',
  item: 'font-mono text-[13px]'
}

const props = defineProps<{
  /** One measured feature of the picked recipe; null folds every feature together. */
  parameter: string | null
  /** Distinct parameter names the picked recipe measured, from the payload. */
  parameterNames: string[]
  /** The payload carrying the list is still in flight — empty is not yet empty. */
  pending: boolean
  /**
   * Why the control cannot be used yet, or null when it can. `no-recipe`: the
   * first step is not taken; `no-data`: the recipe's answer is unavailable, so
   * there is no row set to list features from.
   */
  lock: ParameterLock
}>()

const emit = defineEmits<{
  (e: 'update:parameter', value: string | null): void
}>()

const onParameter = (value: string) => emit('update:parameter', value || null)

const term = ref('')
const matched = computed(() => filterByTerm(props.parameterNames, term.value, name => name))
const overflowed = computed(() => matched.value.length > PARAMETER_LIMIT)
// The sentinel stays at the top so clearing the filter is always one click away.
const items = computed(() => [ALL_PARAMETERS, ...matched.value.slice(0, PARAMETER_LIMIT)])

// The search box keeps its term across openings, so a term typed against the
// PREVIOUS recipe's parameters would silently filter the new recipe's list down
// to nothing — the menu would read as "this recipe has no parameters". The
// list changes identity with the payload, which is exactly when to clear.
watch(() => props.parameterNames, () => {
  term.value = ''
})
</script>
