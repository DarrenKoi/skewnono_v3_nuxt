<template>
  <div class="flex flex-col gap-3 h-full min-h-0 p-4">
    <UCard
      class="dashboard-surface flex flex-col flex-1 min-h-0"
      :ui="{ body: 'p-0 sm:p-0 flex flex-1 flex-col min-h-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <AppBackButton to="/" />
            <span
              class="h-6 w-px bg-(--sk-border-soft)"
              aria-hidden="true"
            />
            <h2 class="sk-heading">
              미연결 장비
            </h2>
            <UBadge
              v-if="status === 'success'"
              color="neutral"
              variant="subtle"
            >
              조회됨 {{ rows.length }} 대
            </UBadge>
          </div>
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-rotate-ccw"
            label="새로고침"
            :loading="status === 'pending'"
            @click="load"
          />
        </div>
      </template>

      <AppLoadingState
        v-if="status === 'pending'"
        title="전사 장비 명부를 불러오는 중입니다."
        description="장비 수에 따라 시간이 걸릴 수 있습니다."
      />

      <AppStatusMessage
        v-else-if="status === 'error'"
        v-bind="statusMessages.error"
      />

      <AppStatusMessage
        v-else-if="status === 'success' && rows.length === 0"
        v-bind="statusMessages.empty"
      />

      <div
        v-else-if="status === 'success'"
        class="flex flex-col flex-1 min-h-0"
      >
        <!-- Tool-type filter. Scopes the matrix AND the IP list: an IT request
             is filed per tool type, not as one mixed list. -->
        <div class="flex flex-wrap items-center gap-2 border-b border-(--sk-border) bg-(--sk-brand-soft) px-4 py-3">
          <div
            class="flex flex-wrap items-center gap-1.5"
            role="group"
            aria-label="장비 유형 필터"
          >
            <SkChip
              v-for="chip in groupChips"
              :key="chip.value"
              size="sm"
              :label="chip.label"
              :count="chip.count"
              :active="chip.value === activeGroup"
              @click="selectGroup(chip.value)"
            />
          </div>

          <div class="flex-1" />

          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-clipboard"
            label="IP 목록 복사"
            :disabled="visibleRows.length === 0"
            @click="copyIpList"
          />
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-download"
            label="CSV 다운로드"
            :disabled="visibleRows.length === 0"
            @click="downloadPendingCsv"
          />
        </div>

        <div class="flex-1 min-h-0 overflow-auto">
          <!-- Matrix -->
          <table class="min-w-full w-max border-separate border-spacing-0 text-left">
            <caption class="sr-only">
              Fab별 미연결 장비 모델 수
            </caption>
            <thead>
              <tr>
                <th
                  scope="col"
                  class="sticky left-0 top-0 z-30 border-b border-r border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 sk-label"
                >
                  Fab
                </th>
                <th
                  v-for="model in matrix.models"
                  :key="model"
                  scope="col"
                  class="sticky top-0 z-20 whitespace-nowrap border-b border-r border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 text-center sk-label"
                >
                  {{ model }}
                </th>
                <th
                  scope="col"
                  class="sticky right-0 top-0 z-30 border-b border-l border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 text-center sk-label"
                >
                  합계
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(fab, fabAt) in matrix.fabs"
                :key="fab"
                class="group transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
              >
                <th
                  scope="row"
                  class="sticky left-0 z-10 whitespace-nowrap border-b border-r border-(--sk-border-soft) bg-(--sk-surface) px-3 py-1.5 text-left group-hover:bg-zinc-50 dark:group-hover:bg-zinc-800/50 sk-value"
                >
                  {{ fab }}
                </th>
                <td
                  v-for="(model, modelAt) in matrix.models"
                  :key="model"
                  class="border-b border-r border-(--sk-border-soft) px-3 py-1.5 text-center"
                >
                  <!-- Zero renders as · so occupied cells carry the eye. -->
                  <button
                    v-if="cellCount(fabAt, modelAt)"
                    type="button"
                    :aria-pressed="isSelectedCell(fab, model)"
                    :aria-label="`${fab} ${model} 장비 ${cellCount(fabAt, modelAt)}대 보기`"
                    class="inline-flex min-h-7 min-w-8 items-center justify-center rounded-[var(--sk-r-sidebar)] border px-2 py-1 transition-colors sk-value-num"
                    :class="isSelectedCell(fab, model)
                      ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
                      : 'border-(--sk-border) bg-(--sk-muted-surface) text-(--sk-ink) hover:bg-(--sk-accent-soft)'"
                    @click="selectCell(fab, model)"
                  >
                    {{ cellCount(fabAt, modelAt) }}
                  </button>
                  <span
                    v-else
                    class="text-(--sk-ink-subtle) sk-label"
                  >·</span>
                </td>
                <td class="sticky right-0 z-10 border-b border-l border-(--sk-border-soft) bg-(--sk-surface) px-3 py-1.5 text-center group-hover:bg-zinc-50 dark:group-hover:bg-zinc-800/50 sk-value-num">
                  {{ matrix.fabTotals[fabAt] }}
                </td>
              </tr>
            </tbody>
            <tfoot>
              <tr class="bg-(--sk-muted-surface)">
                <th
                  scope="row"
                  class="sticky left-0 z-10 border-r border-t border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 text-left sk-label"
                >
                  합계
                </th>
                <td
                  v-for="(model, modelAt) in matrix.models"
                  :key="model"
                  class="border-r border-t border-(--sk-border-soft) px-3 py-2 text-center sk-value-num"
                >
                  {{ matrix.modelTotals[modelAt] }}
                </td>
                <td class="sticky right-0 z-10 border-l border-t border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-2 text-center sk-value-num">
                  {{ matrix.total }}
                </td>
              </tr>
            </tfoot>
          </table>

          <!-- Drill-down -->
          <div
            v-if="selectedCell"
            class="m-3 overflow-hidden rounded-[var(--sk-r-card)] border border-(--sk-border) bg-(--sk-muted-surface)"
          >
            <div class="flex items-center justify-between gap-3 border-b border-(--sk-border-soft) px-3 py-2.5">
              <div class="flex items-center gap-2">
                <h3 class="sk-title">
                  {{ selectedCell.fab }} / {{ selectedCell.model }}
                </h3>
                <UBadge
                  color="neutral"
                  variant="subtle"
                >
                  {{ drilldownRows.length }}대
                </UBadge>
              </div>
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                icon="i-lucide-x"
                aria-label="드릴다운 닫기"
                @click="selectedCell = null"
              />
            </div>
            <UTable
              class="bg-(--sk-surface)"
              :columns="drilldownColumns"
              :data="drilldownRows"
              :meta="drilldownTableMeta"
              :ui="{
                root: 'w-full',
                base: 'min-w-0 w-full',
                td: 'px-3 py-1.5 sk-value',
                th: 'px-3 py-2 sk-label'
              }"
            >
              <template #eqp_id-cell="{ row }">
                <span class="sk-value-num">{{ row.original.eqp_id }}</span>
              </template>
              <template #eqp_ip-cell="{ row }">
                <span class="sk-value-num">{{ row.original.eqp_ip }}</span>
              </template>
              <template #vendor_nm-cell="{ row }">
                <span class="sk-value capitalize">{{ row.original.vendor_nm.toLowerCase() }}</span>
              </template>
              <template #updt_dt-cell="{ row }">
                <span class="sk-value-num">
                  {{ arrivalDate(row.original.updt_dt) }}
                </span>
              </template>
            </UTable>
          </div>
        </div>
      </div>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { PendingToolGroup, PendingToolRow } from '~/utils/pendingToolMatrix'
import {
  buildPendingToolMatrix,
  cellRows,
  countByGroup,
  filterActionablePendingTools,
  filterByGroup,
  IP_LIST_SEPARATOR,
  sortByArrivalDesc,
  uniqueIps,
  UNCLASSIFIED
} from '~/utils/pendingToolMatrix'
import { copyTextToClipboard, downloadCsv } from '~/utils/csvDownload'
import { todayStamp } from '~/utils/dateTime'

const { data, status, error, execute } = usePendingTools()
const toast = useToast()

const rows = computed<PendingToolRow[]>(() =>
  filterActionablePendingTools(data.value ?? [])
)

interface StatusMessageContent {
  icon: string
  iconClass: string
  title: string
  description?: string
}

const statusMessages = computed<Record<'error' | 'empty', StatusMessageContent>>(() => ({
  error: {
    icon: 'i-lucide-triangle-alert',
    iconClass: 'text-(--sk-bad)',
    title: '명부를 불러오지 못했습니다.',
    description: error.value?.message
  },
  empty: {
    icon: 'i-lucide-check',
    iconClass: 'text-(--sk-ok)',
    title: '명부의 모든 장비가 연결되어 있습니다.'
  }
}))

const activeGroup = ref<PendingToolGroup | 'all'>('all')
const selectedCell = ref<{ fab: string, model: string } | null>(null)

const load = async () => {
  selectedCell.value = null
  await execute()
}

const GROUP_LABELS: Array<{ value: PendingToolGroup, label: string }> = [
  { value: 'cd-sem', label: 'CD-SEM' },
  { value: 'hv-sem', label: 'HV-SEM' },
  { value: 'veritysem', label: 'VeritySEM' },
  { value: 'provision', label: 'Provision' },
  { value: UNCLASSIFIED, label: '미분류' }
]

// Only groups that actually have tools get a chip, so 미분류 stays invisible
// until an unrecognized model shows up — at which point it is the signal.
const groupChips = computed(() => {
  const counts = countByGroup(rows.value)
  return [
    { value: 'all' as const, label: '전체', count: rows.value.length },
    ...GROUP_LABELS
      .filter(group => counts.has(group.value))
      .map(group => ({ ...group, count: counts.get(group.value) ?? 0 }))
  ]
})

const visibleRows = computed(() => filterByGroup(rows.value, activeGroup.value))
const matrix = computed(() => buildPendingToolMatrix(visibleRows.value))

// One lookup per cell instead of re-indexing matrix.counts in v-if, :label
// and :aria-label separately.
const cellCount = (fabAt: number, modelAt: number) => matrix.value.counts[fabAt]?.[modelAt]

const isSelectedCell = (fab: string, model: string): boolean =>
  selectedCell.value?.fab === fab && selectedCell.value.model === model

const selectGroup = (group: PendingToolGroup | 'all') => {
  activeGroup.value = group
  // The previous cell may not exist under the new filter.
  selectedCell.value = null
}

const selectCell = (fab: string, model: string) => {
  selectedCell.value = { fab, model }
}

const drilldownRows = computed(() => {
  const cell = selectedCell.value
  if (!cell) return []
  return sortByArrivalDesc(cellRows(visibleRows.value, cell.fab, cell.model))
})

const arrivalDate = (updtDt: string) => updtDt.slice(0, 10)

// Same hover/typography convention as ToolInventoryView.vue and
// PpidUnavailablePanel.vue's tableMeta — the drill-down needs no sorting, so
// only the `class` half of that pattern applies here.
const drilldownTableMeta = {
  class: {
    tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50'
  }
}

const drilldownColumnConfigs: Array<{ id: keyof PendingToolRow, header: string }> = [
  { id: 'eqp_id', header: 'Equipment ID' },
  { id: 'eqp_ip', header: 'IP Address' },
  { id: 'vendor_nm', header: 'Vendor' },
  { id: 'updt_dt', header: '반입일' }
]
const drilldownColumns: TableColumn<PendingToolRow>[] = drilldownColumnConfigs.map(
  ({ id, header }) => ({ accessorKey: id, header })
)

const copyIpList = async () => {
  // Count from the array, never by re-splitting the joined text: that coupling
  // meant the separator and the count had to be kept in sync by hand.
  const ips = uniqueIps(visibleRows.value)
  const ok = await copyTextToClipboard(ips.join(IP_LIST_SEPARATOR))
  toast.add(
    ok
      ? {
          title: `IP ${ips.length}건이 복사되었습니다`,
          icon: 'i-lucide-check',
          color: 'success'
        }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

const CSV_COLUMNS: Array<{ id: keyof PendingToolRow, header: string }> = [
  { id: 'fac_id', header: 'Fac' },
  { id: 'fab_name', header: 'Fab' },
  { id: 'eqp_id', header: 'Equipment ID' },
  { id: 'eqp_model_cd', header: 'Model' },
  { id: 'vendor_nm', header: 'Vendor' },
  { id: 'eqp_ip', header: 'IP Address' },
  { id: 'eqp_grp_id', header: 'Group' },
  { id: 'updt_dt', header: '반입일' }
]

const downloadPendingCsv = () => {
  downloadCsv(
    `pending-tools-${activeGroup.value}-${todayStamp()}.csv`,
    CSV_COLUMNS.map(column => column.header),
    visibleRows.value.map(row => CSV_COLUMNS.map(column => row[column.id]))
  )
}
</script>
