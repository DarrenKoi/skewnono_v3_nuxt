<template>
  <div class="mx-auto max-w-7xl space-y-4 px-4 py-6">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="flex items-center gap-2 text-2xl font-semibold text-zinc-950 dark:text-zinc-50">
          <UIcon
            name="i-lucide-file-search"
            class="text-sky-500"
          />
          Production Logs
        </h1>
        <p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          skewnono_logging
          <UBadge
            v-if="isDemoMode"
            class="ml-2"
            color="warning"
            variant="subtle"
            size="sm"
          >
            demo
          </UBadge>
        </p>
      </div>

      <div class="flex items-center gap-2">
        <span
          v-if="logs"
          class="text-xs text-zinc-500 tabular-nums"
        >
          {{ logs.total.toLocaleString() }} rows
        </span>
        <UButton
          :loading="pending"
          color="neutral"
          variant="outline"
          icon="i-lucide-refresh-cw"
          @click="refresh()"
        >
          Refresh
        </UButton>
      </div>
    </header>

    <section class="dashboard-surface rounded-lg border border-(--sk-border) p-3">
      <div class="grid grid-cols-1 gap-2 md:grid-cols-4 xl:grid-cols-6">
        <UInput
          v-model="draft.from"
          type="datetime-local"
          size="xs"
          color="neutral"
          variant="subtle"
        />
        <UInput
          v-model="draft.to"
          type="datetime-local"
          size="xs"
          color="neutral"
          variant="subtle"
        />
        <USelect
          v-model="draft.level"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="levelOptions"
        />
        <USelect
          v-model="draft.event"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="eventOptions"
        />
        <USelect
          v-model="draft.method"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="methodOptions"
        />
        <USelect
          :model-value="pageSize"
          size="xs"
          color="neutral"
          variant="subtle"
          :items="pageSizeOptions"
          @update:model-value="setPageSize"
        />
      </div>

      <div class="mt-2 grid grid-cols-1 gap-2 md:grid-cols-4 xl:grid-cols-6">
        <UInput
          v-model="draft.user_id"
          size="xs"
          icon="i-lucide-user"
          color="neutral"
          variant="subtle"
          placeholder="User"
        />
        <UInput
          v-model="draft.feature"
          size="xs"
          icon="i-lucide-box"
          color="neutral"
          variant="subtle"
          placeholder="Feature"
        />
        <UInput
          v-model="draft.status_min"
          size="xs"
          color="neutral"
          variant="subtle"
          placeholder="Status min"
        />
        <UInput
          v-model="draft.status_max"
          size="xs"
          color="neutral"
          variant="subtle"
          placeholder="Status max"
        />
        <UInput
          v-model="draft.path"
          size="xs"
          icon="i-lucide-route"
          color="neutral"
          variant="subtle"
          placeholder="Path"
        />
        <UInput
          v-model="draft.q"
          size="xs"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="Message / stack"
        />
      </div>

      <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
        <div class="text-xs text-zinc-500 tabular-nums">
          Page {{ currentPage }} / {{ pageCount }}
        </div>
        <div class="flex items-center gap-1.5">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            @click="resetFilters"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="solid"
            icon="i-lucide-search"
            @click="applyFilters"
          >
            Search
          </UButton>
        </div>
      </div>
    </section>

    <UAlert
      v-if="errorMessage"
      color="error"
      variant="soft"
      icon="i-lucide-triangle-alert"
      :title="errorMessage"
    />

    <section class="dashboard-surface overflow-hidden rounded-lg border border-(--sk-border)">
      <div
        v-if="pending"
        class="flex items-center justify-center gap-2 px-4 py-12 text-sm text-zinc-500"
      >
        <UIcon
          name="i-lucide-loader-circle"
          class="h-4 w-4 animate-spin"
        />
        Loading logs...
      </div>

      <div
        v-else-if="!rows.length"
        class="px-4 py-12 text-center text-sm text-zinc-500"
      >
        No logs matched the current filters.
      </div>

      <div
        v-else
        class="overflow-x-auto"
      >
        <table class="w-full min-w-[72rem] text-left text-xs">
          <thead class="border-b border-(--sk-border) text-[11px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th class="px-3 py-2">
                Time
              </th>
              <th class="px-3 py-2">
                Level
              </th>
              <th class="px-3 py-2">
                Event
              </th>
              <th class="px-3 py-2">
                User
              </th>
              <th class="px-3 py-2">
                Method
              </th>
              <th class="px-3 py-2">
                Path
              </th>
              <th class="px-3 py-2 text-right">
                Status
              </th>
              <th class="px-3 py-2 text-right">
                ms
              </th>
              <th class="px-3 py-2">
                Feature
              </th>
              <th class="px-3 py-2">
                Message
              </th>
            </tr>
          </thead>
          <tbody>
            <template
              v-for="row in rows"
              :key="row.id"
            >
              <tr
                class="cursor-pointer border-b border-(--sk-border) hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                @click="toggleRow(row.id)"
              >
                <td class="whitespace-nowrap px-3 py-2 font-mono tabular-nums text-zinc-500">
                  {{ formatTime(row.timestamp) }}
                </td>
                <td class="px-3 py-2">
                  <UBadge
                    :color="levelColor(row.level)"
                    variant="subtle"
                    size="sm"
                  >
                    {{ row.level || '-' }}
                  </UBadge>
                </td>
                <td class="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-zinc-600 dark:text-zinc-300">
                  {{ row.event || '-' }}
                </td>
                <td class="whitespace-nowrap px-3 py-2 font-mono text-[11px]">
                  {{ row.user_id || '-' }}
                </td>
                <td class="px-3 py-2 font-mono text-[11px]">
                  {{ row.method || '-' }}
                </td>
                <td class="max-w-[22rem] truncate px-3 py-2 font-mono text-[11px] text-zinc-600 dark:text-zinc-300">
                  {{ row.path || '-' }}
                </td>
                <td class="px-3 py-2 text-right font-mono tabular-nums">
                  {{ row.status ?? '-' }}
                </td>
                <td class="px-3 py-2 text-right font-mono tabular-nums">
                  {{ row.latency_ms ?? '-' }}
                </td>
                <td class="whitespace-nowrap px-3 py-2 font-mono text-[11px]">
                  {{ row.feature || '-' }}
                </td>
                <td class="max-w-[28rem] truncate px-3 py-2 text-zinc-600 dark:text-zinc-300">
                  {{ row.message || '-' }}
                </td>
              </tr>
              <tr
                v-if="expandedId === row.id"
                class="border-b border-(--sk-border) bg-zinc-50/80 dark:bg-zinc-950/60"
              >
                <td
                  colspan="10"
                  class="px-3 py-3"
                >
                  <div class="grid gap-3 lg:grid-cols-2">
                    <div>
                      <h3 class="mb-1 text-xs font-semibold text-zinc-700 dark:text-zinc-200">
                        Exception
                      </h3>
                      <pre class="max-h-80 overflow-auto rounded bg-zinc-950 p-3 text-[11px] text-zinc-100">{{ exceptionText(row) }}</pre>
                    </div>
                    <div>
                      <h3 class="mb-1 text-xs font-semibold text-zinc-700 dark:text-zinc-200">
                        Raw document
                      </h3>
                      <pre class="max-h-80 overflow-auto rounded bg-zinc-950 p-3 text-[11px] text-zinc-100">{{ rawText(row) }}</pre>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between border-t border-(--sk-border) px-3 py-2 text-xs text-zinc-500">
        <span class="tabular-nums">
          {{ rangeLabel }}
        </span>
        <div class="flex gap-1">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-chevron-left"
            :disabled="currentPage <= 1 || pending"
            @click="currentPage -= 1"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            trailing-icon="i-lucide-chevron-right"
            :disabled="currentPage >= pageCount || pending"
            @click="currentPage += 1"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  useAdminLogsApi,
  type AdminLogItem,
  type AdminLogQuery
} from '~/composables/useAdminLogsApi'

definePageMeta({ layout: 'hub' })
useHead({ title: 'Production Logs | SKEWNONO' })

type DraftFilters = {
  from: string
  to: string
  level: string
  event: string
  method: string
  user_id: string
  feature: string
  status_min: string
  status_max: string
  path: string
  q: string
}

const toDateTimeInput = (date: Date) => {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}T${hh}:${mi}`
}

const toIso = (value: string) => {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toISOString()
}

const ALL_SENTINEL = '__all__'

const makeDefaultFilters = (): DraftFilters => {
  const now = new Date()
  const from = new Date(now.getTime() - 24 * 60 * 60 * 1000)
  return {
    from: toDateTimeInput(from),
    to: toDateTimeInput(now),
    level: ALL_SENTINEL,
    event: ALL_SENTINEL,
    method: ALL_SENTINEL,
    user_id: '',
    feature: '',
    status_min: '',
    status_max: '',
    path: '',
    q: ''
  }
}

const { fetchLogs } = useAdminLogsApi()
const draft = reactive<DraftFilters>(makeDefaultFilters())
const applied = ref<DraftFilters>({ ...draft })
const currentPage = ref(1)
const pageSize = ref(50)
const expandedId = ref<string | null>(null)

// NuxtUI USelect rejects items with value=''; use ALL_SENTINEL for "no filter"
// and strip it before sending to the backend.
const levelOptions = [
  { label: 'All levels', value: ALL_SENTINEL },
  { label: 'Error', value: 'ERROR' },
  { label: 'Warning', value: 'WARNING' },
  { label: 'Info', value: 'INFO' }
]

const eventOptions = [
  { label: 'All events', value: ALL_SENTINEL },
  { label: 'Request', value: 'request' },
  { label: 'Exception', value: 'request_exception' }
]

const methodOptions = [
  { label: 'All methods', value: ALL_SENTINEL },
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' },
  { label: 'PATCH', value: 'PATCH' },
  { label: 'DELETE', value: 'DELETE' }
]

const fromAll = (value: string) => (value === ALL_SENTINEL ? '' : value)

const pageSizeOptions = [
  { label: '25 / page', value: 25 },
  { label: '50 / page', value: 50 },
  { label: '100 / page', value: 100 },
  { label: '200 / page', value: 200 }
]

const query = computed<AdminLogQuery>(() => ({
  from: toIso(applied.value.from),
  to: toIso(applied.value.to),
  level: fromAll(applied.value.level),
  event: fromAll(applied.value.event),
  method: fromAll(applied.value.method),
  user_id: applied.value.user_id,
  feature: applied.value.feature,
  status_min: applied.value.status_min,
  status_max: applied.value.status_max,
  path: applied.value.path,
  q: applied.value.q,
  page: currentPage.value,
  page_size: pageSize.value
}))

const {
  data: logs,
  pending,
  error,
  refresh
} = await useAsyncData(
  'admin-logs',
  () => fetchLogs(query.value),
  {
    watch: [query]
  }
)

const rows = computed<AdminLogItem[]>(() => logs.value?.items ?? [])
const isDemoMode = computed(() => logs.value?.filters?.demo_mode === true)
const pageCount = computed(() => {
  const total = logs.value?.total ?? 0
  const size = logs.value?.page_size ?? pageSize.value
  return Math.max(1, Math.ceil(total / size))
})

const errorMessage = computed(() => {
  if (!error.value) return ''
  return error.value.message || 'Failed to load logs.'
})

const rangeLabel = computed(() => {
  const total = logs.value?.total ?? 0
  if (!total) return '0 of 0'
  const size = logs.value?.page_size ?? pageSize.value
  const start = (currentPage.value - 1) * size + 1
  const end = Math.min(total, currentPage.value * size)
  return `${start.toLocaleString()}-${end.toLocaleString()} of ${total.toLocaleString()}`
})

const setPageSize = (value: string | number) => {
  const next = typeof value === 'number' ? value : Number.parseInt(value, 10)
  if (Number.isNaN(next) || next === pageSize.value) return
  currentPage.value = 1
  pageSize.value = next
}

const applyFilters = () => {
  currentPage.value = 1
  expandedId.value = null
  applied.value = { ...draft }
}

const resetFilters = () => {
  const defaults = makeDefaultFilters()
  Object.assign(draft, defaults)
  applied.value = { ...defaults }
  currentPage.value = 1
  expandedId.value = null
}

const toggleRow = (id: string) => {
  expandedId.value = expandedId.value === id ? null : id
}

const formatTime = (value: string | null) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ko-KR', { hour12: false })
}

const levelColor = (level: string | null): 'neutral' | 'info' | 'warning' | 'error' => {
  if (level === 'ERROR' || level === 'CRITICAL') return 'error'
  if (level === 'WARNING') return 'warning'
  if (level === 'INFO') return 'info'
  return 'neutral'
}

const exceptionText = (row: AdminLogItem) => {
  if (!row.exception) return 'No exception payload.'
  return row.exception.stack || row.exception.message || JSON.stringify(row.exception, null, 2)
}

const rawText = (row: AdminLogItem) => JSON.stringify(row.raw, null, 2)
</script>
