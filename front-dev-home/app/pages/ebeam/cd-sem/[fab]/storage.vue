<template>
  <div class="space-y-4">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
          CD-SEM
        </p>
        <h1 class="text-2xl font-bold text-zinc-950 dark:text-zinc-50">
          Storage - {{ fabId }}
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
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { Fab } from '~/stores/navigation'
import type { StorageRow } from '~/composables/useStorageApi'

const route = useRoute()
const { setToolType, setFab } = useNavigation()
const { fetchByUrlFab } = useStorageApi()

const fabId = computed(() => String(route.params.fab ?? '').toUpperCase())
const subtitle = computed(() => `Storage usage for ${fabId.value} CD-SEM tools.`)

setToolType('cd-sem')
setFab(fabId.value as Fab)

watch(fabId, (next) => {
  setFab(next as Fab)
})

const { data, pending, error } = await useAsyncData(
  () => `storage:${fabId.value}`,
  () => fetchByUrlFab(fabId.value),
  { watch: [fabId], default: () => [] as StorageRow[] }
)

const rows = computed(() => data.value ?? [])

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
  { label: 'Last Reported (Newest)', value: 'storage_mt:desc' }
]

const filteredRows = computed(() => {
  const term = globalFilter.value.trim().toLowerCase()
  const usage = usageFilter.value

  const matched = rows.value.filter((row) => {
    if (term) {
      const hit = [row.eqp_id, row.eqp_ip, row.fab_name, row.eqp_model_cd, row.fac_id, row.total, row.used, row.percent]
        .some(value => value.toLowerCase().includes(term))
      if (!hit) return false
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
</script>

<style scoped>
.font-mono-ids :deep(td .font-mono) {
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}
</style>
