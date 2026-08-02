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
          <span
            v-if="noRuleCount > 0"
            class="inline-flex items-center gap-1.5 rounded-full bg-(--sk-muted-surface) px-2.5 py-1 font-mono text-[10.5px] font-semibold tracking-wide text-(--sk-ink-subtle) ring-1 ring-(--sk-border) ring-inset"
            title="계측 룰이 없는 fab 의 lot 입니다 — 판정하지 않았습니다"
          >
            <span class="h-[7px] w-[7px] rounded-full bg-(--sk-border)" />
            {{ noRuleCount }} 룰 없음
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
          <span
            v-if="row.original.verdict.health"
            class="inline-flex items-center gap-1.5"
          >
            <span
              class="h-2 w-2 rounded-full"
              :style="{ background: healthSwatches[row.original.verdict.health].dot }"
            />
            <span class="font-mono text-[11px] font-semibold text-(--sk-ink-muted)">{{ row.original.verdict.health }}</span>
          </span>
          <span
            v-else
            class="inline-flex items-center gap-1.5"
            :title="coverageTitle(row.original)"
          >
            <span class="h-2 w-2 rounded-full bg-(--sk-border)" />
            <span class="font-mono text-[11px] font-medium text-(--sk-ink-subtle)">룰 없음</span>
          </span>
        </template>

        <template #violations-cell="{ row }">
          <span
            v-if="row.original.verdict.kind === 'judged'"
            class="tabular-nums"
          >
            <span class="font-semibold text-(--sk-ink)">{{ row.original.verdict.violation_recipes }}</span>
            <span class="text-(--sk-ink-subtle)"> / {{ row.original.verdict.judged_recipes }}</span>
          </span>
          <span
            v-else
            class="text-(--sk-ink-subtle)"
          >—</span>
        </template>

        <template #coverage-cell="{ row }">
          <span
            class="tabular-nums"
            :title="coverageTitle(row.original)"
          >
            <template v-if="row.original.verdict.kind === 'judged'">
              <span class="font-semibold text-(--sk-ink)">{{ row.original.verdict.judged_recipes }}</span>
              <span class="text-(--sk-ink-subtle)"> / {{ row.original.verdict.total_recipes }}</span>
              <span class="ml-1 text-[11px] text-(--sk-ink-subtle)">({{ percent(row.original.verdict.coverage) }})</span>
            </template>
            <span
              v-else
              class="text-(--sk-ink-subtle)"
            >0 / {{ row.original.verdict.total_recipes }}</span>
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

        <template #point_median-cell="{ row }">
          <span
            v-if="row.original.has_profile"
            class="font-mono text-[12px] text-(--sk-ink-muted)"
          >{{ row.original.point_median }}</span>
          <span
            v-else
            class="text-(--sk-ink-subtle)"
            :title="text.noProfile"
          >—</span>
        </template>

        <template #outlier_count-cell="{ row }">
          <UButton
            v-if="row.original.outlier_count > 0"
            size="xs"
            color="neutral"
            variant="ghost"
            class="-my-1 h-6 gap-1 px-1.5"
            :aria-label="`${row.original.lot_cd} outlier ${row.original.outlier_count}건 자세히`"
            @click.stop="emit('open-outliers', row.original.lot_cd)"
          >
            <span class="inline-flex h-5 min-w-7 items-center justify-center rounded bg-rose-100 px-1.5 font-mono text-[11px] font-semibold tabular-nums text-rose-700 dark:bg-rose-950/50 dark:text-rose-300">
              {{ row.original.outlier_count }}
            </span>
            <UIcon
              name="i-lucide-chevron-right"
              class="h-3 w-3 text-(--sk-ink-subtle)"
            />
          </UButton>
          <span
            v-else-if="row.original.has_profile"
            class="inline-flex h-5 min-w-7 items-center justify-center rounded bg-(--sk-surface) px-1.5 font-mono text-[11px] font-semibold tabular-nums text-(--sk-ink-subtle)"
          >0</span>
          <span
            v-else
            class="text-(--sk-ink-subtle)"
            :title="text.noProfile"
          >—</span>
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
import { paraTotal, verdictSortValue, type HealthAugmentedRow } from '~/utils/lotHealth'
import type { HealthLevel } from '~/utils/ruleEngine'
import type { ProfiledLotRow } from '~/utils/comparisonRows'
import { healthSwatches } from './healthTokens'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{
  rows: ProfiledLotRow[]
}>()

const emit = defineEmits<{
  (e: 'select-lot', row: HealthAugmentedRow): void
  (e: 'open-outliers', lot_cd: string): void
}>()

const text = {
  title: 'Lot 요약',
  subtitle: '행을 클릭하면 recipe 상세와 추이를, outlier 를 클릭하면 과다 측정 파라미터를 확인합니다.',
  noProfile: '이 lot 의 recipe 파라미터를 불러오지 못했습니다',
  empty: '표시할 lot 이 없습니다. 다른 bucket 을 선택해 보세요.',
  copy: '클립보드 복사',
  copyAria: '표를 클립보드에 복사',
  download: 'CSV 다운로드'
} as const

const healthLevels: HealthLevel[] = ['red', 'yellow', 'green']

const counts = computed<Record<HealthLevel, number>>(() => ({
  red: props.rows.filter(r => r.verdict.health === 'red').length,
  yellow: props.rows.filter(r => r.verdict.health === 'yellow').length,
  green: props.rows.filter(r => r.verdict.health === 'green').length
}))

// 룰이 없어 판정하지 못한 lot. 초록과 섞이면 안 되므로 따로 셉니다.
const noRuleCount = computed(() => props.rows.filter(r => r.verdict.kind === 'no-rules').length)

const maxParaTotal = computed(() => Math.max(0, ...props.rows.map(paraTotal)))

const percent = (value: number) => `${Math.round(value * 100)}%`

/** gray 사유별 건수를 툴팁 한 줄로. 왜 판정 대상에서 빠졌는지 말해 줍니다. */
const coverageTitle = (r: HealthAugmentedRow) => {
  const v = r.verdict
  if (v.kind === 'no-rules') return `${r.fac_id} 에는 계측 룰이 없습니다 (D22)`
  const reasons = Object.entries(v.gray_reasons)
  if (reasons.length === 0) return `${v.judged_recipes}건 모두 판정했습니다`
  const detail = reasons.map(([reason, n]) => `${reason} ${n}건`).join(', ')
  return `판정 ${v.judged_recipes} / 전체 ${v.total_recipes} — 제외: ${detail}`
}

// 정렬은 lotHealth 가 정의합니다 — 판정 없음이 항상 맨 뒤로 갑니다.
const healthSortValue = (r: HealthAugmentedRow) => verdictSortValue(r.verdict)

const sorting = ref<SortingState>([{ id: 'health', desc: false }])

const columns: TableColumn<ProfiledLotRow>[] = [
  { accessorKey: 'lot_cd', header: 'lot', size: 120 },
  { id: 'stage', accessorFn: r => r.dev_stage, header: 'stage', size: 72 },
  { id: 'health', accessorFn: healthSortValue, header: 'health', size: 90 },
  { id: 'violations', accessorFn: r => r.verdict.violation_recipes, header: 'violations', size: 110 },
  { id: 'coverage', accessorFn: r => r.verdict.coverage, header: '판정 범위', size: 120 },
  { id: 'params', header: 'para 분포', size: 216, enableSorting: false },
  { id: 'para_total', accessorFn: paraTotal, header: 'para 합계', size: 90 },
  { accessorKey: 'avail_recipe', header: '운용 recipe', size: 100 },
  { accessorKey: 'total_recipe', header: '전체 recipe', size: 100 },
  // 측정 프로파일 — 과다 측정 디바이스 탐지. 요약 버킷이 아니라 recipe_params 에서
  // 옵니다(버킷을 바꿔도 기준선이 움직이면 안 되므로).
  { accessorKey: 'point_median', header: '중앙값', size: 90 },
  { accessorKey: 'outlier_count', header: 'outlier', size: 90 },
  { accessorKey: 'ctn_desc', header: 'description' }
]

const sortableColumnIds = [
  'lot_cd', 'stage', 'health', 'violations', 'coverage',
  'para_total', 'avail_recipe', 'total_recipe',
  'point_median', 'outlier_count', 'ctn_desc'
] as const

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

const tableUi = {
  tr: 'cursor-pointer select-none transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  // nowrap: 열이 늘어나 폭이 빠듯해지면 브라우저가 한글 헤더를 글자 단위로 세로
  // 배열해 버립니다("측/정/중/앙/값"). 줄바꿈을 막고 가로 스크롤로 넘깁니다.
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40 whitespace-nowrap'
}

// Mirror the active column sort so exports match what the user sees;
// UTable sorts internally and never mutates props.rows.
const exportSortValue: Record<string, (r: ProfiledLotRow) => string | number> = {
  lot_cd: r => r.lot_cd,
  stage: r => r.dev_stage,
  health: healthSortValue,
  violations: r => r.verdict.violation_recipes,
  coverage: r => r.verdict.coverage,
  para_total: paraTotal,
  avail_recipe: r => r.avail_recipe,
  total_recipe: r => r.total_recipe,
  point_median: r => r.point_median,
  outlier_count: r => r.outlier_count,
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
  // health 가 빈 칸이면 "판정 없음" 입니다 — 초록으로 읽히지 않도록 색 이름 대신
  // 빈 값을 내보내고, 몇 건을 실제로 판정했는지는 옆 두 열이 말합니다.
  const headers = [
    'lot_cd', 'fac_id', 'stage', 'health', 'violation_recipes',
    'judged_recipes', 'total_recipes', 'coverage',
    'para_16', 'para_13', 'para_9', 'para_5', 'para_total',
    'avail_recipe', 'total_recipe', 'point_median', 'outlier_count', 'ctn_desc'
  ]
  // 프로파일이 없는 lot 은 0 이 아니라 빈 칸으로 나갑니다 — 표의 "—" 와 같은 뜻이고,
  // 스프레드시트에서 "측정 0건" 으로 집계되면 안 됩니다.
  const rows = exportRows.value.map(r => [
    r.lot_cd, r.fac_id, r.dev_stage, r.verdict.health ?? '', r.verdict.violation_recipes,
    r.verdict.judged_recipes, r.verdict.total_recipes, r.verdict.coverage.toFixed(3),
    r.para_16, r.para_13, r.para_9, r.para_5, paraTotal(r),
    r.avail_recipe, r.total_recipe,
    r.has_profile ? r.point_median : '', r.has_profile ? r.outlier_count : '',
    r.ctn_desc
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
