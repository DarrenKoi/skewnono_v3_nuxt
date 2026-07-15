<template>
  <UCard
    class="dashboard-surface rounded-2xl"
    :ui="{ body: 'p-4 sm:p-5', header: 'px-4 sm:px-5 py-3' }"
  >
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-scatter-chart"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            Summary by point
          </h2>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <USelect
            v-model="selectedStatistic"
            size="xs"
            :items="statisticItems"
            class="min-w-[7rem]"
          />
          <div class="flex flex-wrap gap-1">
            <button
              v-for="col in measurementColumns"
              :key="col"
              type="button"
              class="inline-flex h-6 items-center rounded-md px-2 text-[11px] font-medium ring-1 transition-colors"
              :class="chipClass(selectedMeasurements.includes(col))"
              @click="toggleMeasurement(col)"
            >
              {{ col }}
            </button>
          </div>
        </div>
      </div>
    </template>

    <div
      v-if="!summary?.length"
      class="px-4 py-12 text-center sk-body"
    >
      No statistical data available
    </div>
    <div
      v-else
      ref="chartEl"
      class="h-72 w-full"
    />
  </UCard>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { AfmSummaryItem, AfmSummaryRow } from '~/composables/useAfmDetailApi'
import { AFM_SUMMARY_ITEMS } from '~/composables/useAfmDetailApi'
import { chipClass } from '~/utils/chipClass'

const props = defineProps<{
  summary: AfmSummaryRow[]
}>()

const statisticItems = [...AFM_SUMMARY_ITEMS]
const selectedStatistic = ref<AfmSummaryItem>('MEAN')

const measurementColumns = computed(() => {
  if (!props.summary?.length) return []
  return Object.keys(props.summary[0]!).filter(k => k !== 'Site' && k !== 'ITEM')
})

const selectedMeasurements = ref<string[]>([])

watch(measurementColumns, (cols) => {
  if (cols.length && selectedMeasurements.value.length === 0) {
    selectedMeasurements.value = cols.slice(0, 3)
  }
}, { immediate: true })

const toggleMeasurement = (col: string) => {
  const next = new Set(selectedMeasurements.value)
  if (next.has(col)) next.delete(col)
  else next.add(col)
  selectedMeasurements.value = Array.from(next)
}

const sites = computed(() =>
  Array.from(new Set(props.summary.map(r => r.Site)))
)

const summaryIndex = computed(() => {
  const map = new Map<string, AfmSummaryRow>()
  for (const row of props.summary) map.set(`${row.Site}|${row.ITEM}`, row)
  return map
})

const chartEl = ref<HTMLDivElement | null>(null)

const chartOption = computed<EChartsOption>(() => ({
  grid: { left: 50, right: 24, top: 24, bottom: 36 },
  tooltip: { trigger: 'item' },
  legend: { top: 0, right: 8, textStyle: { fontSize: 11 } },
  xAxis: {
    type: 'category',
    data: sites.value,
    axisLabel: { fontSize: 10 }
  },
  yAxis: {
    type: 'value',
    scale: true,
    axisLabel: { fontSize: 10 }
  },
  series: selectedMeasurements.value.map(col => ({
    name: col,
    type: 'scatter',
    symbolSize: 10,
    data: sites.value.map((site) => {
      const value = summaryIndex.value.get(`${site}|${selectedStatistic.value}`)?.[col]
      return typeof value === 'number' ? value : null
    })
  }))
}))

useEchart(chartEl, chartOption)
</script>
