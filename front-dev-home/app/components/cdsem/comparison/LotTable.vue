<template>
  <section class="space-y-3">
    <header class="flex flex-wrap items-end justify-between gap-3 px-1">
      <div class="flex items-start gap-3">
        <span
          class="mt-0.5 h-10 w-1 flex-none rounded-[2px] bg-(--sk-accent)"
          aria-hidden="true"
        />
        <div>
          <h2 class="text-lg font-bold leading-tight tracking-tight text-(--sk-ink)">
            {{ text.title }}
          </h2>
          <p class="mt-1 sk-meta">
            {{ text.subtitle }}
          </p>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <div class="flex items-center gap-1.5">
          <span
            v-for="level in healthLevels"
            :key="level"
            class="inline-flex items-center gap-1.5 rounded-full bg-(--sk-muted-surface) px-2.5 py-1 font-mono text-[10.5px] font-semibold tracking-wide text-(--sk-ink-muted) ring-1 ring-(--sk-border) ring-inset"
          >
            <span
              class="h-[7px] w-[7px] rounded-full"
              :style="{ background: healthSwatches[level].dot }"
            />
            {{ counts[level] }} {{ level }}
          </span>
        </div>
        <UTooltip :text="text.copy">
          <UButton
            size="xs"
            color="neutral"
            variant="outline"
            icon="i-lucide-clipboard"
            :aria-label="text.copyAria"
            :disabled="rows.length === 0"
            @click="copyLotTable"
          />
        </UTooltip>
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-download"
          :label="text.download"
          :disabled="rows.length === 0"
          @click="downloadLotCsv"
        />
      </div>
    </header>

    <div class="dashboard-surface overflow-hidden rounded-2xl">
      <UTable
        v-model:sorting="sorting"
        class="max-h-136"
        :columns="columns"
        :data="rows"
        :empty="text.empty"
        :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
        sticky="header"
        :ui="tableUi"
        @select="(_, row) => emit('select-lot', row.original)"
      >
        <template
          v-for="id in sortableColumnIds"
          :key="id"
          #[`${id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click.stop="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ column.columnDef.header }}
          </UButton>
        </template>

        <template #lot_cd-cell="{ row }">
          <span class="font-mono font-semibold text-(--sk-ink)">{{ row.original.lot_cd }}</span>
        </template>

        <template #stage-cell="{ row }">
          <CdsemComparisonStageChip
            :stage="row.original.dev_stage"
            :inferred="row.original.stage_inferred"
          />
        </template>

        <template #health-cell="{ row }">
          <span class="inline-flex items-center gap-1.5">
            <span
              class="h-2 w-2 rounded-full"
              :style="{ background: healthSwatches[row.original.health].dot }"
            />
            <span class="font-mono text-[11px] font-semibold text-(--sk-ink-muted)">{{ row.original.health }}</span>
          </span>
        </template>

        <template #violations-cell="{ row }">
          <span class="tabular-nums">
            <span class="font-semibold text-(--sk-ink)">{{ row.original.violations }}</span>
            <span class="text-(--sk-ink-subtle)"> / 4</span>
          </span>
        </template>

        <template #params-cell="{ row }">
          <div class="w-[200px]">
            <CdsemComparisonStackedBar
              :row="row.original"
              :height="14"
              :normalize="false"
              :max-total="maxParaTotal"
            />
          </div>
        </template>

        <template #ctn_desc-cell="{ row }">
          <span
            class="block max-w-md truncate text-(--sk-ink-muted)"
            :title="row.original.ctn_desc"
          >
            {{ row.original.ctn_desc || '—' }}
          </span>
        </template>
      </UTable>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { HealthAugmentedRow } from '~/composables/useLotHealthMock'
import { healthOrder, healthSwatches, type HealthLevel } from './healthTokens'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{
  rows: HealthAugmentedRow[]
}>()

const emit = defineEmits<{ (e: 'select-lot', row: HealthAugmentedRow): void }>()

const text = {
  title: 'Lot 요약',
  subtitle: '행을 클릭하면 recipe 상세와 추이를 확인합니다.',
  empty: '표시할 lot 이 없습니다. 다른 bucket 을 선택해 보세요.',
  copy: '클립보드 복사',
  copyAria: '표를 클립보드에 복사',
  download: 'CSV 다운로드'
} as const

const healthLevels: HealthLevel[] = ['red', 'yellow', 'green']

const counts = computed<Record<HealthLevel, number>>(() => ({
  red: props.rows.filter(r => r.health === 'red').length,
  yellow: props.rows.filter(r => r.health === 'yellow').length,
  green: props.rows.filter(r => r.health === 'green').length
}))

const maxParaTotal = computed(() => Math.max(0, ...props.rows.map(r => r.para_total)))

// Two-level sort in one number: severity band (red 0 / yellow 1 / green 2),
// then higher violation ratio first within a band.
const healthSortValue = (r: HealthAugmentedRow) => healthOrder[r.health] - r.violation_ratio / 10

const sorting = ref<SortingState>([{ id: 'health', desc: false }])

const columns: TableColumn<HealthAugmentedRow>[] = [
  { accessorKey: 'lot_cd', header: 'lot', size: 120 },
  { id: 'stage', accessorFn: r => r.dev_stage, header: 'stage', size: 72 },
  { id: 'health', accessorFn: healthSortValue, header: 'health', size: 90 },
  { accessorKey: 'violations', header: 'violations', size: 90 },
  { id: 'params', header: 'para 분포', size: 216, enableSorting: false },
  { accessorKey: 'para_total', header: 'para 합계', size: 90 },
  { accessorKey: 'avail_recipe', header: '운용 recipe', size: 100 },
  { accessorKey: 'total_recipe', header: '전체 recipe', size: 100 },
  { accessorKey: 'ctn_desc', header: 'description' }
]

const sortableColumnIds = [
  'lot_cd', 'stage', 'health', 'violations',
  'para_total', 'avail_recipe', 'total_recipe', 'ctn_desc'
] as const

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

const tableUi = {
  tr: 'cursor-pointer select-none transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}

// Mirror the active column sort so exports match what the user sees;
// UTable sorts internally and never mutates props.rows.
const exportSortValue: Record<string, (r: HealthAugmentedRow) => string | number> = {
  lot_cd: r => r.lot_cd,
  stage: r => r.dev_stage,
  health: healthSortValue,
  violations: r => r.violations,
  para_total: r => r.para_total,
  avail_recipe: r => r.avail_recipe,
  total_recipe: r => r.total_recipe,
  ctn_desc: r => r.ctn_desc
}

const exportRows = computed(() => {
  const active = sorting.value[0]
  const get = active ? exportSortValue[active.id] : undefined
  if (!get) return [...props.rows]
  const direction = active?.desc ? -1 : 1
  return [...props.rows].sort((a, b) => {
    const av = get(a)
    const bv = get(b)
    const diff = typeof av === 'number' && typeof bv === 'number'
      ? av - bv
      : String(av).localeCompare(String(bv), undefined, { numeric: true })
    return diff * direction || a.lot_cd.localeCompare(b.lot_cd)
  })
})

const lotTable = () => {
  const headers = [
    'lot_cd', 'fac_id', 'stage', 'health', 'violations',
    'para_16', 'para_13', 'para_9', 'para_5', 'para_total',
    'avail_recipe', 'total_recipe', 'ctn_desc'
  ]
  const rows = exportRows.value.map(r => [
    r.lot_cd, r.fac_id, r.dev_stage, r.health, r.violations,
    r.para_16, r.para_13, r.para_9, r.para_5, r.para_total,
    r.avail_recipe, r.total_recipe, r.ctn_desc
  ])
  return { headers, rows }
}

const toast = useToast()

const exportFileName = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return `cdsem-comparison-lots-${today}.csv`
})

const downloadLotCsv = () => {
  const { headers, rows } = lotTable()
  downloadCsv(exportFileName.value, headers, rows)
}

const copyLotTable = async () => {
  const { headers, rows } = lotTable()
  const ok = await copyTableToClipboard(headers, rows)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
</script>
