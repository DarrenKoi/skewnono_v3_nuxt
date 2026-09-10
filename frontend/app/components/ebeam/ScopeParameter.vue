<template>
  <div class="min-w-0">
    <p class="mb-1.5 sk-label">
      PARAMETER
    </p>
    <!-- The list is the payload's own `parameters` — the names measured under
         the picked recipe, read off the same rows the skew is computed from.
         So there is no "lookup failed" state to caption here: if the payload
         came, the list came with it.

         Multi-select: the N배화 group is "tools that match on EACH picked
         parameter", and the 장비 그룹 배치도 is PCA over the same picks — so
         a pick is a column of the analysis, and several columns is the normal
         case. Empty = every parameter. -->
    <USelectMenu
      v-model:search-term="term"
      :model-value="parameters"
      multiple
      ignore-filter
      :reset-search-term-on-select="false"
      :items="items"
      :disabled="lock !== null"
      :search-input="parameterNames.length > 8 ? { placeholder: 'parameter 검색…' } : false"
      :loading="lock === 'loading'"
      icon="i-lucide-crosshair"
      color="neutral"
      variant="outline"
      class="w-full"
      :ui="{ ...scopeMenuUi, itemTrailingIcon: 'hidden' }"
      @update:model-value="emit('update:parameters', [...($event as string[])])"
    >
      <template #default>
        <span
          class="truncate font-mono text-[13px]"
          :title="parameters.join(', ') || ALL_PARAMETERS"
        >
          <template v-if="parameters.length">
            <span class="font-sans font-semibold">{{ parameters.length }}개</span> · {{ parameters.join(', ') }}
          </template>
          <template v-else>{{ ALL_PARAMETERS }}</template>
        </span>
      </template>

      <template #item-leading="{ item }">
        <AppSelectCheck :checked="selectedSet.has(String(item))" />
      </template>

      <template #content-bottom>
        <div
          class="flex items-center gap-1 border-t border-(--sk-border-soft) p-1"
          @keydown.enter.stop
          @keydown.space.stop
        >
          <UButton
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-list-checks"
            :disabled="parameters.length === parameterNames.length"
            @click="emit('update:parameters', [...parameterNames])"
          >
            모두 선택
          </UButton>
          <UButton
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-eraser"
            :disabled="parameters.length === 0"
            @click="emit('update:parameters', [])"
          >
            해제 (전체)
          </UButton>
        </div>
      </template>
    </USelectMenu>
    <p class="mt-1.5 sk-field-label leading-relaxed">
      <!-- Disabled rather than hidden while it cannot be used: the control has
           to be visible for the procedure (비교 대상 → 분석 조건) to read as
           two steps, and the caption says which step is missing. -->
      <template v-if="lock === 'no-recipe'">
        먼저 위에서 recipe 를 고르십시오 — parameter 는 그 recipe 의 측정 데이터에서 고릅니다.
      </template>
      <template v-else-if="lock === 'no-request'">
        위 데이터 요청을 누르면 이 recipe 의 측정 데이터에서 parameter 를 읽습니다.
      </template>
      <template v-else-if="lock === 'no-data'">
        이 비교 대상에는 계산할 측정 데이터가 없습니다 — 아래 안내를 보십시오.
      </template>
      <template v-else-if="lock === 'loading'">
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
      <template v-else-if="parameters.length">
        {{ parameterNames.length.toLocaleString() }}개 중 {{ parameters.length }}개 선택 · 고른 항목마다 맞아야 N배화이고, 배치도는 이 항목들의 PCA 로 그립니다.
      </template>
      <template v-else>
        {{ parameterNames.length.toLocaleString() }}개 측정됨 · 비우면 모든 항목으로 판정하고, 배치도는 전체 항목의 PCA 로 그립니다. 여러 개를 고를 수 있습니다.
      </template>
    </p>
  </div>
</template>

<script setup lang="ts">
import { useMenuFilter } from '~/composables/useMenuFilter'
import { scopeMenuUi } from '~/utils/scopeMenuUi'
import type { AnalysisLock } from '~/utils/tttmRecipeScope'

const ALL_PARAMETERS = '전체 (모든 측정 항목)'
// A recipe holds tens of parameters, not thousands — this cap exists so a
// pathological recipe cannot lock the page, not because it is expected to bind.
const PARAMETER_LIMIT = 200

const props = defineProps<{
  /** Measured features of the picked recipe to fold; empty folds every feature. */
  parameters: string[]
  /** Distinct parameter names the picked recipe measured, from the payload. */
  parameterNames: string[]
  /** Why the control is inert, or null when it is live — see analysisLock. */
  lock: AnalysisLock
}>()

const emit = defineEmits<{
  (e: 'update:parameters', value: string[]): void
}>()

const selectedSet = computed(() => new Set(props.parameters))

// `parameterNames` is content-stable (useTttmScope), so the term resets when
// the LIST changes — a new recipe — not on every refetch of the same list.
// No sentinel row: "전체" is the empty selection, reached by 해제 below.
const { term, matched, overflowed, items } = useMenuFilter(
  () => props.parameterNames,
  { limit: PARAMETER_LIMIT }
)
</script>
