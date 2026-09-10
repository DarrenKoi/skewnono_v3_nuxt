<template>
  <UCard
    class="dashboard-surface"
    :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
  >
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 class="sk-heading">
            PPID 미접속 장비
          </h2>
          <p class="mt-0.5 sk-meta">
            기준일 <span class="sk-value-num">{{ latestDate || '-' }}</span>
          </p>
        </div>
        <UBadge
          color="neutral"
          variant="subtle"
        >
          {{ filteredRows.length }} / {{ rows.length }}
        </UBadge>
      </div>
    </template>

    <div class="flex flex-wrap items-center gap-2 border-b border-(--sk-border) px-4 py-2.5">
      <UInput
        v-model="search"
        class="min-w-[14rem] flex-1"
        size="xs"
        icon="i-lucide-search"
        color="neutral"
        variant="subtle"
        placeholder="미접속 장비 검색"
      />
      <UButton
        size="xs"
        color="neutral"
        variant="outline"
        icon="i-lucide-rotate-ccw"
        label="초기화"
        :disabled="!hasActiveControls"
        @click="reset"
      />
    </div>

    <AppLoadingState
      v-if="pending"
      variant="inline"
      title="PPID 미접속 정보를 불러오는 중입니다."
    />
    <div
      v-else-if="error"
      class="px-4 py-10 text-center text-sm text-rose-600 dark:text-rose-400"
    >
      PPID 미접속 목록을 불러오지 못했습니다.
    </div>
    <div
      v-else-if="rows.length === 0"
      class="px-4 py-12 text-center"
    >
      <UIcon
        name="i-lucide-circle-check-big"
        class="mx-auto mb-2 h-6 w-6 text-(--sk-ok)"
      />
      <p class="text-sm font-medium text-(--sk-ink)">
        기준일에 PPID 접속에 실패한 장비가 없습니다.
      </p>
      <p class="mt-0.5 text-xs leading-relaxed text-(--sk-ink-muted)">
        {{ fab }} {{ toolLabel }} · {{ latestDate || '최신 기준일' }}
      </p>
    </div>
    <div
      v-else-if="filteredRows.length === 0"
      class="px-4 py-10 text-center"
    >
      <UIcon
        name="i-lucide-filter-x"
        class="mx-auto mb-2 h-6 w-6 text-(--sk-ink-muted)"
      />
      <p class="text-sm font-medium text-(--sk-ink)">
        검색 조건에 맞는 장비가 없습니다.
      </p>
      <p class="mt-0.5 text-xs leading-relaxed text-(--sk-ink-muted)">
        검색 조건으로 {{ rows.length }}대가 숨겨져 있습니다.
      </p>
      <UButton
        class="mt-3"
        size="xs"
        color="neutral"
        variant="outline"
        icon="i-lucide-rotate-ccw"
        label="검색 초기화"
        @click="reset"
      />
    </div>
    <UTable
      v-else
      v-model:sorting="sorting"
      class="max-h-[22rem]"
      :columns="columns"
      :data="filteredRows"
      :meta="tableMeta"
      :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false, manualSorting: true }"
      sticky="header"
    >
      <template
        v-for="head in sortableHeaders"
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

      <template #fab_name-cell="{ row }">
        <span class="sk-value">{{ row.original.fab_name || '—' }}</span>
      </template>
      <template #eqp_id-cell="{ row }">
        <span class="sk-value-num">{{ row.original.eqp_id || '—' }}</span>
      </template>
      <template #eqp_model_cd-cell="{ row }">
        <span class="sk-value-num">{{ row.original.eqp_model_cd || '—' }}</span>
      </template>
      <template #eqp_ip-cell="{ row }">
        <div class="flex items-center gap-1">
          <span class="sk-value-num">{{ row.original.eqp_ip }}</span>
          <UTooltip text="IP 복사">
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-copy"
              :aria-label="`${row.original.eqp_ip} 복사`"
              @click="copyIp(row.original.eqp_ip)"
            />
          </UTooltip>
        </div>
      </template>
      <template #missing_days_streak-cell="{ row }">
        <span
          class="inline-flex min-w-[2rem] items-center justify-center rounded-[var(--sk-r-chip)] px-1.5 py-0.5 font-semibold tabular-nums"
          :class="row.original.missing_days_streak >= 7
            ? 'bg-(--sk-bad-soft) text-(--sk-bad)'
            : 'bg-(--sk-muted-surface) text-(--sk-ink-muted)'"
        >
          {{ row.original.missing_days_streak }}d
        </span>
      </template>
    </UTable>
  </UCard>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { PpidUnavailableRow } from '~/composables/useStorageApi'
import { copyTextToClipboard } from '~/utils/tableExport'

const props = defineProps<{
  rows: readonly PpidUnavailableRow[]
  latestDate: string
  pending: boolean
  error: unknown
  fab: string
  toolLabel: string
}>()

const search = ref('')
const defaultSort = { id: 'missing_days_streak', desc: true }
const sorting = ref<SortingState>([defaultSort])
const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' })

const compareRows = (left: PpidUnavailableRow, right: PpidUnavailableRow, key: keyof PpidUnavailableRow) => {
  const leftValue = left[key]
  const rightValue = right[key]
  if (typeof leftValue === 'number' && typeof rightValue === 'number') return leftValue - rightValue
  return collator.compare(String(leftValue), String(rightValue))
}

const filteredRows = computed(() => {
  const term = search.value.trim().toLowerCase()
  const matched = props.rows.filter((row) => {
    if (!term) return true
    return [row.eqp_id, row.eqp_ip, row.fab_name, row.eqp_model_cd]
      .some(value => value.toLowerCase().includes(term))
  })
  const currentSort = sorting.value[0]
  if (!currentSort) return matched
  const key = currentSort.id as keyof PpidUnavailableRow
  const direction = currentSort.desc ? -1 : 1
  return [...matched].sort((left, right) => {
    const result = compareRows(left, right, key)
    return result !== 0 ? result * direction : collator.compare(left.eqp_ip, right.eqp_ip)
  })
})

const hasActiveControls = computed(() => {
  const currentSort = sorting.value[0]
  return search.value.length > 0
    || currentSort?.id !== defaultSort.id
    || currentSort?.desc !== defaultSort.desc
})

const reset = () => {
  search.value = ''
  sorting.value = [defaultSort]
}

const toast = useToast()

const copyIp = async (ip: string) => {
  const ok = await copyTextToClipboard(ip)
  toast.add(
    ok
      ? { title: 'IP가 복사되었습니다', description: ip, icon: 'i-lucide-check', color: 'success' }
      : { title: 'IP 복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

const tableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50/60 dark:hover:bg-zinc-800/40',
    td: 'py-1.5 px-3 whitespace-nowrap overflow-hidden text-ellipsis sk-value',
    th: 'py-2 px-3 sk-label'
  }
}

const columnConfigs: Array<{ id: keyof PpidUnavailableRow, header: string, size: number }> = [
  { id: 'missing_days_streak', header: 'Days Down', size: 88 },
  { id: 'fab_name', header: 'Fab', size: 64 },
  { id: 'eqp_id', header: 'Equipment ID', size: 130 },
  { id: 'eqp_model_cd', header: 'Model', size: 130 },
  { id: 'eqp_ip', header: 'IP Address', size: 168 }
]
const columns: TableColumn<PpidUnavailableRow>[] = columnConfigs.map(({ id, ...column }) => ({
  accessorKey: id,
  ...column
}))
const sortableHeaders = columnConfigs.map(column => ({ id: column.id, label: column.header }))

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}
</script>
