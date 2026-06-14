<template>
  <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-5 md:p-6">
      <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div class="min-w-0">
          <p class="text-xs uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
            AFM - See Together
          </p>
          <h1 class="text-xl md:text-2xl font-semibold tracking-tight">
            Time series comparison
          </h1>
          <p class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
            {{ toolName }} - {{ groupedItems.length }} selected measurements
          </p>
        </div>
        <UButton
          :to="`/afm/${toolId}`"
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-arrow-left"
        >
          Back to search
        </UButton>
      </div>
    </section>

    <section
      v-if="groupedItems.length === 0"
      class="dashboard-surface rounded-2xl px-4 py-14 text-center"
    >
      <UIcon
        name="i-lucide-layers-2"
        class="mx-auto h-10 w-10 text-zinc-400"
      />
      <h2 class="mt-3 text-base font-semibold">
        No grouped measurements
      </h2>
      <p class="mt-1 text-sm text-zinc-500">
        Add AFM recipes to Data Grouping before opening See Together.
      </p>
    </section>

    <template v-else>
      <section class="dashboard-surface rounded-2xl">
        <header class="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-list-checks"
              class="h-4 w-4 text-zinc-500"
            />
            <h2 class="text-sm font-semibold">
              Selected measurements
            </h2>
          </div>
          <UBadge
            :label="String(groupedItems.length)"
            color="primary"
            size="xs"
            variant="subtle"
          />
        </header>

        <ul class="grid gap-px divide-y divide-zinc-200 dark:divide-zinc-800">
          <li
            v-for="item in sortedGroupedItems"
            :key="item.filename"
            class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5"
          >
            <span class="font-mono text-xs font-semibold tabular-nums">
              {{ item.formattedDate }}
            </span>
            <span class="truncate text-sm font-medium">
              {{ item.recipeName }}
            </span>
            <span class="font-mono text-xs text-zinc-500">
              {{ item.lotId }}
            </span>
            <UBadge
              :label="`Slot ${item.slotNumber}`"
              size="xs"
              color="neutral"
              variant="subtle"
            />
            <UBadge
              :label="item.measuredInfo"
              size="xs"
              color="neutral"
              variant="outline"
            />
          </li>
        </ul>
      </section>

      <UAlert
        v-if="failedLoads.length > 0"
        color="warning"
        variant="soft"
        icon="i-lucide-triangle-alert"
        :title="`${failedLoads.length} measurements could not be loaded`"
        description="The chart below uses the measurements that returned valid AFM detail data."
      />

      <section class="dashboard-surface rounded-2xl">
        <header class="flex flex-col gap-3 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800 lg:flex-row lg:items-center lg:justify-between">
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-chart-no-axes-combined"
              class="h-4 w-4 text-zinc-500"
            />
            <h2 class="text-sm font-semibold">
              Time series
            </h2>
            <span class="text-xs text-zinc-500">
              {{ loadedPayloads.length }} loaded
            </span>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <USelect
              v-model="selectedSite"
              :items="siteItems"
              size="xs"
              class="min-w-28"
              aria-label="Site"
            />
            <USelect
              v-model="selectedItem"
              :items="statisticItems"
              size="xs"
              class="min-w-28"
              aria-label="Statistic"
            />
            <USelect
              v-model="selectedColumn"
              :items="measurementColumnItems"
              size="xs"
              class="min-w-36"
              aria-label="Measurement column"
            />
          </div>
        </header>

        <div class="p-4">
          <div
            v-if="pending"
            class="flex h-96 items-center justify-center text-sm text-zinc-500"
          >
            <UIcon
              name="i-lucide-loader-circle"
              class="mr-2 h-4 w-4 animate-spin"
            />
            Loading grouped measurement details...
          </div>
          <div
            v-else-if="loadedPayloads.length === 0"
            class="flex h-96 items-center justify-center text-center text-sm text-zinc-500"
          >
            No measurement details were loaded.
          </div>
          <div
            v-else-if="!selectedSite || !selectedColumn"
            class="flex h-96 items-center justify-center text-center text-sm text-zinc-500"
          >
            Select a site and measurement column.
          </div>
          <AfmTrendTimeSeriesChart
            v-else
            :series="chartSeries"
            :selected-column="selectedColumn"
          />
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { AfmGroupedEntry } from '~/composables/useAfmCart'
import type {
  AfmDetailPayload,
  AfmSummaryItem,
  AfmSummaryRow
} from '~/composables/useAfmDetailApi'
import { AFM_SUMMARY_ITEMS } from '~/composables/useAfmDetailApi'

definePageMeta({
  layout: 'hub',
  key: route => route.path
})

interface LoadedMeasurement {
  measurement: AfmGroupedEntry
  payload: AfmDetailPayload | null
  error: string | null
}

interface AfmTrendPoint {
  timestamp: string
  value: number
  lotId: string
  recipe: string
  filename: string
  site: string
}

interface AfmTrendSeries {
  name: string
  data: AfmTrendPoint[]
}

const route = useRoute()
const toolId = computed(() => String(route.params.tool ?? ''))
const toolName = computed(() => toolId.value.toUpperCase())
const cart = useAfmCart(toolId.value)
const { fetchDetail } = useAfmDetailApi()

const groupedItems = computed(() => cart.groupedData.value)
const sortedGroupedItems = computed(() =>
  [...groupedItems.value].sort((a, b) => a.formattedDate.localeCompare(b.formattedDate))
)
const groupKey = computed(() =>
  groupedItems.value.map(item => `${item.toolId}:${item.filename}`).sort().join('|')
)

const { data: loadedMeasurements, pending } = await useAsyncData(
  `afm-see-together:${toolName.value}`,
  async (): Promise<LoadedMeasurement[]> => {
    if (groupedItems.value.length === 0) return []

    return await Promise.all(groupedItems.value.map(async (measurement) => {
      const measurementTool = measurement.toolId ? measurement.toolId.toUpperCase() : toolName.value
      try {
        const response = await fetchDetail(measurementTool, measurement.filename)
        return {
          measurement,
          payload: response.success ? response.data : null,
          error: response.success ? null : 'Detail response was not successful'
        }
      } catch (error) {
        return {
          measurement,
          payload: null,
          error: error instanceof Error ? error.message : 'Detail request failed'
        }
      }
    }))
  },
  { watch: [groupKey] }
)

const loadedRows = computed(() => loadedMeasurements.value ?? [])
const loadedPayloads = computed(() => loadedRows.value.filter(row => row.payload))
const failedLoads = computed(() => loadedRows.value.filter(row => row.error))

const statisticItems = [...AFM_SUMMARY_ITEMS]
const selectedSite = ref('')
const selectedItem = ref<AfmSummaryItem>('MEAN')
const selectedColumn = ref('')

const naturalCompare = (a: string, b: string) =>
  a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })

const siteItems = computed(() => {
  const sites = new Set<string>()
  for (const row of loadedPayloads.value) {
    for (const site of row.payload?.available_points ?? []) sites.add(site)
    for (const summaryRow of row.payload?.summary ?? []) {
      if (summaryRow.Site) sites.add(summaryRow.Site)
    }
  }
  return Array.from(sites).sort(naturalCompare)
})

const measurementColumnItems = computed(() => {
  const columns = new Set<string>()
  for (const row of loadedPayloads.value) {
    const summary = row.payload?.summary ?? []
    for (const summaryRow of summary) {
      for (const key of Object.keys(summaryRow)) {
        if (key !== 'Site' && key !== 'ITEM' && key.toLowerCase().includes('nm')) {
          columns.add(key)
        }
      }
    }
  }
  return Array.from(columns).sort(naturalCompare)
})

watch(siteItems, (next) => {
  if (!next.includes(selectedSite.value)) selectedSite.value = next[0] ?? ''
}, { immediate: true })

watch(measurementColumnItems, (next) => {
  if (!next.includes(selectedColumn.value)) selectedColumn.value = next[0] ?? ''
}, { immediate: true })

const parseTimestamp = (payload: AfmDetailPayload, measurement: AfmGroupedEntry) => {
  const startTime = payload.information['Start Time']
  if (typeof startTime === 'string' && startTime.trim()) return startTime
  return measurement.formattedDate
}

const valueFromSummary = (summary: AfmSummaryRow[], site: string, item: AfmSummaryItem, column: string) => {
  const row = summary.find(candidate => candidate.Site === site && candidate.ITEM === item)
  const raw = row?.[column]
  if (typeof raw === 'number') return raw
  if (typeof raw === 'string') {
    const parsed = Number.parseFloat(raw)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

const chartSeries = computed<AfmTrendSeries[]>(() => {
  if (!selectedSite.value || !selectedColumn.value) return []

  const points = loadedPayloads.value.flatMap((row) => {
    if (!row.payload) return []
    const value = valueFromSummary(row.payload.summary, selectedSite.value, selectedItem.value, selectedColumn.value)
    if (value === null) return []
    return [{
      timestamp: parseTimestamp(row.payload, row.measurement),
      value,
      lotId: row.measurement.lotId,
      recipe: row.measurement.recipeName,
      filename: row.measurement.filename,
      site: selectedSite.value
    }]
  }).sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())

  return points.length > 0
    ? [{ name: selectedSite.value, data: points }]
    : []
})
</script>
