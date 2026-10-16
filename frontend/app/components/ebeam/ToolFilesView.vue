<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="eyebrow"
      title="장비 파일"
      :subtitle="target ? target.eqpId : undefined"
    />

    <AppLoadingState
      v-if="accessStatus === 'pending'"
      title="권한을 확인하는 중입니다."
    />
    <AppEmptyState
      v-else-if="access?.verdict !== 'granted'"
      icon="i-lucide-lock"
      title="장비 파일에 접근할 권한이 없습니다."
      description="장비 파일 탐색은 승인된 사용자만 쓸 수 있습니다."
    />

    <UCard
      v-else
      class="dashboard-surface"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center gap-2">
          <USelectMenu
            v-model="selectedEqp"
            class="w-[14rem]"
            size="xs"
            color="neutral"
            variant="subtle"
            :items="toolOptions"
            value-key="value"
            placeholder="장비 선택"
            aria-label="장비 선택"
          />
          <nav
            v-if="listing"
            class="flex flex-wrap items-center gap-1 sk-value-num text-sm"
            aria-label="경로"
          >
            <template
              v-for="(crumb, index) in listing.crumbs"
              :key="crumb.path"
            >
              <UIcon
                v-if="index > 0"
                name="i-lucide-chevron-right"
                class="size-3.5 text-(--sk-ink-muted)"
              />
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                :disabled="crumb.path === listing.path"
                @click="openPath(crumb.path)"
              >
                {{ crumb.name }}
              </UButton>
            </template>
          </nav>
          <UBadge
            v-if="listing"
            class="ml-auto"
            color="neutral"
            variant="subtle"
          >
            {{ visibleEntries.length }} / {{ listing.entries.length }}
          </UBadge>
        </div>
      </template>

      <div class="px-4 py-2.5 flex items-center gap-2 border-b border-(--sk-border)">
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-arrow-up"
          :disabled="!listing?.parent"
          @click="listing?.parent && openPath(listing.parent)"
        >
          상위 폴더
        </UButton>
        <UInput
          v-model="nameFilter"
          class="flex-1 min-w-[14rem]"
          size="xs"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="이 폴더에서 파일 이름 검색"
        />
      </div>

      <AppEmptyState
        v-if="!target"
        icon="i-lucide-server"
        title="장비를 선택하세요."
        description="위 장비 선택에서 장비를 고르면 그 장비의 로그인 폴더가 열립니다."
      />
      <AppLoadingState
        v-else-if="listingStatus === 'pending'"
        title="파일 목록을 불러오는 중입니다."
      />
      <div
        v-else-if="listingError"
        class="space-y-2 p-4 text-center"
      >
        <AppEmptyState
          icon="i-lucide-circle-alert"
          :title="toolFilesErrorMessage(toolFilesErrorCode(listingError))"
        />
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-refresh-cw"
          @click="refreshListing()"
        >
          다시 시도
        </UButton>
      </div>
      <UTable
        v-else-if="listing"
        v-model:sorting="sorting"
        class="max-h-[40rem]"
        :columns="columns"
        :data="visibleEntries"
        :sorting-options="MANUAL_SORTING_OPTIONS"
        empty="이 폴더에 표시할 항목이 없습니다."
        sticky="header"
        @select="onRowSelect"
      >
        <template
          v-for="head in SORTABLE_HEADERS"
          :key="head.id"
          #[`${head.id}-header`]="{ column }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
            :trailing-icon="getSortIcon(column.getIsSorted())"
            :aria-sort="ariaSort(column.getIsSorted())"
            @click="column.toggleSorting(column.getIsSorted() === 'asc')"
          >
            {{ head.label }}
          </UButton>
        </template>

        <template #name-cell="{ row }">
          <span class="flex items-center gap-2 sk-value-num">
            <UIcon
              :name="row.original.is_dir ? 'i-lucide-folder' : 'i-lucide-file'"
              class="size-4 shrink-0 text-(--sk-ink-muted)"
            />
            <button
              v-if="row.original.is_dir"
              type="button"
              class="text-left hover:underline"
              @click="openPath(row.original.path)"
            >
              {{ row.original.name }}
            </button>
            <span v-else>{{ row.original.name }}</span>
          </span>
        </template>
        <template #size-cell="{ row }">
          <span class="sk-value-num block text-right">{{ formatFileSize(row.original.size) }}</span>
        </template>
        <template #modified-cell="{ row }">
          <span class="sk-value-num">{{ formatDateTimeLocal(row.original.modified) }}</span>
        </template>
        <template #actions-cell="{ row }">
          <UTooltip
            v-if="!row.original.is_dir"
            :text="tooLarge(row.original) ? '다운로드 상한보다 커서 받을 수 없습니다.' : 'PC로 다운로드'"
          >
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-download"
              :aria-label="`${row.original.name} 다운로드`"
              :loading="downloading === row.original.path"
              :disabled="tooLarge(row.original)"
              :class="tooLarge(row.original) ? 'cursor-not-allowed' : undefined"
              @click="download(row.original)"
            />
          </UTooltip>
        </template>
      </UTable>
    </UCard>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { ToolType } from '~/utils/toolType'
import { classifyToolType } from '~/utils/toolType'
import { formatDateTimeLocal } from '~/utils/dateTime'
import { MANUAL_SORTING_OPTIONS, getSortIcon } from '~/utils/tableSorting'
import { normalizeFab } from '~/utils/fab'
import {
  filterToolFileEntries,
  formatFileSize,
  sortToolFileEntries,
  toolFilesErrorMessage,
  type ToolFileEntry,
  type ToolFileSortKey
} from '~/utils/toolFiles'

const props = defineProps<{
  toolType: ToolType
  toolLabel: string
  fab: string
}>()

const route = useRoute()
const router = useRouter()
const toast = useToast()

const eyebrow = computed(() => `${props.toolLabel} · ${props.fab}`)

const { data: access, status: accessStatus } = useToolFilesAccess(props.toolType)

const { data: semRows } = useSemList()
const toolOptions = computed(() =>
  (semRows.value ?? [])
    .filter(row => classifyToolType(row.eqp_model_cd) === props.toolType && normalizeFab(row.fab_name) === normalizeFab(props.fab))
    .map(row => ({ label: row.eqp_id, value: row.eqp_id }))
    .sort((a, b) => a.label.localeCompare(b.label))
)

const queryString = (key: string) => {
  const value = route.query[key]
  return typeof value === 'string' && value ? value : undefined
}

const selectedEqp = computed({
  get: () => queryString('eqp'),
  set: (eqp) => { router.replace({ query: { eqp } }) }
})
const currentPath = computed(() => queryString('path'))

const target = computed(() =>
  selectedEqp.value ? { toolType: props.toolType, fab: props.fab, eqpId: selectedEqp.value } : null
)

const {
  data: listing,
  status: listingStatus,
  error: listingError,
  refresh: refreshListing
} = useToolFilesListing(target, currentPath)

const openPath = (path: string) => {
  nameFilter.value = ''
  router.push({ query: { ...route.query, path } })
}

const nameFilter = ref('')
const sorting = ref<SortingState>([{ id: 'name', desc: false }])

const visibleEntries = computed(() => {
  const rows = filterToolFileEntries(listing.value?.entries ?? [], nameFilter.value)
  const sort = sorting.value[0]
  return sort ? sortToolFileEntries(rows, sort.id as ToolFileSortKey, sort.desc ? 'desc' : 'asc') : rows
})

const SORTABLE_HEADERS = [
  { id: 'name', label: '이름' },
  { id: 'size', label: '크기' },
  { id: 'modified', label: '수정 시각' }
] as const

const columns: TableColumn<ToolFileEntry>[] = [
  { accessorKey: 'name', header: '이름' },
  { accessorKey: 'size', header: '크기', meta: { class: { th: 'text-right w-[8rem]', td: 'w-[8rem]' } } },
  { accessorKey: 'modified', header: '수정 시각', meta: { class: { th: 'w-[11rem]', td: 'w-[11rem]' } } },
  { id: 'actions', header: '', enableSorting: false, meta: { class: { th: 'w-[3rem]', td: 'w-[3rem]' } } }
]

const ariaSort = (direction: false | 'asc' | 'desc') =>
  direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none'

const onRowSelect = (_event: Event, row: TableRow<ToolFileEntry>) => {
  if (row.original.is_dir) openPath(row.original.path)
}

const tooLarge = (entry: ToolFileEntry) =>
  !!listing.value && entry.size !== null && entry.size > listing.value.max_bytes

const downloading = ref<string | null>(null)
const download = async (entry: ToolFileEntry) => {
  if (!target.value) return
  downloading.value = entry.path
  try {
    await downloadToolFile(target.value, entry.path, entry.name)
  } catch (error) {
    toast.add({ title: toolFilesErrorMessage(toolFilesErrorCode(error)), color: 'error' })
  } finally {
    downloading.value = null
  }
}
</script>
