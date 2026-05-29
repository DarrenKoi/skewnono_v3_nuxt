<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="eyebrow"
      title="장비 상태"
      :subtitle="subtitle"
      cadence="매일 04:30"
      :stats="metaStats"
    >
      <template #toggle>
        <EbeamEquipmentStatusSubTabs />
      </template>
    </EbeamMetaBar>

    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Storage Inventory
          </h2>
          <p class="text-xs text-(--sk-ink-muted) tabular-nums">
            {{ filteredRows.length }} of {{ rows.length }} tools
          </p>
        </div>
      </template>

      <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-zinc-200/70 dark:border-zinc-800/70">
        <UInput
          v-model="globalFilter"
          class="flex-1 min-w-[14rem]"
          size="xs"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="Search storage inventory"
        />

        <USelect
          v-model="usageFilter"
          class="w-[11rem]"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="usageFilterOptions"
        />

        <USelect
          v-model="sortPreset"
          class="w-[14rem]"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="sortOptions"
        />

        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          label="Reset"
          :disabled="!hasActiveControls"
          @click="resetControls"
        />
      </div>

      <div
        v-if="pending"
        class="flex items-center justify-center gap-2 px-4 py-12 text-sm text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        Loading storage data...
      </div>
      <div
        v-else-if="error"
        class="px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-300"
      >
        Failed to load storage data.
      </div>
      <UTable
        v-else
        v-model:sorting="storageSorting"
        class="max-h-[36rem] font-mono-ids"
        :columns="columns"
        :data="filteredRows"
        :empty="`No storage rows match the current search.`"
        :meta="tableMeta"
        :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false, manualSorting: true }"
        sticky="header"
      >
        <template
          v-for="head in storageSortableHeaders"
          :key="head.id"
          #[`${head.id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-zinc-900 dark:hover:text-zinc-100"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ head.label }}
          </UButton>
        </template>

        <template #eqp_id-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px]">{{ row.original.eqp_id }}</span>
        </template>
        <template #eqp_ip-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px] text-(--sk-ink)">{{ row.original.eqp_ip }}</span>
        </template>
        <template #fab_name-cell="{ row }">
          <span class="text-(--sk-ink) font-medium">{{ row.original.fab_name }}</span>
        </template>
        <template #eqp_model_cd-cell="{ row }">
          <span class="font-mono text-[12.5px]">{{ row.original.eqp_model_cd }}</span>
        </template>
        <template #percent-cell="{ row }">
          <div
            v-if="storageNa(row.original)"
            class="flex items-center gap-1.5 min-w-[10rem] text-(--sk-ink-muted)"
          >
            <UIcon
              name="i-lucide-circle-slash"
              class="h-3.5 w-3.5 shrink-0"
            />
            <span class="text-[12px] italic">Storage N/A</span>
          </div>
          <div
            v-else
            class="flex items-center gap-2 min-w-[10rem]"
          >
            <div class="flex-1 h-1.5 rounded-full bg-zinc-200/70 dark:bg-zinc-800/70 overflow-hidden">
              <div
                class="h-full rounded-full transition-all"
                :class="usageBarClass(parsePercent(row.original.percent))"
                :style="{ width: `${parsePercent(row.original.percent)}%` }"
              />
            </div>
            <span
              class="text-[12px] font-semibold tabular-nums w-10 text-right"
              :class="usageTextClass(parsePercent(row.original.percent))"
            >{{ row.original.percent }}</span>
          </div>
        </template>
        <template #total-cell="{ row }">
          <span
            class="font-mono tabular-nums text-[12.5px]"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : ''"
          >{{ storageNa(row.original) ? 'N/A' : row.original.total }}</span>
        </template>
        <template #used-cell="{ row }">
          <span
            class="font-mono tabular-nums text-[12.5px]"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : ''"
          >{{ storageNa(row.original) ? 'N/A' : row.original.used }}</span>
        </template>
        <template #avail-cell="{ row }">
          <span
            class="font-mono tabular-nums text-[12.5px] text-(--sk-ink)"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : ''"
          >{{ storageNa(row.original) ? 'N/A' : row.original.avail }}</span>
        </template>
        <template #rcp_counts-cell="{ row }">
          <span
            class="inline-flex items-center gap-1 tabular-nums text-[12.5px]"
            :class="rcpClass(row.original.rcp_counts)"
            :title="rcpTier(row.original.rcp_counts) === 'critical' ? `Approaching 50,000 recipe cap — manage this tool` : rcpTier(row.original.rcp_counts) === 'warning' ? `High recipe count, watch for cap` : undefined"
          >
            <UIcon
              v-if="rcpTier(row.original.rcp_counts) === 'critical'"
              name="i-lucide-triangle-alert"
              class="h-3 w-3 shrink-0"
            />
            {{ row.original.rcp_counts.toLocaleString() }}
          </span>
        </template>
        <template #storage_mt-cell="{ row }">
          <span class="text-[12px] text-(--sk-ink) tabular-nums">{{ row.original.storage_mt ? formatTimestamp(row.original.storage_mt) : '—' }}</span>
        </template>
      </UTable>
    </UCard>

    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              PPID Unreachable
            </h2>
            <p class="text-[12px] text-(--sk-ink-muted) mt-0.5">
              Latest date:
              <span class="font-mono tabular-nums">{{ ppidLatestDate || '-' }}</span>
            </p>
          </div>

          <p class="text-xs text-(--sk-ink-muted) tabular-nums">
            {{ filteredPpidUnavailable.length }} of {{ ppidUnavailableRows.length }} tools
          </p>
        </div>
      </template>

      <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-zinc-200/70 dark:border-zinc-800/70">
        <UInput
          v-model="ppidUnavailableFilter"
          class="flex-1 min-w-[14rem]"
          size="xs"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="Search unreachable tools"
        />

        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          label="Reset"
          :disabled="!hasActivePpidControls"
          @click="resetPpidFilters"
        />
      </div>

      <div
        v-if="ppidUnavailablePending"
        class="flex items-center justify-center gap-2 px-4 py-10 text-sm text-(--sk-ink-muted)"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        Loading daily PPID-unreachable data...
      </div>
      <div
        v-else-if="ppidUnavailableError"
        class="px-4 py-10 text-center text-sm text-rose-600 dark:text-rose-300"
      >
        Failed to load PPID-unreachable list.
      </div>
      <div
        v-else-if="ppidUnavailableRows.length === 0"
        class="px-4 py-12 text-center"
      >
        <UIcon
          name="i-lucide-circle-check-big"
          class="mx-auto mb-2 h-6 w-6 text-emerald-500/80"
        />
        <p class="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          No tools failed PPID access on the latest date.
        </p>
        <p class="text-[12px] text-(--sk-ink-muted) mt-0.5">
          {{ props.fab }} {{ props.toolLabel }} on {{ ppidLatestDate || 'the latest date' }}.
        </p>
      </div>
      <div
        v-else-if="filteredPpidUnavailable.length === 0"
        class="px-4 py-10 text-center"
      >
        <UIcon
          name="i-lucide-filter-x"
          class="mx-auto mb-2 h-6 w-6 text-zinc-400"
        />
        <p class="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          No tools match the current search.
        </p>
        <p class="text-[12px] text-(--sk-ink-muted) mt-0.5">
          {{ ppidUnavailableRows.length }} tools are hidden by search.
        </p>
        <UButton
          class="mt-3"
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          label="Clear search"
          @click="resetPpidFilters"
        />
      </div>
      <UTable
        v-else
        v-model:sorting="ppidSorting"
        class="max-h-[22rem] font-mono-ids"
        :columns="ppidColumns"
        :data="filteredPpidUnavailable"
        :meta="ppidTableMeta"
        :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false, manualSorting: true }"
        sticky="header"
      >
        <template
          v-for="head in ppidSortableHeaders"
          :key="head.id"
          #[`${head.id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-zinc-900 dark:hover:text-zinc-100"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ head.label }}
          </UButton>
        </template>

        <template #fab_name-cell="{ row }">
          <span class="text-(--sk-ink) font-medium">{{ row.original.fab_name || '—' }}</span>
        </template>
        <template #eqp_id-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px]">{{ row.original.eqp_id || '—' }}</span>
        </template>
        <template #eqp_model_cd-cell="{ row }">
          <span class="font-mono text-[12.5px]">{{ row.original.eqp_model_cd || '—' }}</span>
        </template>
        <template #eqp_ip-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px] text-(--sk-ink)">{{ row.original.eqp_ip }}</span>
        </template>
        <template #missing_days_streak-cell="{ row }">
          <span
            class="inline-flex items-center justify-center min-w-[2rem] rounded-md px-1.5 py-0.5 text-[11.5px] font-semibold tabular-nums"
            :class="row.original.missing_days_streak >= 7 ? 'bg-rose-500/10 text-rose-600 dark:text-rose-300' : 'bg-zinc-500/10 text-(--sk-ink-muted)'"
          >{{ row.original.missing_days_streak }}d</span>
        </template>
      </UTable>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { Fab, ToolType } from '~/stores/navigation'
import type { StorageRow, StorageTool, PpidUnavailableSnapshot, PpidUnavailableRow } from '~/composables/useStorageApi'
import { isStorageUnavailable } from '~/composables/useStorageApi'
import type { MetaBarStat } from './MetaBar.vue'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: ToolType
}>()

// Backend storage routes only exist for cd-sem and hv-sem in 2026; default cd-sem
// for any future toolType so the SPA still gets a sensible response.
const storageTool: StorageTool = props.toolType === 'hv-sem' ? 'hv-sem' : 'cd-sem'
const { fetchByUrlFab, fetchPpidUnavailableByUrlFab } = useStorageApi(storageTool)

// Meta bar (design option E): stable "장비 상태" title, fab as eyebrow, freshness
// cadence carries the daily update timing the old subtitle used to spell out.
const subtitle = '스큐노노가 획득한 장비 용량 정보입니다.'
const eyebrow = computed(() => `${props.toolLabel} · ${props.fab}`)

// Abort in-flight fetches on unmount so a fast tab-toggle doesn't leave zombie
// requests consuming the backend rate-limit budget the next mount needs.
const abortController = new AbortController()
onScopeDispose(() => abortController.abort())

const { data, pending, error } = await useAsyncData(
  () => `storage:${storageTool}:${props.fab}`,
  () => fetchByUrlFab(props.fab, abortController.signal),
  {
    watch: [() => props.fab],
    default: () => [] as StorageRow[],
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const {
  data: ppidUnavailableData,
  pending: ppidUnavailablePending,
  error: ppidUnavailableError
} = await useAsyncData(
  () => `ppid-unavailable:${storageTool}:${props.fab}`,
  () => fetchPpidUnavailableByUrlFab(props.fab, abortController.signal),
  {
    watch: [() => props.fab],
    default: (): PpidUnavailableSnapshot => ({ latest_date: '', rows: [] }),
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const rows = computed(() => (data.value ?? []).filter(row => classifyToolType(row.eqp_model_cd) === props.toolType))

const ppidLatestDate = computed(() => ppidUnavailableData.value?.latest_date ?? '')

// Orphan rows (no sem_list match) have an empty eqp_model_cd; keep them so
// data-quality gaps stay visible rather than silently filtered out.
const ppidUnavailableRows = computed(() => (ppidUnavailableData.value?.rows ?? []).filter(row => row.eqp_model_cd === '' || classifyToolType(row.eqp_model_cd) === props.toolType))

const parsePercent = (label: string): number => {
  const parsed = Number.parseInt(label.replace('%', ''), 10)
  return Number.isFinite(parsed) ? parsed : 0
}

const parseSizeGb = (label: string): number => {
  const trimmed = label.trim()
  const numeric = Number.parseFloat(trimmed)
  if (!Number.isFinite(numeric)) return 0
  if (trimmed.endsWith('T')) return numeric * 1024
  return numeric
}

const storageNa = (row: StorageRow): boolean => isStorageUnavailable(row)

const usageBarClass = (percent: number) => {
  if (percent >= 80) return 'bg-rose-500 dark:bg-rose-400'
  if (percent >= 60) return 'bg-amber-500 dark:bg-amber-400'
  return 'bg-emerald-500 dark:bg-emerald-400'
}

const usageTextClass = (percent: number) => {
  if (percent >= 80) return 'text-rose-600 dark:text-rose-300'
  if (percent >= 60) return 'text-amber-600 dark:text-amber-300'
  return 'text-emerald-600 dark:text-emerald-300'
}

// Tools cap at 50,000 recipes; flag well before the ceiling so engineers can
// prune before ingestion blocks. Critical tier doubles up color + weight + icon
// so the warning is perceivable without relying on hue alone.
const RCP_WARNING_THRESHOLD = 49000
const RCP_CRITICAL_THRESHOLD = 49800

type RcpTier = 'normal' | 'warning' | 'critical'

const rcpTier = (count: number): RcpTier => {
  if (count > RCP_CRITICAL_THRESHOLD) return 'critical'
  if (count > RCP_WARNING_THRESHOLD) return 'warning'
  return 'normal'
}

const rcpClass = (count: number) => {
  switch (rcpTier(count)) {
    case 'critical':
      return 'text-rose-600 dark:text-rose-300 font-bold'
    case 'warning':
      return 'text-amber-600 dark:text-amber-300 font-semibold'
    default:
      return ''
  }
}

const formatTimestamp = (iso: string) => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`
}

const globalFilter = ref('')
const usageFilter = ref<'all' | 'critical' | 'warning' | 'healthy' | 'unavailable'>('all')
const defaultSortPreset = 'percent:desc'
const storageSorting = ref<SortingState>([
  {
    id: 'percent',
    desc: true
  }
])

const usageFilterOptions = [
  { label: 'All Usage', value: 'all' },
  { label: 'Critical (>=80%)', value: 'critical' },
  { label: 'Warning (60-79%)', value: 'warning' },
  { label: 'Healthy (<60%)', value: 'healthy' },
  { label: 'Not available', value: 'unavailable' }
]

const sortOptions = [
  { label: 'Usage (High to Low)', value: 'percent:desc' },
  { label: 'Usage (Low to High)', value: 'percent:asc' },
  { label: 'Equipment ID (A-Z)', value: 'eqp_id:asc' },
  { label: 'Equipment ID (Z-A)', value: 'eqp_id:desc' },
  { label: 'Fab (A-Z)', value: 'fab_name:asc' },
  { label: 'Fab (Z-A)', value: 'fab_name:desc' },
  { label: 'Model (A-Z)', value: 'eqp_model_cd:asc' },
  { label: 'Model (Z-A)', value: 'eqp_model_cd:desc' },
  { label: 'IP Address (A-Z)', value: 'eqp_ip:asc' },
  { label: 'IP Address (Z-A)', value: 'eqp_ip:desc' },
  { label: 'Total Capacity (High to Low)', value: 'total:desc' },
  { label: 'Total Capacity (Low to High)', value: 'total:asc' },
  { label: 'Used Capacity (High to Low)', value: 'used:desc' },
  { label: 'Used Capacity (Low to High)', value: 'used:asc' },
  { label: 'Available Capacity (High to Low)', value: 'avail:desc' },
  { label: 'Available Capacity (Low to High)', value: 'avail:asc' },
  { label: 'Recipe Count (High to Low)', value: 'rcp_counts:desc' },
  { label: 'Recipe Count (Low to High)', value: 'rcp_counts:asc' },
  { label: 'Last Reported (Newest)', value: 'storage_mt:desc' },
  { label: 'Last Reported (Oldest)', value: 'storage_mt:asc' }
]

const sortPreset = computed({
  get: () => {
    const currentSort = storageSorting.value[0]

    if (!currentSort) {
      return defaultSortPreset
    }

    return `${currentSort.id}:${currentSort.desc ? 'desc' : 'asc'}`
  },
  set: (value: string) => {
    const [columnId = 'percent', direction = 'desc'] = value.split(':')

    storageSorting.value = [
      {
        id: columnId,
        desc: direction === 'desc'
      }
    ]
  }
})

const sortCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') {
    return 'i-lucide-arrow-up-narrow-wide'
  }

  if (direction === 'desc') {
    return 'i-lucide-arrow-down-wide-narrow'
  }

  return 'i-lucide-arrow-up-down'
}

const readStorageSortValue = (row: StorageRow, key: keyof StorageRow) => {
  if (key === 'percent') return parsePercent(row.percent)
  if (key === 'total' || key === 'used' || key === 'avail') return parseSizeGb(row[key])
  if (key === 'storage_mt') {
    const raw = row.storage_mt
    if (!raw) return 0
    const timestamp = Date.parse(raw)
    return Number.isFinite(timestamp) ? timestamp : raw
  }

  return row[key] ?? ''
}

const compareStorageRows = (left: StorageRow, right: StorageRow, key: keyof StorageRow) => {
  const leftValue = readStorageSortValue(left, key)
  const rightValue = readStorageSortValue(right, key)

  if (typeof leftValue === 'number' && typeof rightValue === 'number') {
    return leftValue - rightValue
  }

  return sortCollator.compare(String(leftValue), String(rightValue))
}

const filteredRows = computed(() => {
  const term = globalFilter.value.trim().toLowerCase()
  const usage = usageFilter.value

  const matched = rows.value.filter((row) => {
    if (term) {
      const haystack = [
        row.eqp_id,
        row.eqp_ip,
        row.fab_name,
        row.eqp_model_cd,
        row.total,
        row.used,
        row.avail,
        row.percent,
        String(row.rcp_counts)
      ]

      if (!haystack.some(value => value.toLowerCase().includes(term))) {
        return false
      }
    }

    const na = storageNa(row)
    if (usage === 'unavailable') {
      if (!na) return false
    } else if (usage !== 'all') {
      if (na) return false
      const pct = parsePercent(row.percent)
      if (usage === 'critical' && pct < 80) return false
      if (usage === 'warning' && (pct < 60 || pct >= 80)) return false
      if (usage === 'healthy' && pct >= 60) return false
    }

    return true
  })

  const currentSort = storageSorting.value[0]

  // Storage-N/A rows have no percent/capacity to rank, so they always sit at
  // the bottom regardless of the active sort.
  const available = matched.filter(row => !storageNa(row))
  const unavailable = matched.filter(row => storageNa(row))

  if (currentSort) {
    const key = currentSort.id as keyof StorageRow
    const direction = currentSort.desc ? -1 : 1
    available.sort((a, b) => {
      const sortResult = compareStorageRows(a, b, key)
      if (sortResult !== 0) return sortResult * direction
      return sortCollator.compare(a.eqp_id, b.eqp_id)
    })
  }

  unavailable.sort((a, b) => sortCollator.compare(a.eqp_id, b.eqp_id))

  return [...available, ...unavailable]
})

const summary = computed(() => {
  let critical = 0
  let warning = 0
  let healthy = 0
  let na = 0
  for (const row of rows.value) {
    if (storageNa(row)) {
      na++
      continue
    }
    const pct = parsePercent(row.percent)
    if (pct >= 80) critical++
    else if (pct >= 60) warning++
    else healthy++
  }

  return {
    total: rows.value.length,
    critical,
    warning,
    healthy,
    na
  }
})

const metaStats = computed<MetaBarStat[]>(() => [
  { key: 'total', label: 'Total Tools', value: summary.value.total, tone: 'neutral' },
  { key: 'critical', label: 'Critical', value: summary.value.critical, tone: 'bad' },
  { key: 'warning', label: 'Warning', value: summary.value.warning, tone: 'warn' },
  { key: 'healthy', label: 'Healthy', value: summary.value.healthy, tone: 'ok' },
  { key: 'na', label: 'Storage N/A', value: summary.value.na, tone: 'neutral' }
])

const hasActiveControls = computed(() => {
  return globalFilter.value.length > 0 || usageFilter.value !== 'all' || sortPreset.value !== defaultSortPreset
})

const resetControls = () => {
  globalFilter.value = ''
  usageFilter.value = 'all'
  storageSorting.value = [
    {
      id: 'percent',
      desc: true
    }
  ]
}

const tableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

type StorageColumnConfig = {
  id: keyof StorageRow
  header: string
  size: number
}

const storageColumnConfigs: StorageColumnConfig[] = [
  { id: 'eqp_id', header: 'Equipment ID', size: 130 },
  { id: 'fab_name', header: 'Fab', size: 64 },
  { id: 'eqp_model_cd', header: 'Model', size: 130 },
  { id: 'eqp_ip', header: 'IP Address', size: 140 },
  { id: 'total', header: 'Total', size: 76 },
  { id: 'used', header: 'Used', size: 76 },
  { id: 'avail', header: 'Available', size: 96 },
  { id: 'percent', header: 'Usage', size: 180 },
  { id: 'rcp_counts', header: 'Recipes', size: 80 },
  { id: 'storage_mt', header: 'Last Reported', size: 140 }
]

const columns: TableColumn<StorageRow>[] = storageColumnConfigs.map(({ id, ...column }) => ({
  accessorKey: id,
  ...column
}))

const storageSortableHeaders = storageColumnConfigs.map(column => ({
  id: column.id,
  label: column.header
}))

const ppidUnavailableFilter = ref('')
const defaultPpidSort = {
  id: 'missing_days_streak',
  desc: true
}
const ppidSorting = ref<SortingState>([
  defaultPpidSort
])

const comparePpidRows = (left: PpidUnavailableRow, right: PpidUnavailableRow, key: keyof PpidUnavailableRow) => {
  const leftValue = left[key]
  const rightValue = right[key]

  if (typeof leftValue === 'number' && typeof rightValue === 'number') {
    return leftValue - rightValue
  }

  return sortCollator.compare(String(leftValue), String(rightValue))
}

const filteredPpidUnavailable = computed(() => {
  const term = ppidUnavailableFilter.value.trim().toLowerCase()

  const matched = ppidUnavailableRows.value.filter((row) => {
    if (!term) return true
    const hay = [
      row.eqp_id,
      row.eqp_ip,
      row.fab_name,
      row.eqp_model_cd
    ]
    return hay.some(v => v.toLowerCase().includes(term))
  })

  const currentSort = ppidSorting.value[0]

  if (!currentSort) {
    return matched
  }

  const key = currentSort.id as keyof PpidUnavailableRow
  const direction = currentSort.desc ? -1 : 1

  return [...matched].sort((a, b) => {
    const sortResult = comparePpidRows(a, b, key)

    if (sortResult !== 0) {
      return sortResult * direction
    }

    return sortCollator.compare(a.eqp_ip, b.eqp_ip)
  })
})

const hasActivePpidControls = computed(() => {
  const currentSort = ppidSorting.value[0]

  return ppidUnavailableFilter.value.length > 0
    || currentSort?.id !== defaultPpidSort.id
    || currentSort?.desc !== defaultPpidSort.desc
})

const resetPpidFilters = () => {
  ppidUnavailableFilter.value = ''
  ppidSorting.value = [
    defaultPpidSort
  ]
}

const ppidTableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

type PpidColumnConfig = {
  id: keyof PpidUnavailableRow
  header: string
  size: number
}

const ppidColumnConfigs: PpidColumnConfig[] = [
  { id: 'missing_days_streak', header: 'Days Down', size: 88 },
  { id: 'fab_name', header: 'Fab', size: 64 },
  { id: 'eqp_id', header: 'Equipment ID', size: 130 },
  { id: 'eqp_model_cd', header: 'Model', size: 130 },
  { id: 'eqp_ip', header: 'IP Address', size: 140 }
]

const ppidColumns: TableColumn<PpidUnavailableRow>[] = ppidColumnConfigs.map(({ id, ...column }) => ({
  accessorKey: id,
  ...column
}))

const ppidSortableHeaders = ppidColumnConfigs.map(column => ({
  id: column.id,
  label: column.header
}))
</script>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
