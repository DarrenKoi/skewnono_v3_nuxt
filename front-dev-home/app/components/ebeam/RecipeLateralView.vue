<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ColumnFiltersState } from '@tanstack/vue-table'
import type { Fab } from '~/stores/navigation'
import type {
  LateralRecipeResponse,
  LateralRecipeRow,
  LateralRecipeToolType
} from '~/composables/useLateralRecipeApi'
import { chipClass } from '~/utils/chipClass'
import { readRecipeNameQuery, recipeTableUi } from '~/utils/recipeView'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: LateralRecipeToolType
}>()

const route = useRoute()
const { fetchLateralRecipe } = useLateralRecipeApi()

const recipeName = computed(() => readRecipeNameQuery(route))
const backRoute = computed(() => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`)
const { goBack: goBackToList } = useHistoryBack(backRoute)

const cacheKey = computed(() => `lateral:${props.toolType}:${props.fab || 'ALL'}:${recipeName.value}`)

const { data, pending, error, refresh } = await useAsyncData<LateralRecipeResponse | null>(
  () => cacheKey.value,
  () => {
    if (!recipeName.value) {
      return Promise.resolve(null)
    }

    return fetchLateralRecipe({
      toolType: props.toolType,
      fabName: props.fab,
      recipeName: recipeName.value
    })
  },
  {
    watch: [cacheKey],
    default: () => null,
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const rows = computed<LateralRecipeRow[]>(() => data.value?.rows ?? [])
const totalTools = computed(() => data.value?.total_tools_in_fab ?? 0)
const readyCount = computed(() => data.value?.ready_count ?? 0)
const notReadyCount = computed(() => data.value?.not_ready_count ?? 0)
const readyPercent = computed(() => {
  if (totalTools.value === 0) return 0
  return Math.round((readyCount.value / totalTools.value) * 100)
})

type ReadinessFilter = 'all' | 'ready' | 'not-ready'
const readinessFilter = ref<ReadinessFilter>('all')

const columnFilters = computed<ColumnFiltersState>(() => {
  if (readinessFilter.value === 'all') return []
  return [{ id: 'recipe_ready', value: readinessFilter.value === 'ready' }]
})

const filterOptions = computed<{ value: ReadinessFilter, label: string, count: number }[]>(() => [
  { value: 'all', label: '전체', count: totalTools.value },
  { value: 'ready', label: 'Recipe 보유', count: readyCount.value },
  { value: 'not-ready', label: '미보유', count: notReadyCount.value }
])

const headerStats = computed(() => [
  { label: 'Total tools', value: totalTools.value.toLocaleString(), tone: 'neutral' as const },
  { label: 'Recipe 보유', value: readyCount.value.toLocaleString(), tone: 'accent' as const },
  { label: '미보유', value: notReadyCount.value.toLocaleString(), tone: 'bad' as const }
])

const columns: TableColumn<LateralRecipeRow>[] = [
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 132 },
  { accessorKey: 'eqp_model_cd', header: 'model', size: 124 },
  { accessorKey: 'vendor_nm', header: 'vendor', size: 100 },
  { accessorKey: 'available', header: 'avail', size: 90 },
  { accessorKey: 'recipe_ready', header: 'recipe', size: 130, filterFn: 'equals' },
  { accessorKey: 'recipe_version', header: 'version', size: 96 }
]

const tableUi = recipeTableUi
</script>

<template>
  <div class="space-y-4">
    <div class="space-y-3">
      <UButton
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-arrow-left"
        label="목록으로"
        class="rounded-full font-semibold"
        :to="backRoute"
        @click.prevent="goBackToList"
      />

      <EbeamFeatureHeader
        :eyebrow="`${toolLabel} · ${fab} · 횡전개`"
        :stats="data ? headerStats : []"
        :subtitle="data ? `이 fab 안에서 해당 recipe를 보유한 장비를 확인합니다. 보유 ratio: ${readyPercent}%` : ''"
        :title="recipeName || 'Recipe 횡전개'"
      />
    </div>

    <div
      v-if="!recipeName"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="mx-auto h-6 w-6 text-rose-500"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        Recipe 이름이 없습니다.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        label="Recipe 검색으로 돌아가기"
        :to="backRoute"
      />
    </div>

    <div
      v-else-if="pending"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-zinc-500"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mx-auto h-5 w-5 animate-spin text-zinc-400"
      />
      <p class="mt-2">
        Recipe 횡전개 정보를 불러오는 중입니다.
      </p>
    </div>

    <div
      v-else-if="error"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="mx-auto h-6 w-6 text-rose-500"
      />
      <p class="mt-2 text-sm font-medium text-rose-600 dark:text-rose-300">
        Recipe 횡전개 정보를 불러오지 못했습니다.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-refresh-cw"
        label="Retry"
        @click="refresh()"
      />
    </div>

    <section
      v-else-if="data"
      class="dashboard-surface rounded-2xl px-3.5 py-3"
    >
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            장비 리스트
          </h2>
          <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            {{ rows.length.toLocaleString() }}
          </span>
        </div>

        <div
          role="radiogroup"
          aria-label="recipe readiness filter"
          class="inline-flex flex-wrap items-center gap-1.5"
        >
          <button
            v-for="option in filterOptions"
            :key="option.value"
            type="button"
            role="radio"
            :aria-checked="readinessFilter === option.value"
            class="inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-xs font-semibold ring-1 transition-colors"
            :class="chipClass(readinessFilter === option.value)"
            @click="readinessFilter = option.value"
          >
            {{ option.label }}
            <span class="font-mono text-[10px] tabular-nums opacity-70">
              {{ option.count.toLocaleString() }}
            </span>
          </button>
        </div>
      </div>

      <UTable
        class="font-mono-ids"
        :columns="columns"
        :data="rows"
        :column-filters="columnFilters"
        sticky="header"
        :ui="tableUi"
      >
        <template #eqp_id-cell="{ row }">
          <span class="font-mono text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
            {{ row.original.eqp_id }}
          </span>
        </template>

        <template #available-cell="{ row }">
          <span
            class="sk-lateral-badge"
            :class="row.original.available === 'On' ? 'sk-lateral-badge--ok' : 'sk-lateral-badge--bad'"
          >
            {{ row.original.available }}
          </span>
        </template>

        <template #recipe_ready-cell="{ row }">
          <span
            class="sk-lateral-badge"
            :class="row.original.recipe_ready ? 'sk-lateral-badge--ok' : 'sk-lateral-badge--bad'"
          >
            {{ row.original.recipe_ready ? '보유' : '미보유' }}
          </span>
        </template>

        <template #recipe_version-cell="{ row }">
          <span
            class="font-mono text-[12px] tabular-nums"
            :class="row.original.recipe_version === null ? 'text-zinc-400' : 'text-zinc-700 dark:text-zinc-200'"
          >
            {{ row.original.recipe_version === null ? '—' : `v${row.original.recipe_version}` }}
          </span>
        </template>
      </UTable>
    </section>
  </div>
</template>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}

.sk-lateral-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 9999px;
  border: 1px solid transparent;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.2;
}

.sk-lateral-badge--ok {
  background: var(--sk-ok-soft);
  border-color: var(--sk-ok-border);
  color: var(--sk-ok);
}

.sk-lateral-badge--bad {
  background: var(--sk-bad-soft);
  border-color: var(--sk-bad-border);
  color: var(--sk-bad);
}
</style>
