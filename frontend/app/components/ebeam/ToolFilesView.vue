<template>
  <div class="space-y-3">
    <EbeamMetaBar
      :eyebrow="eyebrow"
      title="장비 파일"
    >
      <template #leading>
        <AppBackButton
          :to="inventoryPath"
          label="장비 목록"
        />
      </template>
      <template #actions>
        <dl
          v-if="selectedEqp"
          class="flex flex-wrap items-center gap-x-5 gap-y-1 px-3 py-1"
        >
          <div
            v-for="fact in toolFacts"
            :key="fact.label"
          >
            <dt class="sk-label">
              {{ fact.label }}
            </dt>
            <dd class="sk-value-num">
              {{ fact.value }}
            </dd>
          </div>
          <UBadge
            v-if="connection"
            :color="connection.color"
            variant="subtle"
            :icon="connection.icon"
          >
            {{ connection.label }}
          </UBadge>
        </dl>
      </template>
    </EbeamMetaBar>

    <AppLoadingState
      v-if="accessStatus === 'pending'"
      title="권한을 확인하는 중입니다."
    />
    <div
      v-else-if="accessError"
      class="space-y-2 p-4 text-center"
    >
      <AppEmptyState
        icon="i-lucide-circle-alert"
        :title="toolFilesErrorMessage(toolFilesErrorCode(accessError))"
      />
      <UButton
        size="xs"
        color="neutral"
        variant="outline"
        icon="i-lucide-refresh-cw"
        @click="refreshAccess()"
      >
        다시 시도
      </UButton>
    </div>
    <AppEmptyState
      v-else-if="view === 'notice'"
      icon="i-lucide-lock"
      :title="refusal.title"
      :description="refusal.description"
    />

    <UCard
      v-else-if="view !== 'explorer'"
      class="dashboard-surface max-w-2xl"
    >
      <div class="space-y-3">
        <div class="flex items-start gap-3">
          <UIcon
            :name="view === 'pending' ? 'i-lucide-hourglass' : view === 'rejected' ? 'i-lucide-circle-x' : 'i-lucide-lock'"
            class="mt-0.5 size-5 shrink-0 text-(--sk-ink-muted)"
          />
          <div>
            <p class="sk-title">
              {{ refusal.title }}
            </p>
            <p class="mt-1 sk-meta">
              {{ refusal.description }}
            </p>
          </div>
        </div>

        <dl
          v-if="ownRequest"
          class="grid grid-cols-[5rem_1fr] gap-x-3 gap-y-1 rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3 py-2"
        >
          <dt class="sk-field-label">
            신청 시각
          </dt>
          <dd class="sk-body">
            {{ formatKoreanDateTime(ownRequest.requested_at) }}
          </dd>
          <dt class="sk-field-label">
            사유
          </dt>
          <dd class="sk-body whitespace-pre-wrap break-words">
            {{ ownRequest.reason }}
          </dd>
        </dl>

        <UButton
          v-if="view === 'pending'"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-refresh-cw"
          :loading="checking"
          @click="checkApproval"
        >
          승인 확인
        </UButton>

        <form
          v-else
          class="space-y-2"
          @submit.prevent="submitRequest"
        >
          <UTextarea
            v-model="reason"
            class="w-full"
            color="neutral"
            variant="subtle"
            :rows="3"
            :maxlength="TOOL_FILES_REASON_MAX"
            placeholder="신청 사유 (예: 레시피 백업 전 로그 폴더 확인)"
            aria-label="신청 사유"
          />
          <div class="flex items-center justify-between gap-3">
            <span class="sk-meta tabular-nums">{{ reason.length }} / {{ TOOL_FILES_REASON_MAX }}</span>
            <UButton
              type="submit"
              color="primary"
              size="sm"
              icon="i-lucide-send"
              :loading="submitting"
              :disabled="!toolFilesReasonValid(reason)"
              :class="!toolFilesReasonValid(reason) ? 'cursor-not-allowed' : undefined"
            >
              {{ view === 'rejected' ? '다시 신청' : '권한 신청' }}
            </UButton>
          </div>
          <p
            v-if="submitError"
            class="sk-meta text-rose-600 dark:text-rose-400"
          >
            {{ submitError }}
          </p>
        </form>
      </div>
    </UCard>

    <UCard
      v-else
      class="dashboard-surface"
      :ui="{ body: 'p-0 sm:p-0', header: 'px-4 py-3 sm:px-4' }"
    >
      <template #header>
        <div class="flex flex-wrap items-center gap-2">
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-arrow-up"
            aria-label="상위 폴더"
            :disabled="!listing?.parent"
            @click="listing?.parent && openPath(listing.parent)"
          />
          <nav
            class="flex h-8 min-w-0 flex-[1_1_22rem] items-center gap-0.5 rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-muted-surface) px-1.5"
            aria-label="경로"
          >
            <UIcon
              name="i-lucide-hard-drive"
              class="mx-1 size-3.5 shrink-0 text-(--sk-ink-muted)"
            />
            <template
              v-for="(crumb, index) in listing?.crumbs ?? []"
              :key="crumb.path"
            >
              <UIcon
                v-if="index > 0"
                name="i-lucide-chevron-right"
                class="size-3 shrink-0 text-(--sk-ink-subtle)"
              />
              <button
                type="button"
                class="rounded-(--sk-r-sidebar) px-1.5 py-0.5 sk-value-num hover:bg-(--sk-chip-bg)"
                :class="crumb.path === listing?.path ? 'font-semibold' : undefined"
                @click="openPath(crumb.path)"
              >
                {{ crumb.name }}
              </button>
            </template>
            <UButton
              v-if="listing"
              class="ml-auto"
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-copy"
              aria-label="경로 복사"
              @click="copyPath"
            />
          </nav>
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-refresh-cw"
            :loading="listingStatus === 'pending'"
            :disabled="!target"
            @click="refreshListing()"
          >
            새로고침
          </UButton>
        </div>
      </template>

      <div class="flex flex-wrap items-center gap-2 border-b border-(--sk-border-soft) px-4 py-2.5">
        <UInput
          v-model="nameFilter"
          class="min-w-[14rem] flex-1"
          size="sm"
          icon="i-lucide-search"
          color="neutral"
          variant="subtle"
          placeholder="이 폴더에서 이름 검색"
          aria-label="이 폴더에서 이름 검색"
        />
        <div
          class="flex gap-1"
          role="group"
          aria-label="종류"
        >
          <SkChip
            v-for="option in KIND_OPTIONS"
            :key="option.id"
            :label="option.label"
            :count="kindCounts[option.id]"
            :active="kindFilter === option.id"
            @click="kindFilter = option.id"
          />
        </div>
      </div>
      <label
        v-if="canWrite && listing && listingStatus === 'success'"
        class="mx-4 my-2.5 flex cursor-pointer items-center justify-center gap-2 rounded-(--sk-r-nav) border border-dashed px-4 py-3 text-sm text-(--sk-ink-muted) transition-colors"
        :class="dragging ? 'border-(--sk-accent) bg-(--sk-accent-tint) text-(--sk-ink)' : 'border-(--sk-border) hover:bg-(--sk-muted-surface)'"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
      >
        <UIcon
          :name="uploading ? 'i-lucide-loader-circle' : 'i-lucide-upload'"
          :class="['size-4', uploading && 'animate-spin']"
        />
        <span>{{ uploading ? `${uploading} 올리는 중…` : `파일을 끌어 놓거나 눌러서 ${listing.path} 에 올리기` }}</span>
        <input
          type="file"
          class="sr-only"
          multiple
          :disabled="!!uploading"
          @change="onPick"
        >
      </label>

      <AppEmptyState
        v-if="!target"
        icon="i-lucide-server"
        title="장비가 지정되지 않았습니다."
        description="장비 목록이나 Storage 표에서 장비 행의 파일 링크로 들어오세요."
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
              class="text-left font-semibold hover:underline"
              @click="openPath(row.original.path)"
            >
              {{ row.original.name }}
            </button>
            <span v-else>{{ row.original.name }}</span>
            <UBadge
              v-if="tooLarge(row.original)"
              size="sm"
              color="warning"
              variant="subtle"
            >
              상한 초과
            </UBadge>
            <UTooltip
              v-else-if="looksUndecoded(row.original.name)"
              text="장비에 저장된 파일명 바이트가 손상되어 원래 이름을 읽을 수 없습니다. 받기는 됩니다."
            >
              <UBadge
                size="sm"
                color="neutral"
                variant="subtle"
              >
                이름 손상
              </UBadge>
            </UTooltip>
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
          <UButton
            v-if="canWrite && !row.original.is_dir"
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-trash-2"
            class="text-rose-600"
            :aria-label="`${row.original.name} 삭제`"
            @click="pendingDelete = row.original"
          />
        </template>
      </UTable>
      <footer
        v-if="listing && listingStatus === 'success'"
        class="flex flex-wrap items-center justify-between gap-2 rounded-b-(--sk-r-card) bg-(--sk-muted-surface) px-4 py-2.5 sk-meta"
      >
        <span>
          폴더 <b class="sk-value-num">{{ kindCounts.dir }}</b>
          · 파일 <b class="sk-value-num">{{ kindCounts.file }}</b>
          · 합계 <b class="sk-value-num">{{ formatFileSize(totalBytes) }}</b>
        </span>
        <span>수정 시각은 장비 시계 기준 추정값입니다. 링크(바로가기)는 표시하지 않습니다.</span>
      </footer>
    </UCard>

    <UModal
      :open="!!pendingDelete"
      title="파일 삭제"
      @update:open="(open: boolean) => { if (!open && !deleting) pendingDelete = null }"
    >
      <template #body>
        <p class="text-sm text-(--sk-ink)">
          장비에서 다음 파일을 삭제합니다. 되돌릴 수 없습니다.
        </p>
        <p class="mt-2 break-all rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3 py-2 sk-value-num text-sm">
          {{ pendingDelete?.name }}
        </p>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :disabled="deleting"
            @click="pendingDelete = null"
          >
            취소
          </UButton>
          <UButton
            color="neutral"
            variant="outline"
            icon="i-lucide-trash-2"
            class="text-rose-600"
            :loading="deleting"
            @click="confirmDelete"
          >
            삭제
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn, TableRow } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import type { ToolType } from '~/utils/toolType'
import { formatDateTimeLocal, formatKoreanDateTime } from '~/utils/dateTime'
import { MANUAL_SORTING_OPTIONS, getSortIcon } from '~/utils/tableSorting'
import { copyTextToClipboard } from '~/utils/tableExport'
import { fabSegment } from '~/utils/fab'
import {
  TOOL_FILES_REASON_MAX,
  filterToolFileEntries,
  formatFileSize,
  looksUndecoded,
  sortToolFileEntries,
  toolFilesAccessView,
  toolFilesErrorCode,
  toolFilesErrorMessage,
  toolFilesReasonValid,
  toolFilesVerdictMessage,
  type ToolFileEntry,
  type ToolFileKind,
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
const inventoryPath = computed(() => `/ebeam/${props.toolType}/${fabSegment(props.fab)}`)

const { data: access, status: accessStatus, error: accessError, refresh: refreshAccess } = useToolFilesAccess(props.toolType)

// A button, not polling: approval is rare and /api is rate-limited per user.
const checking = ref(false)
const checkApproval = async () => {
  checking.value = true
  try {
    await refreshAccess()
  } finally {
    checking.value = false
  }
}
const view = computed(() => toolFilesAccessView(access.value))
const refusal = computed(() => {
  const verdict = access.value?.verdict
  return toolFilesVerdictMessage(!verdict || verdict === 'granted' ? 'store_unavailable' : verdict)
})
const ownRequest = computed(() => access.value?.request ?? null)

const reason = ref('')
const submitting = ref(false)
const submitError = ref('')

const submitRequest = async () => {
  if (!toolFilesReasonValid(reason.value) || submitting.value) return
  submitting.value = true
  submitError.value = ''
  try {
    await requestToolFilesAccess(reason.value.trim())
    reason.value = ''
    await refreshAccess()
  } catch (error) {
    submitError.value = toolFilesErrorMessage(toolFilesErrorCode(error))
  } finally {
    submitting.value = false
  }
}

const queryString = (key: string) => {
  const value = route.query[key]
  return typeof value === 'string' && value ? value : undefined
}

// One page = one tool, fixed by the ?eqp= the inventory/storage row link carries.
const selectedEqp = computed(() => queryString('eqp'))
const currentPath = computed(() => queryString('path'))

// Null until access is granted, so a refused visitor never sends a /list that
// can only come back 403 (a console network error nothing can suppress).
const target = computed(() =>
  access.value?.verdict === 'granted' && selectedEqp.value
    ? { toolType: props.toolType, fab: props.fab, eqpId: selectedEqp.value }
    : null
)

const { data: semRows } = useSemList()
// Display only: a duplicated eqp_id resolves server-side (409 when rows differ).
const semRow = computed(() => (semRows.value ?? []).find(row => row.eqp_id === selectedEqp.value))

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

const toolFacts = computed(() => [
  { label: '장비', value: selectedEqp.value ?? '' },
  { label: '모델', value: semRow.value ? `${semRow.value.eqp_model_cd} · ${semRow.value.vendor_nm}` : '—' },
  { label: '로그인 폴더', value: listing.value?.root ?? '—' },
  { label: '다운로드 상한', value: listing.value ? formatFileSize(listing.value.max_bytes) : '—' }
])

// Read off the listing call itself: there is no separate health probe.
const connection = computed(() => {
  if (!target.value) return null
  if (listingStatus.value === 'pending') return { label: '확인 중', color: 'neutral' as const, icon: 'i-lucide-loader-circle' }
  if (listingError.value) return { label: '접속 실패', color: 'error' as const, icon: 'i-lucide-unplug' }
  if (listing.value) return { label: '접속됨', color: 'success' as const, icon: 'i-lucide-check' }
  return null
})

const copyPath = async () => {
  if (!listing.value) return
  const ok = await copyTextToClipboard(listing.value.path)
  toast.add({ title: ok ? '경로를 복사했습니다.' : '경로를 복사하지 못했습니다.', color: ok ? 'success' : 'error' })
}

const nameFilter = ref('')
const kindFilter = ref<ToolFileKind>('all')
const KIND_OPTIONS: { id: ToolFileKind, label: string }[] = [
  { id: 'all', label: '전체' },
  { id: 'dir', label: '폴더' },
  { id: 'file', label: '파일' }
]
const kindCounts = computed(() => {
  const entries = listing.value?.entries ?? []
  const dir = entries.filter(entry => entry.is_dir).length
  return { all: entries.length, dir, file: entries.length - dir }
})
const totalBytes = computed(() => (listing.value?.entries ?? []).reduce((sum, entry) => sum + (entry.size ?? 0), 0))
const sorting = ref<SortingState>([{ id: 'name', desc: false }])

const visibleEntries = computed(() => {
  const rows = filterToolFileEntries(listing.value?.entries ?? [], nameFilter.value, kindFilter.value)
  const sort = sorting.value[0]
  return sort ? sortToolFileEntries(rows, sort.id as ToolFileSortKey, sort.desc ? 'desc' : 'asc') : rows
})

const SORTABLE_HEADERS = [
  { id: 'name', label: '이름' },
  { id: 'size', label: '크기' },
  { id: 'modified', label: '수정 시각' }
] as const

const canWrite = computed(() => access.value?.can_write === true)

const columns = computed<TableColumn<ToolFileEntry>[]>(() => [
  { accessorKey: 'name', header: '이름' },
  { accessorKey: 'size', header: '크기', meta: { class: { th: 'text-right w-[8rem]', td: 'w-[8rem]' } } },
  { accessorKey: 'modified', header: '수정 시각', meta: { class: { th: 'w-[11rem]', td: 'w-[11rem]' } } },
  {
    id: 'actions',
    header: '',
    enableSorting: false,
    meta: { class: canWrite.value ? { th: 'w-[5rem]', td: 'w-[5rem]' } : { th: 'w-[3rem]', td: 'w-[3rem]' } }
  }
])

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

const dragging = ref(false)
const uploading = ref<string | null>(null)

// One request per file, in order: the server takes one file per upload.
// Only on a settled listing: while a new folder loads, `listing` still holds
// the old one, and its path would go out with the new target.
const uploadAll = async (files: File[]) => {
  const current = target.value
  const dir = listing.value?.path
  if (!current || !dir || listingStatus.value !== 'success' || uploading.value) return
  let uploaded = 0
  for (const file of files) {
    uploading.value = file.name
    try {
      await uploadToolFile(current, dir, file)
      uploaded += 1
    } catch (error) {
      toast.add({
        title: `${file.name}: ${toolFilesErrorMessage(toolFilesErrorCode(error), 'upload')}`,
        color: 'error'
      })
    }
  }
  uploading.value = null
  if (uploaded) toast.add({ title: `${uploaded}개 파일을 올렸습니다.`, color: 'success' })
  await refreshListing()
}

const onDrop = (event: DragEvent) => {
  dragging.value = false
  uploadAll([...(event.dataTransfer?.files ?? [])])
}

const onPick = (event: Event) => {
  const input = event.target as HTMLInputElement
  const files = [...(input.files ?? [])]
  input.value = ''
  uploadAll(files)
}

const pendingDelete = ref<ToolFileEntry | null>(null)
const deleting = ref(false)

const confirmDelete = async () => {
  const entry = pendingDelete.value
  if (!entry || !target.value) return
  deleting.value = true
  try {
    await deleteToolFile(target.value, entry.path)
    toast.add({ title: `${entry.name}을(를) 삭제했습니다.`, color: 'success' })
  } catch (error) {
    toast.add({ title: toolFilesErrorMessage(toolFilesErrorCode(error)), color: 'error' })
  } finally {
    deleting.value = false
    pendingDelete.value = null
  }
  await refreshListing()
}
</script>
