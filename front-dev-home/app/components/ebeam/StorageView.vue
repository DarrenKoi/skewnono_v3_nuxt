<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          {{ toolLabel }}
        </p>
        <h1 class="text-2xl font-bold text-zinc-950 dark:text-zinc-50">
          Storage - {{ fab }}
        </h1>
        <p class="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
          {{ subtitle }}
        </p>
      </div>

      <div class="dashboard-surface rounded-2xl flex overflow-hidden self-start md:self-auto">
        <div
          v-for="(cell, index) in statCells"
          :key="cell.label"
          class="px-5 py-2.5 flex flex-col gap-0.5 min-w-[96px]"
          :class="{ 'border-l border-zinc-200/70 dark:border-zinc-800/70': index > 0 }"
        >
          <span
            class="text-[22px] font-bold leading-none tabular-nums"
            :class="cell.tone"
          >{{ cell.value }}</span>
          <span class="text-[11px] text-zinc-500">{{ cell.label }}</span>
        </div>
      </div>
    </div>

    <UCard
      class="dashboard-surface rounded-2xl"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Storage Inventory
          </h2>
          <p class="text-xs text-zinc-500 tabular-nums">
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
        class="flex items-center justify-center gap-2 px-4 py-12 text-sm text-zinc-500"
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
        class="max-h-[36rem] font-mono-ids"
        :columns="columns"
        :data="filteredRows"
        :empty="`No storage rows match the current search.`"
        :meta="tableMeta"
        sticky="header"
      >
        <template #eqp_id-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px]">{{ row.original.eqp_id }}</span>
        </template>
        <template #eqp_ip-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px] text-zinc-500">{{ row.original.eqp_ip }}</span>
        </template>
        <template #fab_name-cell="{ row }">
          <span class="text-zinc-500 font-medium">{{ row.original.fab_name }}</span>
        </template>
        <template #eqp_model_cd-cell="{ row }">
          <span class="font-mono text-[12.5px]">{{ row.original.eqp_model_cd }}</span>
        </template>
        <template #percent-cell="{ row }">
          <div class="flex items-center gap-2 min-w-[10rem]">
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
          <span class="font-mono tabular-nums text-[12.5px]">{{ row.original.total }}</span>
        </template>
        <template #used-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px]">{{ row.original.used }}</span>
        </template>
        <template #avail-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px] text-zinc-500">{{ row.original.avail }}</span>
        </template>
        <template #rcp_counts-cell="{ row }">
          <span class="tabular-nums text-[12.5px]">{{ row.original.rcp_counts }}</span>
        </template>
        <template #storage_mt-cell="{ row }">
          <span class="text-[12px] text-zinc-500 tabular-nums">{{ formatTimestamp(row.original.storage_mt) }}</span>
        </template>
      </UTable>
    </UCard>

    <UCard
      class="diagnostic-surface rounded-2xl"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <span class="diagnostic-dot" />
            <h2 class="text-sm font-semibold text-zinc-800 dark:text-zinc-200 tracking-wide">
              Storage Unreachable
            </h2>
            <span class="hidden sm:inline text-[11px] uppercase tracking-[0.14em] text-zinc-400 dark:text-zinc-500">
              · diagnostics
            </span>
          </div>

          <div class="flex items-center gap-2 flex-wrap">
            <div class="flex items-center gap-1.5 text-[11px] tabular-nums text-zinc-500 dark:text-zinc-400">
              <span class="font-semibold text-zinc-700 dark:text-zinc-300">{{ filteredUnavailable.length }}</span>
              <span>tools ·</span>
              <span class="text-amber-700 dark:text-amber-300">{{ unavailableSummary.unreachable }} unreachable</span>
              <span>·</span>
              <span class="text-orange-700 dark:text-orange-300">{{ unavailableSummary.stale }} stale</span>
              <span>·</span>
              <span class="text-rose-700 dark:text-rose-300">{{ unavailableSummary.auth_failed }} auth</span>
              <span>·</span>
              <span class="text-zinc-600 dark:text-zinc-400">{{ unavailableSummary.never_reported }} new</span>
            </div>

            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-rotate-cw"
              label="Retry sweep"
              :loading="unavailablePending"
              @click="refreshUnavailable()"
            />
          </div>
        </div>
      </template>

      <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-dashed border-zinc-300/70 dark:border-zinc-700/60">
        <UInput
          v-model="unavailableFilter"
          class="flex-1 min-w-[14rem]"
          size="xs"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="Search unreachable tools"
        />

        <div class="flex items-center gap-1">
          <button
            v-for="opt in reasonChipOptions"
            :key="opt.value"
            type="button"
            class="reason-chip"
            :class="[reasonChipClass(opt.value), { 'reason-chip--active': reasonFilter === opt.value }]"
            @click="reasonFilter = reasonFilter === opt.value ? 'all' : opt.value"
          >
            <UIcon
              :name="opt.icon"
              class="h-3 w-3"
            />
            <span>{{ opt.label }}</span>
            <span class="reason-chip__count">{{ opt.count }}</span>
          </button>
        </div>
      </div>

      <div
        v-if="unavailablePending"
        class="flex items-center justify-center gap-2 px-4 py-10 text-sm text-zinc-500"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        Probing unreachable tools...
      </div>
      <div
        v-else-if="unavailableError"
        class="px-4 py-10 text-center text-sm text-rose-600 dark:text-rose-300"
      >
        Failed to load unreachable list.
      </div>
      <div
        v-else-if="unavailableRows.length === 0"
        class="px-4 py-12 text-center"
      >
        <UIcon
          name="i-lucide-circle-check-big"
          class="mx-auto mb-2 h-6 w-6 text-emerald-500/80"
        />
        <p class="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          All tools reporting cleanly.
        </p>
        <p class="text-[12px] text-zinc-500 mt-0.5">
          No unreachable storage probes for {{ props.fab }} {{ props.toolLabel }}.
        </p>
      </div>
      <div
        v-else-if="filteredUnavailable.length === 0"
        class="px-4 py-10 text-center"
      >
        <UIcon
          name="i-lucide-filter-x"
          class="mx-auto mb-2 h-6 w-6 text-zinc-400"
        />
        <p class="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          No tools match the current filter.
        </p>
        <p class="text-[12px] text-zinc-500 mt-0.5">
          {{ unavailableRows.length }} unreachable {{ unavailableRows.length === 1 ? 'tool is' : 'tools are' }} hidden by search or reason filter.
        </p>
        <UButton
          class="mt-3"
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          label="Clear filters"
          @click="resetUnavailableFilters"
        />
      </div>
      <UTable
        v-else
        class="max-h-[28rem] font-mono-ids"
        :columns="unavailableColumns"
        :data="filteredUnavailable"
        :meta="unavailableTableMeta"
        sticky="header"
      >
        <template #reason-cell="{ row }">
          <span
            class="reason-pill"
            :class="reasonPillClass(row.original.reason)"
          >
            <UIcon
              :name="reasonMeta(row.original.reason).icon"
              class="h-3 w-3"
            />
            {{ reasonMeta(row.original.reason).label }}
          </span>
        </template>
        <template #eqp_id-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px]">{{ row.original.eqp_id }}</span>
        </template>
        <template #fab_name-cell="{ row }">
          <span class="text-zinc-500 font-medium">{{ row.original.fab_name }}</span>
        </template>
        <template #eqp_model_cd-cell="{ row }">
          <span class="font-mono text-[12.5px]">{{ row.original.eqp_model_cd }}</span>
        </template>
        <template #eqp_ip-cell="{ row }">
          <span class="font-mono tabular-nums text-[12.5px] text-zinc-500">{{ row.original.eqp_ip }}</span>
        </template>
        <template #error_code-cell="{ row }">
          <span class="error-code">{{ row.original.error_code }}</span>
        </template>
        <template #last_success-cell="{ row }">
          <span
            v-if="row.original.last_success"
            class="text-[12px] tabular-nums text-zinc-500"
          >{{ formatRelative(row.original.last_success) }}</span>
          <span
            v-else
            class="never-pill"
          >never</span>
        </template>
        <template #last_attempt-cell="{ row }">
          <span class="text-[12px] tabular-nums text-zinc-500">{{ formatRelative(row.original.last_attempt) }}</span>
        </template>
      </UTable>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Fab, ToolType } from '~/stores/navigation'
import type { StorageRow, UnavailableRow, UnavailableReason, StorageTool } from '~/composables/useStorageApi'

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: ToolType
}>()

// Backend storage routes only exist for cd-sem and hv-sem in 2026; default cd-sem
// for any future toolType so the SPA still gets a sensible response.
const storageTool: StorageTool = props.toolType === 'hv-sem' ? 'hv-sem' : 'cd-sem'
const { fetchByUrlFab, fetchUnavailableByUrlFab } = useStorageApi(storageTool)

const subtitle = computed(() => `Storage usage for ${props.fab} ${props.toolLabel} tools.`)

const { data, pending, error } = await useAsyncData(
  () => `storage:${storageTool}:${props.fab}`,
  () => fetchByUrlFab(props.fab),
  { watch: [() => props.fab], default: () => [] as StorageRow[] }
)

const {
  data: unavailableData,
  pending: unavailablePending,
  error: unavailableError,
  refresh: refreshUnavailable
} = await useAsyncData(
  () => `storage-unavailable:${storageTool}:${props.fab}`,
  () => fetchUnavailableByUrlFab(props.fab),
  { watch: [() => props.fab], default: () => [] as UnavailableRow[] }
)

const rows = computed(() => (data.value ?? []).filter(row => classifyToolType(row.eqp_model_cd) === props.toolType))

const unavailableRows = computed(() => (unavailableData.value ?? []).filter(row => classifyToolType(row.eqp_model_cd) === props.toolType))

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
const usageFilter = ref<'all' | 'critical' | 'warning' | 'healthy'>('all')
const sortPreset = ref('percent:desc')

const usageFilterOptions = [
  { label: 'All Usage', value: 'all' },
  { label: 'Critical (>=80%)', value: 'critical' },
  { label: 'Warning (60-79%)', value: 'warning' },
  { label: 'Healthy (<60%)', value: 'healthy' }
]

const sortOptions = [
  { label: 'Usage (High to Low)', value: 'percent:desc' },
  { label: 'Usage (Low to High)', value: 'percent:asc' },
  { label: 'Equipment ID (A-Z)', value: 'eqp_id:asc' },
  { label: 'Equipment ID (Z-A)', value: 'eqp_id:desc' },
  { label: 'Total Capacity (High to Low)', value: 'total:desc' },
  { label: 'Total Capacity (Low to High)', value: 'total:asc' },
  { label: 'Recipe Count (High to Low)', value: 'rcp_counts:desc' },
  { label: 'Recipe Count (Low to High)', value: 'rcp_counts:asc' }
]

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

    if (usage !== 'all') {
      const pct = parsePercent(row.percent)
      if (usage === 'critical' && pct < 80) return false
      if (usage === 'warning' && (pct < 60 || pct >= 80)) return false
      if (usage === 'healthy' && pct >= 60) return false
    }

    return true
  })

  const [keyRaw, dirRaw] = sortPreset.value.split(':')
  const key = (keyRaw ?? 'percent') as keyof StorageRow
  const dir = dirRaw === 'desc' ? -1 : 1
  const numericKeys: (keyof StorageRow)[] = ['percent', 'total', 'used', 'avail', 'rcp_counts']

  return [...matched].sort((a, b) => {
    if (numericKeys.includes(key)) {
      const left = key === 'rcp_counts'
        ? Number(a[key])
        : key === 'percent'
          ? parsePercent(a[key] as string)
          : parseSizeGb(a[key] as string)
      const right = key === 'rcp_counts'
        ? Number(b[key])
        : key === 'percent'
          ? parsePercent(b[key] as string)
          : parseSizeGb(b[key] as string)
      return (left - right) * dir
    }
    return String(a[key]).localeCompare(String(b[key]), undefined, { numeric: true }) * dir
  })
})

const summary = computed(() => {
  const total = rows.value.length
  if (total === 0) {
    return { total: 0, avg: 0, critical: 0, healthy: 0 }
  }

  let sum = 0
  let critical = 0
  let healthy = 0
  for (const row of rows.value) {
    const pct = parsePercent(row.percent)
    sum += pct
    if (pct >= 80) critical++
    else if (pct < 60) healthy++
  }

  return {
    total,
    avg: Math.round(sum / total),
    critical,
    healthy
  }
})

const statCells = computed(() => [
  { label: 'Total Tools', value: summary.value.total, tone: 'text-zinc-900 dark:text-zinc-100' },
  { label: 'Avg Usage', value: `${summary.value.avg}%`, tone: 'text-(--sk-accent)' },
  { label: 'Critical', value: summary.value.critical, tone: 'text-rose-600 dark:text-rose-300' },
  { label: 'Healthy', value: summary.value.healthy, tone: 'text-emerald-600 dark:text-emerald-300' }
])

const hasActiveControls = computed(() => {
  return globalFilter.value.length > 0 || usageFilter.value !== 'all' || sortPreset.value !== 'percent:desc'
})

const resetControls = () => {
  globalFilter.value = ''
  usageFilter.value = 'all'
  sortPreset.value = 'percent:desc'
}

const tableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-zinc-50/60 dark:bg-zinc-900/40'
  }
}

const columns: TableColumn<StorageRow>[] = [
  { accessorKey: 'eqp_id', header: 'Equipment ID', size: 130 },
  { accessorKey: 'fab_name', header: 'Fab', size: 64 },
  { accessorKey: 'eqp_model_cd', header: 'Model', size: 130 },
  { accessorKey: 'eqp_ip', header: 'IP Address', size: 140 },
  { accessorKey: 'total', header: 'Total', size: 76 },
  { accessorKey: 'used', header: 'Used', size: 76 },
  { accessorKey: 'avail', header: 'Available', size: 96 },
  { accessorKey: 'percent', header: 'Usage', size: 180 },
  { accessorKey: 'rcp_counts', header: 'Recipes', size: 80 },
  { accessorKey: 'storage_mt', header: 'Last Reported', size: 140 }
]

// ---------------------------------------------------------------------------
// Diagnostics: unreachable / failed-extraction tools.
// ---------------------------------------------------------------------------

const REASON_META: Record<UnavailableReason, { label: string, icon: string }> = {
  unreachable: { label: 'Unreachable', icon: 'i-lucide-wifi-off' },
  stale: { label: 'Stale', icon: 'i-lucide-clock-alert' },
  auth_failed: { label: 'Auth failed', icon: 'i-lucide-shield-alert' },
  never_reported: { label: 'Never reported', icon: 'i-lucide-circle-dashed' }
}

const reasonMeta = (reason: UnavailableReason) => REASON_META[reason]

const reasonPillClass = (reason: UnavailableReason) => {
  switch (reason) {
    case 'unreachable':
      return 'reason-pill--amber'
    case 'stale':
      return 'reason-pill--orange'
    case 'auth_failed':
      return 'reason-pill--rose'
    case 'never_reported':
      return 'reason-pill--dashed'
  }
}

const reasonChipClass = (reason: 'all' | UnavailableReason) => {
  if (reason === 'all') return 'reason-chip--neutral'
  return `reason-chip--${reason}`
}

const unavailableFilter = ref('')
const reasonFilter = ref<'all' | UnavailableReason>('all')

const unavailableSummary = computed(() => {
  const counts: Record<UnavailableReason, number> = {
    unreachable: 0,
    stale: 0,
    auth_failed: 0,
    never_reported: 0
  }
  for (const row of unavailableRows.value) counts[row.reason]++
  return counts
})

const reasonChipOptions = computed(() => [
  { value: 'all' as const, label: 'All', icon: 'i-lucide-list', count: unavailableRows.value.length },
  { value: 'unreachable' as const, label: 'Unreachable', icon: REASON_META.unreachable.icon, count: unavailableSummary.value.unreachable },
  { value: 'stale' as const, label: 'Stale', icon: REASON_META.stale.icon, count: unavailableSummary.value.stale },
  { value: 'auth_failed' as const, label: 'Auth', icon: REASON_META.auth_failed.icon, count: unavailableSummary.value.auth_failed },
  { value: 'never_reported' as const, label: 'New', icon: REASON_META.never_reported.icon, count: unavailableSummary.value.never_reported }
])

const filteredUnavailable = computed(() => {
  const term = unavailableFilter.value.trim().toLowerCase()
  const reason = reasonFilter.value

  return unavailableRows.value.filter((row) => {
    if (reason !== 'all' && row.reason !== reason) return false
    if (!term) return true
    const hay = [row.eqp_id, row.eqp_ip, row.fab_name, row.eqp_model_cd, row.error_code, row.reason]
    return hay.some(v => v.toLowerCase().includes(term))
  })
})

const resetUnavailableFilters = () => {
  unavailableFilter.value = ''
  reasonFilter.value = 'all'
}

const formatRelative = (iso: string) => {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (!Number.isFinite(then)) return iso
  // Anchor to the same mock "now" the backend uses (2026-04-26 12:00 UTC) so the
  // demo stays stable across reloads. In Phase 2/3 swap this to Date.now().
  const now = Date.UTC(2026, 3, 26, 12, 0, 0)
  const deltaMin = Math.max(0, Math.round((now - then) / 60000))
  if (deltaMin < 60) return `${deltaMin}m ago`
  const deltaH = Math.round(deltaMin / 60)
  if (deltaH < 48) return `${deltaH}h ago`
  const deltaD = Math.round(deltaH / 24)
  if (deltaD < 30) return `${deltaD}d ago`
  const deltaW = Math.round(deltaD / 7)
  return `${deltaW}w ago`
}

const unavailableTableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40',
    td: 'py-1.5 px-3 text-[12.5px] whitespace-nowrap overflow-hidden text-ellipsis',
    th: 'py-2 px-3 text-[11px] font-medium text-zinc-500 bg-transparent'
  }
}

const unavailableColumns: TableColumn<UnavailableRow>[] = [
  { accessorKey: 'reason', header: 'Reason', size: 150 },
  { accessorKey: 'eqp_id', header: 'Equipment ID', size: 130 },
  { accessorKey: 'fab_name', header: 'Fab', size: 64 },
  { accessorKey: 'eqp_model_cd', header: 'Model', size: 130 },
  { accessorKey: 'eqp_ip', header: 'IP Address', size: 140 },
  { accessorKey: 'error_code', header: 'Error Code', size: 130 },
  { accessorKey: 'last_success', header: 'Last Success', size: 110 },
  { accessorKey: 'last_attempt', header: 'Last Probe', size: 100 }
]
</script>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}

/* Diagnostic surface: muted muted base + 135deg "void" stripes signal that this
   card is auxiliary / missing-data, not primary inventory. Dashed border carries
   the same "incomplete" semantic as the stripes. */
.diagnostic-surface {
  position: relative;
  border: 1px dashed var(--sk-border);
  background-color: var(--sk-muted-surface);
  background-image: repeating-linear-gradient(
    135deg,
    transparent 0,
    transparent 14px,
    var(--sk-border-soft) 14px,
    var(--sk-border-soft) 15px
  );
  box-shadow:
    0 1px 0 rgba(0, 0, 0, 0.02),
    0 8px 22px -18px rgba(0, 0, 0, 0.18);
}

.dark .diagnostic-surface {
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.02),
    0 8px 22px -18px rgba(0, 0, 0, 0.6);
}

.diagnostic-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: oklch(0.78 0.12 70);
  box-shadow: 0 0 0 3px oklch(0.78 0.12 70 / 0.15);
}

.reason-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.reason-pill--amber {
  background: oklch(0.96 0.05 80);
  color: oklch(0.40 0.10 60);
  box-shadow: inset 0 0 0 1px oklch(0.85 0.07 75);
}
.dark .reason-pill--amber {
  background: oklch(0.30 0.06 65);
  color: oklch(0.85 0.10 80);
  box-shadow: inset 0 0 0 1px oklch(0.45 0.08 70);
}

.reason-pill--orange {
  background: oklch(0.95 0.06 50);
  color: oklch(0.42 0.13 40);
  box-shadow: inset 0 0 0 1px oklch(0.82 0.10 45);
}
.dark .reason-pill--orange {
  background: oklch(0.30 0.07 45);
  color: oklch(0.82 0.12 50);
  box-shadow: inset 0 0 0 1px oklch(0.50 0.10 45);
}

.reason-pill--rose {
  background: oklch(0.95 0.04 20);
  color: oklch(0.40 0.13 22);
  box-shadow: inset 0 0 0 1px oklch(0.82 0.09 22);
}
.dark .reason-pill--rose {
  background: oklch(0.28 0.06 22);
  color: oklch(0.80 0.10 22);
  box-shadow: inset 0 0 0 1px oklch(0.46 0.10 22);
}

.reason-pill--dashed {
  background: transparent;
  color: oklch(0.50 0.012 70);
  border: 1px dashed oklch(0.74 0.012 70);
  padding: 1px 7px;
}
.dark .reason-pill--dashed {
  color: oklch(0.80 0.008 70);
  border-color: oklch(0.50 0.012 70);
}

.reason-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 9999px;
  font-size: 11px;
  font-weight: 500;
  background: transparent;
  color: var(--sk-ink-muted);
  border: 1px solid transparent;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
}

.reason-chip:hover {
  background: var(--sk-chip-bg);
  color: var(--sk-ink);
}

.reason-chip__count {
  font-variant-numeric: tabular-nums;
  font-size: 10px;
  font-weight: 600;
  padding: 0 5px;
  border-radius: 9999px;
  background: rgba(0, 0, 0, 0.05);
  color: var(--sk-ink-muted);
  margin-left: 2px;
}
.dark .reason-chip__count {
  background: rgba(255, 255, 255, 0.06);
}

.reason-chip--active {
  background: var(--sk-surface);
  color: var(--sk-ink);
  border-color: var(--sk-border);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

.reason-chip--active.reason-chip--unreachable {
  border-color: oklch(0.78 0.10 75 / 0.6);
}
.reason-chip--active.reason-chip--stale {
  border-color: oklch(0.74 0.12 45 / 0.6);
}
.reason-chip--active.reason-chip--auth_failed {
  border-color: oklch(0.74 0.12 22 / 0.6);
}
.reason-chip--active.reason-chip--never_reported {
  border-style: dashed;
}

.error-code {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 11px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--sk-chip-bg);
  color: var(--sk-chip-text);
  letter-spacing: 0.02em;
}

.never-pill {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  font-style: italic;
  color: oklch(0.55 0.012 70);
  padding: 1px 7px;
  border: 1px dashed oklch(0.74 0.012 70);
  border-radius: 9999px;
}
.dark .never-pill {
  color: oklch(0.74 0.008 70);
  border-color: oklch(0.45 0.012 70);
}

/* Lift the table above the diagonal stripe so rows stay legible. */
.diagnostic-surface :deep(table) {
  background: color-mix(in oklab, var(--sk-surface) 92%, transparent);
}
.dark .diagnostic-surface :deep(table) {
  background: color-mix(in oklab, var(--sk-surface) 88%, transparent);
}
</style>
