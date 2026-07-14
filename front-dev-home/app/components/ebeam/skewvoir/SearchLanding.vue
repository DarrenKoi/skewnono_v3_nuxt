<template>
  <div class="space-y-4">
    <!-- Landing header -->
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="font-mono text-[11px] tracking-wide text-(--sk-ink-subtle)">
          {{ toolLabel }} · SKEWVOIR
        </p>
        <h1 class="mt-0.5 text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          측정 결과 검색
        </h1>
        <p class="mt-1 text-[12.5px] text-(--sk-ink-muted)">
          Lot · Recipe · 장비 · 날짜 · MSR 로 측정을 찾고, 결과를 열면 분석 워크스페이스로 이동합니다.
        </p>
      </div>

      <!-- Saved views -->
      <UPopover>
        <UButton
          color="neutral"
          variant="outline"
          icon="i-lucide-bookmark"
          :label="`저장된 뷰 ${savedViews.views.value.length}`"
          size="sm"
        />
        <template #content>
          <div class="w-80 p-2">
            <p class="px-2 py-1 font-mono text-[10px] font-semibold tracking-wider text-(--sk-ink-muted)">
              SAVED VIEWS
            </p>
            <p
              v-if="!savedViews.views.value.length"
              class="px-2 py-3 text-[12px] text-(--sk-ink-muted)"
            >
              저장된 뷰가 없습니다. 분석 화면에서 “Save view”로 저장하세요.
            </p>
            <ul
              v-else
              class="max-h-72 space-y-0.5 overflow-y-auto"
            >
              <li
                v-for="v in savedViews.views.value"
                :key="v.id"
                class="group flex items-center gap-2 rounded-(--sk-r-nav) px-2 py-1.5 hover:bg-zinc-500/10"
              >
                <button
                  type="button"
                  class="min-w-0 flex-1 text-left"
                  @click="openSaved(v)"
                >
                  <span class="block truncate text-[12.5px] font-medium text-zinc-800 dark:text-zinc-100">{{ v.name }}</span>
                  <span class="block truncate font-mono text-[10.5px] text-(--sk-ink-subtle)">{{ String(v.query.lot ?? '') }}</span>
                </button>
                <button
                  type="button"
                  class="opacity-0 transition-opacity group-hover:opacity-100"
                  @click="savedViews.remove(v.id)"
                >
                  <UIcon
                    name="i-lucide-x"
                    class="h-3.5 w-3.5 text-(--sk-ink-muted) hover:text-(--sk-bad)"
                  />
                </button>
              </li>
            </ul>
          </div>
        </template>
      </UPopover>
    </div>

    <!-- Search + filters -->
    <div class="dashboard-surface rounded-(--sk-r-card) p-3">
      <EbeamSkewvoirSearchBar
        v-model="search.queryText.value"
        :parsed="search.parsed.value"
        :pending="search.pending.value"
        :retention-days="search.retentionDays.value"
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
    </div>

    <!-- Results -->
    <EbeamSkewvoirSearchResultTable
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
      @update:narrow-text="search.narrowText.value = $event"
      @open="open"
      @open-set="openSet"
      @load-more="search.loadMore"
      @retry="search.search"
    />

    <!-- Recently viewed (localStorage) -->
    <EbeamSkewvoirSearchRecentlyViewed
      :items="recent.items.value"
      @open="openRecent"
      @remove="recent.remove"
      @clear="recent.clear"
    />
  </div>
</template>

<script setup lang="ts">
import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { SkewvoirRecentEntry } from '~/composables/useSkewvoirRecentlyViewed'
import type { SkewvoirSavedView } from '~/composables/useSkewvoirSavedViews'
import type { SkewvoirSelection } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{
  toolLabel: string
  toolType: MeasHistToolType
}>()

const ws = useSkewvoirWorkspace(props.toolType, props.toolLabel)
const savedViews = useSkewvoirSavedViews(props.toolType)
const search = useMeasHistSearch(props.toolType)
const recent = useSkewvoirRecentlyViewed(props.toolType)
const router = useRouter()

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
  recent.record({
    msr: row.msr,
    toolType: props.toolType,
    lot: row.lot_id,
    recipe: row.full_name,
    eq: row.eqp_id,
    fab: row.fab_name,
    capturedAt: row.timestamp,
    viewedAt: new Date().toISOString()
  })
  ws.openAnalysis(toSelection(row))
}

const openSet = (rows: MeasHistRow[]) => {
  const first = rows[0]
  if (!first) return
  ws.openAnalysisSet(toSelection(first), rows.map(r => r.msr), 'time-series')
}

const openRecent = (item: SkewvoirRecentEntry) => {
  ws.openAnalysis({
    lot: item.lot,
    recipe: item.recipe.includes('/') ? item.recipe.split('/')[1]! : item.recipe,
    eq: item.eq,
    mp: 'WAFER',
    msr: item.msr,
    capturedAt: item.capturedAt
  })
}

const openSaved = (v: SkewvoirSavedView) =>
  router.push({ path: ws.analysisPath, query: v.query })
</script>
