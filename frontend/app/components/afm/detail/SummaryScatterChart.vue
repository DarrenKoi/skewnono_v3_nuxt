<template>
  <AfmCard
    icon="i-lucide-scatter-chart"
    title="사이트별 요약"
    :count="rows.length || undefined"
  >
    <template
      v-if="summary.length"
      #actions
    >
      <SkSegmentedToggle
        v-model="selectedStatistic"
        :items="STATISTIC_ITEMS"
        label="통계 항목"
      />
    </template>

    <p
      v-if="!summary.length"
      class="flex h-full min-h-60 items-center justify-center sk-body"
    >
      통계 데이터가 없습니다.
    </p>
    <div
      v-else
      class="flex h-full flex-col gap-3"
    >
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="mr-1 sk-meta">측정 항목</span>
        <SkChip
          v-for="col in columns"
          :key="col"
          size="sm"
          :label="col"
          :active="selectedColumns.includes(col)"
          @click="toggleColumn(col)"
        />
      </div>
      <div
        ref="chartEl"
        class="min-h-64 w-full flex-1"
      />
      <div class="overflow-x-auto rounded-(--sk-r-chip) border border-(--sk-border)">
        <table class="w-full">
          <thead>
            <tr class="border-b border-(--sk-border) bg-(--sk-muted-surface)">
              <th class="px-3 py-1.5 text-left text-xs font-semibold whitespace-nowrap text-(--sk-ink-muted)">
                Site · {{ selectedStatistic }}
              </th>
              <th
                v-for="col in columns"
                :key="col"
                class="px-3 py-1.5 text-right text-xs font-semibold whitespace-nowrap"
                :class="selectedColumns.includes(col) ? 'text-(--sk-ink)' : 'text-(--sk-ink-muted)'"
              >
                {{ col }}
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-(--sk-border-soft)">
            <tr
              v-for="row in rows"
              :key="row.Site"
            >
              <td class="px-3 py-1.5 text-left font-mono text-[13px] font-medium text-(--sk-ink)">
                {{ row.Site }}
              </td>
              <td
                v-for="col in columns"
                :key="col"
                class="px-3 py-1.5 text-right font-mono text-[13px] tabular-nums text-(--sk-ink)"
              >
                {{ summaryNumber(row[col])?.toFixed(2) ?? '–' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
// Per-site summary of the file: one statistic at a time (the toggle), chart for
// the picked measurement columns, and the same statistic as a table for every
// column so the exact numbers sit under the dots.
import type { EChartsOption } from 'echarts'
import type { AfmSummaryItem, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { AFM_SUMMARY_ITEMS } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  summary: AfmSummaryRow[]
  exportName?: string
}>()

const STATISTIC_ITEMS = AFM_SUMMARY_ITEMS.map(item => ({ label: item, value: item }))

// A string, not AfmSummaryItem: SkSegmentedToggle emits plain strings.
const selectedStatistic = ref<string>('MEAN' satisfies AfmSummaryItem)

const columns = computed(() => summaryColumns(props.summary))
const selectedColumns = ref<string[]>([])

watch(columns, (cols) => {
  if (cols.length && selectedColumns.value.length === 0) {
    selectedColumns.value = cols.slice(0, 3)
  }
}, { immediate: true })

const toggleColumn = (col: string) => {
  selectedColumns.value = selectedColumns.value.includes(col)
    ? selectedColumns.value.filter(c => c !== col)
    : [...selectedColumns.value, col]
}

// One row per site for the picked statistic, in payload order.
const rows = computed(() => props.summary.filter(row => row.ITEM === selectedStatistic.value))

const chartEl = ref<HTMLDivElement | null>(null)

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 56, right: 24, top: 32, bottom: 36 },
  tooltip: { trigger: 'item' },
  legend: { top: 0, right: 8, textStyle: CHART_LEGEND_LABEL },
  xAxis: {
    type: 'category',
    data: rows.value.map(row => row.Site),
    axisLabel: CHART_AXIS_LABEL
  },
  yAxis: {
    type: 'value',
    scale: true,
    axisLabel: CHART_AXIS_LABEL
  },
  series: selectedColumns.value.map(col => ({
    name: col,
    type: 'scatter',
    symbolSize: 12,
    data: rows.value.map(row => summaryNumber(row[col]))
  }))
}))

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
