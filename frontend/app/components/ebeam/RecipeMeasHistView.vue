<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingFn, SortingState } from '@tanstack/vue-table'
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
const routeFabSegment = useRouteFabSegment(() => props.fab)

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
    getCachedData: payloadCache
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
  { label: 'Avg fail ratio', value: `${aggregates.value.avgFailRatio.toFixed(1)}%`, tone: 'neutral' as const }
])

const formatTimestamp = (iso: string) => formatRecipeTimestamp(iso)

// fail_ratio is a PERCENTAGE (0..100) — it arrives already computed in the
// office OpenSearch documents, so nothing here multiplies by 100. The
// threshold is on the same scale: 15 means 15%, matching the fail-issue
// contract's MEAS_FAIL_THRESHOLD.
const MEAS_FAIL_THRESHOLD = 15

// Column order encodes priority: identity → 측정 상태(signal) → 참고용 context.
// The signal block (msr/align/images/fail/ratio) is what you actually scan for,
// so it sits left of lot_id/meas(s), which are only needed once a row already
// looks suspicious. Dividers mark the three blocks.
//
// class sits immediately left of recipe because the two are one name split in
// half — full_name is literally `class/recipe` (ADI/ADI_CD_BIAS_001). Parking
// class over in the context block made the reader reassemble it across the
// whole table width.
const BLOCK_START = 'border-l border-(--sk-border)'
const CONTEXT_COL = 'text-(--sk-ink-muted)'

// Fail is the reason anyone sorts this column, so rank by severity rather than
// alphabetically — 'Fail' < 'NA' < 'Pass' as strings would bury it in the middle.
const ALIGN_SEVERITY: Record<string, number> = { Fail: 2, NA: 1, Pass: 0 }
const sortAlignBySeverity: SortingFn<MeasHistRow> = (rowA, rowB) =>
  (ALIGN_SEVERITY[rowA.original.align_fail] ?? -1) - (ALIGN_SEVERITY[rowB.original.align_fail] ?? -1)

// Sortable columns are the measurement outcome ones: you sort them to find the
// worst rows, never the best, so the first click goes descending
// (`sortDescFirst`). A third click drops the sort and restores 최신순.
const SORTABLE_IDS = ['align_fail', 'total_images', 'fail_images', 'fail_ratio', 'meastime'] as const

const columns: TableColumn<MeasHistRow>[] = [
  { accessorKey: 'timestamp', header: 'timestamp', size: 138 },
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 112 },
  { accessorKey: 'class_name', header: 'class', size: 74 },
  { accessorKey: 'recipe_name', header: 'recipe', size: 240 },
  { accessorKey: 'msr_check', header: 'msr', size: 82, meta: { class: { td: BLOCK_START, th: BLOCK_START } } },
  { accessorKey: 'align_fail', header: 'align', size: 96, sortDescFirst: true, sortingFn: sortAlignBySeverity },
  { accessorKey: 'total_images', header: 'images', size: 96, sortDescFirst: true },
  { accessorKey: 'fail_images', header: 'fail', size: 88, sortDescFirst: true },
  { accessorKey: 'fail_ratio', header: 'ratio', size: 100, sortDescFirst: true },
  {
    accessorKey: 'lot_id',
    header: 'lot_id',
    size: 128,
    meta: { class: { td: `${BLOCK_START} ${CONTEXT_COL}`, th: BLOCK_START } }
  },
  { accessorKey: 'meastime', header: 'meas(s)', size: 96, sortDescFirst: true, meta: { class: { td: CONTEXT_COL } } }
]

// Empty by default so rows keep the API's 최신순 order until the user sorts.
const sorting = ref<SortingState>([])

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

// The section title used to read "(최신순)" unconditionally, which stops being
// true the moment a column is sorted. Header text is read back off the column
// defs so the title can never drift from what the header button says.
const sortLabel = computed(() => {
  const active = sorting.value[0]
  if (!active) return '최신순'

  const column = columns.find(candidate => 'accessorKey' in candidate && candidate.accessorKey === active.id)
  const header = typeof column?.header === 'string' ? column.header : active.id
  return `${header} ${active.desc ? '내림차순' : '오름차순'}`
})

// Local override rather than editing `recipeTableUi` — that preset is shared with
// 횡전개 and AlignPopup, which shouldn't inherit this view's larger body text.
const tableUi = {
  ...recipeTableUi,
  td: 'py-2 px-3 text-[13px] whitespace-nowrap overflow-hidden text-ellipsis text-(--sk-ink)',
  th: 'py-2 px-3 sk-label bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>

<template>
  <div class="space-y-4">
    <EbeamRecipeSwitcher
      :tool-type="toolType"
      :fab-segment="routeFabSegment"
      :owner-fab="fab"
      active-screen="meas-hist"
    />
    <div class="space-y-3">
      <EbeamRecipeDetailNav
        :tool-type="toolType"
        :fab-segment="routeFabSegment"
        :owner-fab="fab"
        :recipe-name="recipeName"
        active-screen="meas-hist"
      />

      <EbeamFeatureHeader
        :stats="data ? headerStats : []"
        subtitle="최근 30일 측정 row 기준입니다. msr_check / align_fail / fail_ratio로 측정 상태를 판단합니다."
        title="측정 이력"
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
      <p class="mt-2 sk-body">
        Recipe 이름이 없습니다.
      </p>
      <UButton
        class="mt-3"
        size="sm"
        color="neutral"
        variant="outline"
        label="Recipe 검색으로 돌아가기"
        :to="`/ebeam/${toolType}/${routeFabSegment}/recipe-search`"
      />
    </div>

    <AppLoadingState
      v-else-if="pending"
      title="측정 이력을 불러오는 중입니다."
    />

    <div
      v-else-if="error"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="mx-auto h-6 w-6 text-rose-500"
      />
      <p class="mt-2 sk-body text-rose-600 dark:text-rose-300">
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
      <p class="mt-2 sk-body">
        측정 이력이 없습니다.
      </p>
    </div>

    <section
      v-else-if="data"
      class="dashboard-surface rounded-2xl px-3.5 py-3"
    >
      <div class="mb-3 flex items-center justify-between gap-3">
        <h2 class="sk-title">
          측정 이력 ({{ sortLabel }})
        </h2>
        <span class="sk-meta">
          {{ rows.length.toLocaleString() }} rows
        </span>
      </div>

      <UTable
        v-model:sorting="sorting"
        class="font-mono-ids"
        :columns="columns"
        :data="rows"
        :sorting-options="{ enableMultiSort: false }"
        sticky="header"
        :ui="tableUi"
      >
        <template
          v-for="id in SORTABLE_IDS"
          :key="id"
          #[`${id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 sk-label hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting()"
          >
            {{ column.columnDef.header }}
          </UButton>
        </template>

        <template #timestamp-cell="{ row }">
          <span class="font-mono text-[13px] tabular-nums text-zinc-700 dark:text-zinc-300">
            {{ formatTimestamp(row.original.timestamp) }}
          </span>
        </template>

        <template #eqp_id-cell="{ row }">
          <span class="font-mono text-[13px] font-semibold text-zinc-900 dark:text-zinc-50">
            {{ row.original.eqp_id }}
          </span>
        </template>

        <template #class_name-cell="{ row }">
          <span class="font-mono text-[13px] text-(--sk-ink-muted)">
            {{ row.original.class_name }}
          </span>
        </template>

        <template #recipe_name-cell="{ row }">
          <span class="font-mono text-[13px] text-zinc-800 dark:text-zinc-100">
            {{ row.original.recipe_name }}
          </span>
        </template>

        <template #msr_check-cell="{ row }">
          <UBadge
            :label="row.original.msr_check"
            :color="row.original.msr_check === 'Yes' ? 'success' : 'error'"
            size="sm"
            variant="subtle"
          />
        </template>

        <template #align_fail-cell="{ row }">
          <UBadge
            :label="row.original.align_fail"
            :color="row.original.align_fail === 'Pass' ? 'success' : row.original.align_fail === 'Fail' ? 'error' : 'neutral'"
            size="sm"
            variant="subtle"
          />
        </template>

        <template #total_images-cell="{ row }">
          <span class="font-mono text-[13px] font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
            {{ row.original.total_images }}
          </span>
        </template>

        <template #fail_images-cell="{ row }">
          <span
            class="font-mono text-[13px] font-semibold tabular-nums"
            :class="row.original.fail_images > 0 ? 'text-rose-600 dark:text-rose-300' : 'text-zinc-900 dark:text-zinc-50'"
          >
            {{ row.original.fail_images }}
          </span>
        </template>

        <template #fail_ratio-cell="{ row }">
          <span
            class="font-mono text-[13px] font-semibold tabular-nums"
            :class="row.original.fail_ratio >= MEAS_FAIL_THRESHOLD ? 'text-rose-600 dark:text-rose-300' : 'text-zinc-900 dark:text-zinc-50'"
          >
            {{ row.original.fail_ratio.toFixed(1) }}%
          </span>
        </template>

        <template #lot_id-cell="{ row }">
          <span class="font-mono text-xs text-(--sk-ink-muted)">
            {{ row.original.lot_id }}
          </span>
        </template>

        <template #meastime-cell="{ row }">
          <span class="font-mono text-xs tabular-nums text-(--sk-ink-muted)">
            {{ row.original.meastime }}
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
