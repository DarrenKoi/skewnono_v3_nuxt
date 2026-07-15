<template>
  <div class="mx-auto flex w-full max-w-[1600px] flex-col gap-3 pb-20 xl:h-full xl:min-h-0 xl:pb-0">
    <!-- Landing header -->
    <div class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
      <p class="sk-eyebrow">
        {{ toolLabel }} · SKEWVOIR
      </p>
      <h1 class="sk-heading">
        측정 검색
      </h1>
      <p class="sk-meta">
        찾은 측정을 작업 세트에 모아 분석합니다.
      </p>
    </div>

    <div class="grid items-start gap-3 xl:min-h-0 xl:flex-1 xl:grid-cols-[minmax(0,1fr)_340px] xl:items-stretch">
      <main class="flex min-w-0 flex-col gap-3 xl:min-h-0">
        <!-- Search and the active measurement set share the master width
             equally. They are the two inputs to the result/analysis flow. -->
        <div class="grid gap-3 lg:grid-cols-2 lg:items-stretch">
          <div class="dashboard-surface rounded-(--sk-r-card) p-3">
            <EbeamSkewvoirSearchBar
              v-model="search.queryText.value"
              :parsed="search.parsed.value"
              :pending="search.pending.value"
              :retention-days="search.retentionDays.value"
              :disabled="search.searchDisabled.value"
              @search="search.search"
            />
            <EbeamSkewvoirSearchFilterBar
              :filters="search.filters.value"
              :facets="search.facets.value!"
              :disabled="search.facetsPending.value"
              :anchor="search.anchor.value"
              :retention-days="search.retentionDays.value"
              :range="search.resolvedRange.value"
              @update:filters="search.filters.value = $event"
              @set-date-range="search.setDateRange"
              @reset="search.resetFilters"
            />
            <EbeamSkewvoirSearchScopeStrip
              :parsed="search.parsed.value"
              :range="search.resolvedRange.value"
              :retention-days="search.retentionDays.value"
              :searched="search.searched.value"
              :total="search.total.value"
              :capped="search.capped.value"
            />
          </div>

          <EbeamSkewvoirSearchSelectionWorkbench
            :selected="selection.selected.value"
            @remove="selection.remove"
            @clear="selection.clear"
            @analyze="openSet"
          />
        </div>

        <!-- Master: the results own the wide workspace and scroll internally
             on engineering desktop displays. -->
        <EbeamSkewvoirSearchResultTable
          class="xl:min-h-0 xl:flex-1"
          :rows="search.narrowedRows.value"
          :total="search.total.value"
          :capped="search.capped.value"
          :out-of-retention="search.outOfRetention.value"
          :searched="search.searched.value"
          :pending="search.pending.value"
          :error="search.error.value"
          :has-more="search.hasMore.value"
          :narrow-text="search.narrowText.value"
          :retention-days="search.retentionDays.value"
          :selected="selection.selected.value"
          @update:narrow-text="search.narrowText.value = $event"
          @open="open"
          @toggle="selection.toggle"
          @select-rows="selection.setMany"
          @load-more="search.loadMore"
          @retry="search.search"
        />
      </main>

      <!-- Detail: recent history exclusively owns the desktop rail. -->
      <aside class="hidden min-h-0 xl:block">
        <EbeamSkewvoirSearchRecentMeasurementsRail
          :items="recent.items.value"
          @open="openRecent"
          @remove="recent.remove"
          @clear="recent.clear"
        />
      </aside>
    </div>

    <!-- Below desktop width the same detail component becomes an explicit
         drawer; the results table keeps the full available width. -->
    <div class="xl:hidden">
      <UButton
        class="fixed bottom-4 right-4 z-40 shadow-lg"
        color="primary"
        variant="solid"
        icon="i-lucide-history"
        :label="`최근 본 측정 · ${recent.items.value.length}`"
        @click="recentOpen = true"
      />
      <USlideover
        :open="recentOpen"
        title="최근 본 측정"
        description="최근 단일 측정과 Time-Series 분석"
        :ui="{ content: 'w-[92vw] sm:max-w-[390px]' }"
        @update:open="recentOpen = $event"
      >
        <template #body>
          <EbeamSkewvoirSearchRecentMeasurementsRail
            :items="recent.items.value"
            @open="openRecentFromRail"
            @remove="recent.remove"
            @clear="recent.clear"
          />
        </template>
      </USlideover>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { SkewvoirRecentEntry } from '~/composables/useSkewvoirRecentlyViewed'
import type { SkewvoirSelection } from '~/composables/useSkewvoirWorkspace'
import { toSkewvoirRecentMeasurement, type SkewvoirRecentMeasurement } from '~/utils/skewvoirRecent'

const props = defineProps<{
  toolLabel: string
  toolType: MeasHistToolType
}>()

const ws = useSkewvoirWorkspace(props.toolType, props.toolLabel)
const search = useMeasHistSearch(props.toolType)
const selection = useSkewvoirSearchSelection(props.toolType)
const recent = useSkewvoirRecentlyViewed(props.toolType)
const recentOpen = ref(false)

// Expiry in the recently-viewed list is judged against the backend's retention
// anchor, not wall clock.
watch(search.anchor, value => recent.setAnchor(value), { immediate: true })

const toSelection = (row: MeasHistRow): SkewvoirSelection => ({
  lot: row.lot_id,
  recipe: row.recipe_name,
  eq: row.eqp_id,
  mp: 'WAFER',
  msr: row.msr,
  capturedAt: row.timestamp
})

const open = (row: MeasHistRow) => {
  recent.record('single', [toSkewvoirRecentMeasurement(row)])
  ws.openAnalysis(toSelection(row))
}

const openSet = () => {
  const rows = selection.selected.value
  const first = rows[0]
  if (!first) return
  recent.record('time-series', rows.map(toSkewvoirRecentMeasurement))
  ws.openAnalysisSet(toSelection(first), rows.map(r => r.msr), 'time-series')
}

const recentSelection = (measurement: SkewvoirRecentMeasurement): SkewvoirSelection => ({
  lot: measurement.lot,
  recipe: measurement.recipe.includes('/')
    ? measurement.recipe.slice(measurement.recipe.indexOf('/') + 1)
    : measurement.recipe,
  eq: measurement.eq,
  mp: 'WAFER',
  msr: measurement.msr,
  capturedAt: measurement.capturedAt
})

const openRecent = (item: SkewvoirRecentEntry) => {
  const focus = item.measurements[0]
  if (!focus) return
  // Reopening an entry makes it recent again and moves it to the top.
  recent.record(item.mode, item.measurements)
  const focusSelection = recentSelection(focus)
  if (item.mode === 'time-series') {
    ws.openAnalysisSet(
      focusSelection,
      item.measurements.map(measurement => measurement.msr),
      'time-series'
    )
    return
  }

  ws.openAnalysis(focusSelection)
}

const openRecentFromRail = (item: SkewvoirRecentEntry) => {
  recentOpen.value = false
  openRecent(item)
}
</script>
