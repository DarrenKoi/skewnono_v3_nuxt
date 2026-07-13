<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Fab } from '~/stores/navigation'
import type {
  LateralRecipeResponse,
  LateralRecipeRow,
  LateralRecipeToolType
} from '~/composables/useLateralRecipeApi'
import { formatRecipeTimestamp, readRecipeNameQuery, recipeTableUi } from '~/utils/recipeView'

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
const readyRows = computed<LateralRecipeRow[]>(() => rows.value.filter(row => row.recipe_ready))
const notReadyRows = computed<LateralRecipeRow[]>(() => rows.value.filter(row => !row.recipe_ready))
const totalTools = computed(() => data.value?.total_tools_in_fab ?? 0)
const readyCount = computed(() => data.value?.ready_count ?? 0)
const notReadyCount = computed(() => data.value?.not_ready_count ?? 0)
const readyPercent = computed(() => {
  if (totalTools.value === 0) return 0
  return Math.round((readyCount.value / totalTools.value) * 100)
})

type LateralTab = 'ready' | 'not-ready'
const activeTab = ref<LateralTab>('ready')

const tabOptions = computed<{ value: LateralTab, label: string, count: number }[]>(() => [
  { value: 'ready', label: '보유', count: readyCount.value },
  { value: 'not-ready', label: '미보유', count: notReadyCount.value }
])

const headerStats = computed(() => [
  { label: 'Total tools', value: totalTools.value.toLocaleString(), tone: 'neutral' as const },
  { label: 'Recipe 보유', value: readyCount.value.toLocaleString(), tone: 'accent' as const },
  { label: '미보유', value: notReadyCount.value.toLocaleString(), tone: 'bad' as const }
])

const activeRows = computed<LateralRecipeRow[]>(() =>
  activeTab.value === 'ready' ? readyRows.value : notReadyRows.value
)

const versionStatus = computed(() => {
  const totalVersions = data.value?.versions.length ?? 0
  if (totalVersions === 0) return '보유 장비 없음'
  if (totalVersions === 1) return '동일 version'
  return `${totalVersions}개 version 혼재`
})

const formatGeneratedAt = (iso: string | null | undefined) =>
  iso ? formatRecipeTimestamp(iso, { withSeconds: true }) : '—'

const baseColumns: TableColumn<LateralRecipeRow>[] = [
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 132 },
  { accessorKey: 'eqp_model_cd', header: 'model', size: 124 },
  { accessorKey: 'vendor_nm', header: 'vendor', size: 100 },
  { accessorKey: 'available', header: 'avail', size: 90 }
]

const readyColumns: TableColumn<LateralRecipeRow>[] = [
  ...baseColumns,
  { accessorKey: 'recipe_version', header: 'version', size: 96 },
  { accessorKey: 'recipe_generated_at', header: 'generated_at', size: 172 }
]

const activeColumns = computed<TableColumn<LateralRecipeRow>[]>(() =>
  activeTab.value === 'ready' ? readyColumns : baseColumns
)

const tableUi = recipeTableUi
</script>

<template>
  <div class="space-y-4">
    <EbeamRecipeSwitcher
      :tool-type="toolType"
      :fab="fab"
    />
    <div class="space-y-3">
      <UButton
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-arrow-left"
        label="돌아가기"
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
      class="dashboard-surface rounded-2xl px-6 py-12 text-center text-sm text-(--sk-ink-muted)"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="mx-auto h-5 w-5 animate-spin text-(--sk-ink-muted)"
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

    <template v-else-if="data">
      <section class="dashboard-surface rounded-2xl px-4 py-3">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="text-[13px] font-semibold text-zinc-900 dark:text-zinc-100">
                Recipe version
              </h2>
              <span
                class="inline-flex h-6 items-center rounded-md px-2 text-[11px] font-semibold ring-1"
                :class="data.versions.length <= 1
                  ? 'bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:ring-emerald-900'
                  : 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-200 dark:ring-amber-900'"
              >
                {{ versionStatus }}
              </span>
            </div>
            <p class="mt-1 text-xs leading-5 text-(--sk-ink-muted)">
              version별 생성 시간과 보유 장비 수를 먼저 확인한 뒤 장비 리스트를 나눠 봅니다.
            </p>
          </div>
          <div class="text-left lg:text-right">
            <p class="font-mono text-[11px] text-(--sk-ink-muted)">
              latest
            </p>
            <p class="mt-0.5 font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              {{ data.latest_recipe_version === null ? '—' : `v${data.latest_recipe_version}` }}
            </p>
            <p class="mt-0.5 font-mono text-[11px] text-(--sk-ink-muted)">
              {{ formatGeneratedAt(data.latest_generated_at) }}
            </p>
          </div>
        </div>

        <div
          v-if="data.versions.length > 0"
          class="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4"
        >
          <div
            v-for="version in data.versions"
            :key="version.recipe_version"
            class="rounded-lg border border-(--sk-border) bg-white px-3 py-2 dark:bg-zinc-950"
          >
            <div class="flex items-center justify-between gap-3">
              <span class="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                v{{ version.recipe_version }}
              </span>
              <span class="font-mono text-[11px] tabular-nums text-(--sk-ink-muted)">
                {{ version.ready_count.toLocaleString() }} tools
              </span>
            </div>
            <p class="mt-1 font-mono text-[11px] text-(--sk-ink-muted)">
              {{ formatGeneratedAt(version.generated_at) }}
            </p>
          </div>
        </div>

        <div
          v-else
          class="mt-3 rounded-lg border border-dashed border-(--sk-border) px-3 py-5 text-center text-xs text-(--sk-ink-muted)"
        >
          이 fab에서 해당 recipe를 보유한 장비가 없습니다.
        </div>
      </section>

      <section class="dashboard-surface rounded-2xl px-3.5 py-3">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
              {{ activeTab === 'ready' ? '보유 장비 리스트' : '미보유 장비 리스트' }}
            </h2>
            <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              {{ activeRows.length.toLocaleString() }}
            </span>
          </div>

          <div
            role="tablist"
            aria-label="recipe readiness tabs"
            class="inline-flex rounded-lg border border-(--sk-border) bg-zinc-50 p-0.5 dark:bg-zinc-900"
          >
            <button
              v-for="option in tabOptions"
              :key="option.value"
              type="button"
              role="tab"
              :aria-selected="activeTab === option.value"
              class="inline-flex h-8 min-w-24 items-center justify-center gap-1.5 rounded-md px-3 text-xs font-semibold transition-colors"
              :class="activeTab === option.value
                ? 'bg-white text-zinc-950 shadow-sm dark:bg-zinc-800 dark:text-white'
                : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
              @click="activeTab = option.value"
            >
              {{ option.label }}
              <span class="font-mono text-[10px] tabular-nums opacity-70">
                {{ option.count.toLocaleString() }}
              </span>
            </button>
          </div>
        </div>

        <UTable
          v-if="activeRows.length > 0"
          class="font-mono-ids"
          :columns="activeColumns"
          :data="activeRows"
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

          <template #recipe_version-cell="{ row }">
            <span class="font-mono text-[12px] tabular-nums text-zinc-700 dark:text-zinc-200">
              {{ row.original.recipe_version === null ? '—' : `v${row.original.recipe_version}` }}
            </span>
          </template>

          <template #recipe_generated_at-cell="{ row }">
            <span class="font-mono text-[11px] tabular-nums text-(--sk-ink)">
              {{ formatGeneratedAt(row.original.recipe_generated_at) }}
            </span>
          </template>
        </UTable>

        <div
          v-else
          class="rounded-lg border border-dashed border-(--sk-border) px-4 py-10 text-center text-sm text-(--sk-ink-muted)"
        >
          표시할 장비가 없습니다.
        </div>
      </section>
    </template>
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
