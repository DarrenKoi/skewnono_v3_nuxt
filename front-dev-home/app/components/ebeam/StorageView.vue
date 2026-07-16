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
      class="dashboard-surface"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <h2 class="sk-heading">
            스토리지 용량
          </h2>
          <UBadge
            color="neutral"
            variant="subtle"
          >
            {{ filteredRows.length }} / {{ rows.length }}
          </UBadge>
        </div>
      </template>

      <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-(--sk-border)">
        <UInput
          v-model="globalFilter"
          class="flex-1 min-w-[14rem]"
          size="xs"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="장비 ID, Model, IP 검색"
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
          label="초기화"
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
        스토리지 정보를 불러오는 중입니다.
      </div>
      <div
        v-else-if="error"
        class="px-4 py-12 text-center text-sm text-rose-600 dark:text-rose-400"
      >
        스토리지 정보를 불러오지 못했습니다.
      </div>
      <UTable
        v-else
        v-model:sorting="storageSorting"
        class="max-h-[36rem]"
        :columns="columns"
        :data="filteredRows"
        empty="검색 조건에 맞는 스토리지 정보가 없습니다."
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
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ head.label }}
          </UButton>
        </template>

        <template #eqp_id-cell="{ row }">
          <span class="sk-value-num">{{ row.original.eqp_id }}</span>
        </template>
        <template #eqp_ip-cell="{ row }">
          <span class="sk-value-num">{{ row.original.eqp_ip }}</span>
        </template>
        <template #fab_name-cell="{ row }">
          <span class="sk-value">{{ row.original.fab_name }}</span>
        </template>
        <template #eqp_model_cd-cell="{ row }">
          <span class="sk-value-num">{{ row.original.eqp_model_cd }}</span>
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
            <span class="italic">스토리지 정보 없음</span>
          </div>
          <div
            v-else
            class="flex items-center gap-2 min-w-[10rem]"
          >
            <!-- 6px track at 6px radius (--sk-r-sidebar) reads as a bar without
                 reaching for the banned rounded-full. -->
            <div class="flex-1 h-1.5 rounded-[var(--sk-r-sidebar)] bg-(--sk-muted-surface) overflow-hidden">
              <div
                class="h-full rounded-[var(--sk-r-sidebar)] transition-colors duration-200"
                :class="usageBarClass(parsePercent(row.original.percent))"
                :style="{ width: `${parsePercent(row.original.percent)}%` }"
              />
            </div>
            <span
              class="font-semibold tabular-nums w-10 text-right"
              :class="usageTextClass(parsePercent(row.original.percent))"
            >{{ row.original.percent }}</span>
          </div>
        </template>
        <template #total-cell="{ row }">
          <span
            class="font-mono tabular-nums"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : 'text-(--sk-ink)'"
          >{{ storageNa(row.original) ? 'N/A' : row.original.total }}</span>
        </template>
        <template #used-cell="{ row }">
          <span
            class="font-mono tabular-nums"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : 'text-(--sk-ink)'"
          >{{ storageNa(row.original) ? 'N/A' : row.original.used }}</span>
        </template>
        <template #avail-cell="{ row }">
          <span
            class="font-mono tabular-nums"
            :class="storageNa(row.original) ? 'text-(--sk-ink-muted) italic' : 'text-(--sk-ink)'"
          >{{ storageNa(row.original) ? 'N/A' : row.original.avail }}</span>
        </template>
        <template #rcp_counts-cell="{ row }">
          <span
            class="inline-flex items-center gap-1 tabular-nums text-(--sk-ink)"
            :class="rcpClass(row.original.rcp_counts)"
            :title="rcpTier(row.original.rcp_counts) === 'critical' ? 'Recipe 상한(50,000)에 근접했습니다. 정리가 필요합니다.' : rcpTier(row.original.rcp_counts) === 'warning' ? 'Recipe 수가 많습니다. 상한에 주의하세요.' : undefined"
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
          <span class="text-(--sk-ink) tabular-nums">{{ row.original.storage_mt ? formatTimestamp(row.original.storage_mt) : '—' }}</span>
        </template>
      </UTable>
    </UCard>

    <EbeamStoragePpidUnavailablePanel
      :rows="ppidUnavailableRows"
      :latest-date="ppidLatestDate"
      :pending="ppidUnavailablePending"
      :error="ppidUnavailableError"
      :fab="props.fab"
      :tool-label="props.toolLabel"
    />
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { Fab, ToolType } from '~/stores/navigation'
import type { StorageRow, StorageTool, PpidUnavailableSnapshot } from '~/composables/useStorageApi'
import { isStorageUnavailable } from '~/composables/useStorageApi'
import { storageUsageTier } from '~/utils/storageUsage'
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

// Status hues come from the --sk-ok/warn/bad families, not raw Tailwind colors:
// the token pairs are already tuned per mode, so one class covers light + dark.
const usageBarClass = (percent: number) => {
  switch (storageUsageTier(percent)) {
    case 'critical':
      return 'bg-(--sk-bad)'
    case 'warning':
      return 'bg-(--sk-warn)'
    default:
      return 'bg-(--sk-ok)'
  }
}

const usageTextClass = (percent: number) => {
  switch (storageUsageTier(percent)) {
    case 'critical':
      return 'text-(--sk-bad)'
    case 'warning':
      return 'text-(--sk-warn)'
    default:
      return 'text-(--sk-ok)'
  }
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
      return 'text-(--sk-bad) font-bold'
    case 'warning':
      return 'text-(--sk-warn) font-semibold'
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

// Option labels are Korean, values stay English keys. Domain tokens that appear
// as column headers (Model, IP, Fab, Recipe) keep their English form.
const usageFilterOptions = [
  { label: '전체 사용률', value: 'all' },
  { label: '위험 (98% 이상)', value: 'critical' },
  { label: '주의 (90–97%)', value: 'warning' },
  { label: '정상 (90% 미만)', value: 'healthy' },
  { label: '정보 없음', value: 'unavailable' }
]

const sortOptions = [
  { label: '사용률 높은 순', value: 'percent:desc' },
  { label: '사용률 낮은 순', value: 'percent:asc' },
  { label: '장비 ID 오름차순', value: 'eqp_id:asc' },
  { label: '장비 ID 내림차순', value: 'eqp_id:desc' },
  { label: 'Fab 오름차순', value: 'fab_name:asc' },
  { label: 'Fab 내림차순', value: 'fab_name:desc' },
  { label: 'Model 오름차순', value: 'eqp_model_cd:asc' },
  { label: 'Model 내림차순', value: 'eqp_model_cd:desc' },
  { label: 'IP 오름차순', value: 'eqp_ip:asc' },
  { label: 'IP 내림차순', value: 'eqp_ip:desc' },
  { label: '전체 용량 큰 순', value: 'total:desc' },
  { label: '전체 용량 작은 순', value: 'total:asc' },
  { label: '사용 용량 큰 순', value: 'used:desc' },
  { label: '사용 용량 작은 순', value: 'used:asc' },
  { label: '잔여 용량 큰 순', value: 'avail:desc' },
  { label: '잔여 용량 작은 순', value: 'avail:asc' },
  { label: 'Recipe 수 많은 순', value: 'rcp_counts:desc' },
  { label: 'Recipe 수 적은 순', value: 'rcp_counts:asc' },
  { label: '최근 보고 순', value: 'storage_mt:desc' },
  { label: '오래된 보고 순', value: 'storage_mt:asc' }
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
      if (usage !== storageUsageTier(pct)) return false
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
    switch (storageUsageTier(parsePercent(row.percent))) {
      case 'critical':
        critical++
        break
      case 'warning':
        warning++
        break
      default:
        healthy++
    }
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
    td: 'py-1.5 px-3 whitespace-nowrap overflow-hidden text-ellipsis sk-value',
    th: 'py-2 px-3 sk-label'
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
</script>
