<template>
  <AfmCard
    icon="i-lucide-scatter-chart"
    title="포인트별 요약"
  >
    <template #actions>
      <div class="flex flex-wrap items-center gap-2">
        <USelect
          v-model="selectedStatistic"
          size="xs"
          :items="AFM_SUMMARY_ITEMS"
          class="min-w-28"
          aria-label="통계 항목"
        />
        <SkChip
          v-for="col in columns"
          :key="col"
          size="sm"
          :label="col"
          :active="selectedColumns.includes(col)"
          @click="toggleColumn(col)"
        />
      </div>
    </template>

    <p
      v-if="!summary.length"
      class="px-4 py-12 text-center sk-body"
    >
      통계 데이터가 없습니다.
    </p>
    <div
      v-else
      ref="chartEl"
      class="h-72 w-full"
    />
  </AfmCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmSummaryItem, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { AFM_SUMMARY_ITEMS } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  summary: AfmSummaryRow[]
  exportName?: string
}>()

const selectedStatistic = ref<AfmSummaryItem>('MEAN')

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
    symbolSize: 10,
    data: rows.value.map(row => summaryNumber(row[col]))
  }))
}))

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
