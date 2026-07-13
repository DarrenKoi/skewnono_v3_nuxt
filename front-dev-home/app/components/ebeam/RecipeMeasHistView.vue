<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Fab } from '~/stores/navigation'
import type {
  MeasHistResponse,
  MeasHistRow,
  MeasHistToolType
} from '~/composables/useMeasHistApi'
import { formatRecipeTimestamp, readRecipeNameQuery, recipeTableUi } from '~/utils/recipeView'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: MeasHistToolType
}>()

const route = useRoute()
const { fetchMeasHist } = useMeasHistApi()

const recipeName = computed(() => readRecipeNameQuery(route))
const backRoute = computed(() => `/ebeam/${props.toolType}/${props.fab.toLowerCase()}/recipe-search`)
const { goBack: goBackToList } = useHistoryBack(backRoute)

const cacheKey = computed(() => `meas-hist:${props.toolType}:${props.fab || 'ALL'}:${recipeName.value}`)

const { data, pending, error, refresh } = await useAsyncData<MeasHistResponse | null>(
  () => cacheKey.value,
  () => {
    if (!recipeName.value) {
      return Promise.resolve(null)
    }

    return fetchMeasHist({
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

const rows = computed<MeasHistRow[]>(() => data.value?.rows ?? [])
const total = computed(() => data.value?.total ?? 0)

const aggregates = computed(() => {
  let msrMissing = 0
  let alignFail = 0
  let failRatioSum = 0

  for (const row of rows.value) {
    if (row.msr_check === 'No') msrMissing++
    if (row.align_fail === 'Fail') alignFail++
    failRatioSum += row.fail_ratio
  }

  const avgFailRatio = rows.value.length === 0 ? 0 : failRatioSum / rows.value.length
  return { msrMissing, alignFail, avgFailRatio }
})

const headerStats = computed(() => [
  { label: 'Total', value: total.value.toLocaleString(), tone: 'neutral' as const },
  {
    label: 'MSR 없음',
    value: aggregates.value.msrMissing.toLocaleString(),
    tone: aggregates.value.msrMissing > 0 ? 'bad' as const : 'neutral' as const
  },
  {
    label: 'Align Fail',
    value: aggregates.value.alignFail.toLocaleString(),
    tone: aggregates.value.alignFail > 0 ? 'bad' as const : 'neutral' as const
  },
  { label: 'Avg fail ratio', value: `${(aggregates.value.avgFailRatio * 100).toFixed(1)}%`, tone: 'neutral' as const }
])

const formatTimestamp = (iso: string) => formatRecipeTimestamp(iso)

const columns: TableColumn<MeasHistRow>[] = [
  { accessorKey: 'timestamp', header: 'timestamp', size: 138 },
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 110 },
  { accessorKey: 'lot_id', header: 'lot_id', size: 132 },
  { accessorKey: 'class_name', header: 'class', size: 80 },
  { accessorKey: 'recipe_name', header: 'recipe', size: 240 },
  { accessorKey: 'meastime', header: 'meas(s)', size: 86 },
  { accessorKey: 'msr_check', header: 'msr', size: 76 },
  { accessorKey: 'align_fail', header: 'align', size: 84 },
  { accessorKey: 'total_images', header: 'images', size: 82 },
  { accessorKey: 'fail_images', header: 'fail', size: 70 },
  { accessorKey: 'fail_ratio', header: 'ratio', size: 84 }
]

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
        label="목록으로"
        class="rounded-full font-semibold"
        :to="backRoute"
        @click.prevent="goBackToList"
      />

      <EbeamFeatureHeader
        :eyebrow="`${toolLabel} · ${fab} · 측정 이력`"
        :stats="data ? headerStats : []"
        subtitle="최근 60일 측정 row 기준입니다. msr_check / align_fail / fail_ratio로 측정 상태를 판단합니다."
        :title="recipeName || '측정 이력'"
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
        측정 이력을 불러오는 중입니다.
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
        측정 이력을 불러오지 못했습니다.
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

    <div
      v-else-if="total === 0"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-search-x"
        class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
      />
      <p class="mt-2 text-sm font-medium text-zinc-700 dark:text-zinc-200">
        측정 이력이 없습니다.
      </p>
    </div>

    <section
      v-else-if="data"
      class="dashboard-surface rounded-2xl px-3.5 py-3"
    >
      <div class="mb-3 flex items-center justify-between gap-3">
        <h2 class="text-[12.5px] font-semibold text-zinc-900 dark:text-zinc-100">
          측정 이력 (최신순)
        </h2>
        <span class="font-mono text-[11px] tabular-nums text-(--sk-ink-muted)">
          {{ rows.length.toLocaleString() }} rows
        </span>
      </div>

      <UTable
        class="font-mono-ids"
        :columns="columns"
        :data="rows"
        sticky="header"
        :ui="tableUi"
      >
        <template #timestamp-cell="{ row }">
          <span class="font-mono text-[11.5px] tabular-nums text-zinc-700 dark:text-zinc-200">
            {{ formatTimestamp(row.original.timestamp) }}
          </span>
        </template>

        <template #eqp_id-cell="{ row }">
          <span class="font-mono text-[12px] font-semibold text-zinc-900 dark:text-zinc-100">
            {{ row.original.eqp_id }}
          </span>
        </template>

        <template #lot_id-cell="{ row }">
          <span class="font-mono text-[11.5px] text-zinc-700 dark:text-zinc-200">
            {{ row.original.lot_id }}
          </span>
        </template>

        <template #recipe_name-cell="{ row }">
          <span class="font-mono text-[11.5px] text-zinc-700 dark:text-zinc-200">
            {{ row.original.recipe_name }}
          </span>
        </template>

        <template #meastime-cell="{ row }">
          <span class="font-mono text-[11.5px] tabular-nums text-zinc-700 dark:text-zinc-200">
            {{ row.original.meastime }}
          </span>
        </template>

        <template #msr_check-cell="{ row }">
          <UBadge
            :label="row.original.msr_check"
            :color="row.original.msr_check === 'Yes' ? 'success' : 'error'"
            size="xs"
            variant="subtle"
          />
        </template>

        <template #align_fail-cell="{ row }">
          <UBadge
            :label="row.original.align_fail"
            :color="row.original.align_fail === 'Pass' ? 'success' : row.original.align_fail === 'Fail' ? 'error' : 'neutral'"
            size="xs"
            variant="subtle"
          />
        </template>

        <template #total_images-cell="{ row }">
          <span class="font-mono text-[11.5px] tabular-nums text-zinc-700 dark:text-zinc-200">
            {{ row.original.total_images }}
          </span>
        </template>

        <template #fail_images-cell="{ row }">
          <span
            class="font-mono text-[11.5px] tabular-nums"
            :class="row.original.fail_images > 0 ? 'text-rose-600 dark:text-rose-300' : 'text-zinc-700 dark:text-zinc-200'"
          >
            {{ row.original.fail_images }}
          </span>
        </template>

        <template #fail_ratio-cell="{ row }">
          <span
            class="font-mono text-[11.5px] tabular-nums"
            :class="row.original.fail_ratio >= 0.15 ? 'text-rose-600 dark:text-rose-300' : 'text-zinc-700 dark:text-zinc-200'"
          >
            {{ (row.original.fail_ratio * 100).toFixed(1) }}%
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
</style>
