<template>
  <div class="flex flex-col gap-3 h-full min-h-0 p-4">
    <UCard
      class="dashboard-surface flex flex-col flex-1 min-h-0"
      :ui="{ body: 'p-0 sm:p-0 flex flex-1 flex-col min-h-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
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
            :icon="status === 'success' ? 'i-lucide-rotate-ccw' : 'i-lucide-search'"
            :label="status === 'success' ? '새로고침' : '조회'"
            :loading="status === 'pending'"
            @click="load"
          />
        </div>
      </template>

      <!-- Idle: nothing has been fetched, because this page never fetches on
           navigation. Say why, so the empty screen does not read as broken. -->
      <AppStatusMessage
        v-if="status === 'idle'"
        v-bind="statusMessages.idle"
      />

      <AppLoadingState
        v-else-if="status === 'pending'"
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
        <div class="px-4 py-2.5 flex flex-wrap items-center gap-2 border-b border-(--sk-border)">
          <UButton
            v-for="chip in groupChips"
            :key="chip.value"
            size="sm"
            :color="chip.value === activeGroup ? 'primary' : 'neutral'"
            :variant="chip.value === activeGroup ? 'solid' : 'subtle'"
            @click="selectGroup(chip.value)"
          >
            {{ chip.label }} {{ chip.count }}
          </UButton>

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
          <table class="w-full text-left">
            <thead class="sticky top-0 bg-(--sk-surface)">
              <tr>
                <th class="sk-label py-2 px-3">
                  Fab
                </th>
                <th
                  v-for="model in matrix.models"
                  :key="model"
                  class="sk-label py-2 px-3 text-right"
                >
                  {{ model }}
                </th>
                <th class="sk-label py-2 px-3 text-right">
                  합계
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(fab, fabAt) in matrix.fabs"
                :key="fab"
                class="transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
              >
                <td class="sk-value py-1.5 px-3">
                  {{ fab }}
                </td>
                <td
                  v-for="(model, modelAt) in matrix.models"
                  :key="model"
                  class="py-1.5 px-3 text-right"
                >
                  <!-- Zero renders as · so occupied cells carry the eye. -->
                  <UButton
                    v-if="cellCount(fabAt, modelAt)"
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    :label="String(cellCount(fabAt, modelAt))"
                    :aria-label="`${fab} ${model} 장비 ${cellCount(fabAt, modelAt)}대 보기`"
                    @click="selectCell(fab, model)"
                  />
                  <span
                    v-else
                    class="sk-label"
                  >·</span>
                </td>
                <td class="sk-value-num py-1.5 px-3 text-right">
                  {{ matrix.fabTotals[fabAt] }}
                </td>
              </tr>
            </tbody>
            <tfoot class="border-t border-(--sk-border)">
              <tr>
                <td class="sk-label py-2 px-3">
                  합계
                </td>
                <td
                  v-for="(model, modelAt) in matrix.models"
                  :key="model"
                  class="sk-value-num py-2 px-3 text-right"
                >
                  {{ matrix.modelTotals[modelAt] }}
                </td>
                <td class="sk-value-num py-2 px-3 text-right">
                  {{ matrix.total }}
                </td>
              </tr>
            </tfoot>
          </table>

          <!-- Drill-down -->
          <div
            v-if="selectedCell"
            class="border-t border-(--sk-border)"
          >
            <div class="px-4 py-2.5 flex items-center justify-between gap-3">
              <h3 class="sk-heading">
                {{ selectedCell.fab }} / {{ selectedCell.model }}
                <span class="sk-label">{{ drilldownRows.length }}대</span>
              </h3>
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
              :columns="drilldownColumns"
              :data="drilldownRows"
              :meta="drilldownTableMeta"
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
  filterByGroup,
  IP_LIST_SEPARATOR,
  sortByArrivalDesc,
  uniqueIps,
  UNCLASSIFIED
} from '~/utils/pendingToolMatrix'
import { copyTextToClipboard, downloadCsv } from '~/utils/csvDownload'

const { data, status, error, execute } = usePendingTools()
const toast = useToast()

const rows = computed<PendingToolRow[]>(() => data.value ?? [])

interface StatusMessageContent {
  icon: string
  iconClass: string
  title: string
  description?: string
}

// idle / error / success-empty share one shape (icon + title + optional
// description) — see AppStatusMessage.vue; only the content differs per state.
const statusMessages = computed<Record<'idle' | 'error' | 'empty', StatusMessageContent>>(() => ({
  idle: {
    icon: 'i-lucide-network',
    iconClass: 'text-(--sk-ink-muted)',
    title: '전사 장비 명부는 조회 시점에만 불러옵니다.',
    description: '조회를 누르면 방화벽 해제가 필요한 장비를 확인할 수 있습니다.'
  },
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
  { value: 'verity-sem', label: 'VeritySEM' },
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
    tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
    td: 'py-1.5 px-3 sk-value',
    th: 'py-2 px-3 sk-label'
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
    `pending-tools-${activeGroup.value}-${new Date().toISOString().slice(0, 10)}.csv`,
    CSV_COLUMNS.map(column => column.header),
    visibleRows.value.map(row => CSV_COLUMNS.map(column => row[column.id]))
  )
}
</script>
