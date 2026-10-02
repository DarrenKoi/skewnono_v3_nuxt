<template>
  <div>
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-scatter-chart"
          class="size-4 text-(--sk-ink-muted)"
        />
        <h2 class="sk-title">
          블록별 요약
        </h2>
      </div>
      <USelect
        v-model="selectedStatistic"
        size="xs"
        :items="AFM_SUMMARY_ITEMS"
        class="min-w-28"
        aria-label="통계 항목"
      />
    </div>

    <p
      v-if="!summary.length"
      class="flex h-44 items-center justify-center sk-body"
    >
      통계 데이터가 없습니다.
    </p>
    <template v-else>
      <div class="mt-2.5 flex flex-wrap items-center gap-1">
        <SkChip
          v-for="col in columns"
          :key="col"
          size="sm"
          :label="col"
          :active="selectedColumns.includes(col)"
          @click="toggleColumn(col)"
        />
      </div>
      <p class="mt-2 flex flex-wrap gap-x-3 sk-meta">
        <span>● 블록 {{ selectedStatistic }}</span>
        <span>{{ showsPoint ? `◇ 포인트 ${point}` : '포인트 값은 MEAN·MIN·MAX에서만 겹쳐 보입니다' }}</span>
      </p>
      <div
        ref="chartEl"
        class="h-44 w-full"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmSummaryItem, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { AFM_SUMMARY_ITEMS } from '~/composables/useAfmDetailApi'
import type { PointBlock } from '~/utils/afmPoints'

const props = defineProps<{
  summary: AfmSummaryRow[]
  // The selected point and its row in each block, drawn over the block statistic.
  point: string
  blocks: PointBlock[]
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

// One row per block for the picked statistic, in payload order.
const rows = computed(() => props.summary.filter(row => row.ITEM === selectedStatistic.value))

// A single point has a value to set against a block's MEAN, MIN or MAX; it has
// no STDEV or RANGE of its own.
const showsPoint = computed(() => ['MEAN', 'MIN', 'MAX'].includes(selectedStatistic.value) && props.blocks.length > 0)

const chartEl = ref<HTMLDivElement | null>(null)

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 56, right: 16, top: 32, bottom: 32 },
  tooltip: {
    trigger: 'item',
    formatter: (params: unknown) => {
      const p = params as { seriesName: string, name: string, value: [string, number] }
      return `${p.seriesName}<br/>${p.name} · ${p.value[0]}: ${p.value[1].toFixed(2)}`
    }
  },
  legend: { top: 0, right: 0, textStyle: CHART_LEGEND_LABEL },
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
  // The point's marks ride in the column's own series, so they take its colour
  // and its legend entry without a second palette to keep in step.
  series: selectedColumns.value.map(col => ({
    name: col,
    type: 'scatter',
    symbolSize: 10,
    data: [
      ...rows.value.flatMap((row) => {
        const value = summaryNumber(row[col])
        return value === null ? [] : [{ name: `블록 ${selectedStatistic.value}`, value: [row.Site, value] }]
      }),
      ...(showsPoint.value ? props.blocks : []).flatMap((block) => {
        const value = summaryNumber(block.row[col])
        // A block with no Summary has no category on the axis to sit on.
        return value === null || !rows.value.some(row => row.Site === block.name)
          ? []
          : [{ name: `포인트 ${props.point}`, value: [block.name, value], symbol: 'emptyDiamond', symbolSize: 14 }]
      })
    ]
  }))
}))

useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
