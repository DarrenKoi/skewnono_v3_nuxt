<template>
  <section class="dashboard-surface flex min-h-0 flex-col overflow-hidden rounded-(--sk-r-card)">
    <header class="flex flex-wrap items-center justify-between gap-2 border-b border-(--sk-border-soft) px-3 py-2">
      <div class="flex items-baseline gap-2">
        <h2 class="sk-title">
          검색 결과
        </h2>
        <span
          v-if="searched"
          class="sk-meta tabular-nums"
        >
          {{ rows.length }} / {{ total.toLocaleString() }}건
        </span>
      </div>

      <UInput
        v-if="searched && rows.length"
        :model-value="narrowText"
        size="xs"
        icon="i-lucide-filter"
        placeholder="결과 내 좁히기"
        class="w-48"
        @update:model-value="emit('update:narrowText', String($event))"
      />
    </header>

    <!-- The result set exceeded OpenSearch's retrieval ceiling. Hiding this
         would quietly give a wrong answer to "how many times did this run". -->
    <p
      v-if="capped"
      class="border-b border-(--sk-border-soft) bg-amber-500/10 px-3 py-1.5 text-xs text-amber-700 dark:text-amber-400"
    >
      {{ total.toLocaleString() }}건 중 상위 10,000건만 조회됩니다. 검색어나 기간을 좁혀주세요.
    </p>

    <!-- Errors never blank out rows already on screen: a refetch that fails
         (e.g. narrowing an existing result set) keeps showing the last good
         table, with this banner + retry layered on top. Only when there is
         nothing to keep (bodyState 'error-empty') does the body switch to a
         dedicated error prompt below. -->
    <div
      v-if="error && rows.length"
      class="flex items-center justify-between gap-3 border-b border-(--sk-border-soft) bg-(--sk-bad)/10 px-3 py-1.5 text-xs text-(--sk-bad)"
    >
      <span>{{ error }}</span>
      <UButton
        color="neutral"
        variant="outline"
        size="xs"
        label="재시도"
        @click="emit('retry')"
      />
    </div>

    <AppLoadingState
      v-if="bodyState === 'loading'"
      variant="inline"
      title="검색 중입니다."
    />

    <!-- Default state: no query yet. This is the page's landing state — rows
         are never auto-shown here. -->
    <div
      v-else-if="bodyState === 'default'"
      class="flex flex-col items-center gap-1.5 px-4 py-14 text-center"
    >
      <UIcon
        name="i-lucide-search"
        class="h-5 w-5 text-(--sk-ink-subtle)"
      />
      <p class="sk-body">
        장비 · Recipe · Lot · 날짜 · MSR 로 측정을 검색하세요.
      </p>
      <p class="sk-meta">
        최근 {{ retentionDays }}일 보존
      </p>
    </div>

    <!-- A search that failed outright, with no prior rows to fall back on.
         Distinct from "no match": the fix here is retry, not "search again
         with different terms". -->
    <div
      v-else-if="bodyState === 'errorEmpty'"
      class="flex flex-col items-center gap-2 px-4 py-14 text-center"
    >
      <UIcon
        name="i-lucide-circle-alert"
        class="h-5 w-5 text-(--sk-bad)"
      />
      <p class="text-[12.5px] text-(--sk-bad)">
        {{ error }}
      </p>
      <UButton
        color="neutral"
        variant="outline"
        size="xs"
        label="재시도"
        @click="emit('retry')"
      />
    </div>

    <!-- Out of retention: distinct from "no match" — the fix is to widen the
         date range, not to change the search terms. -->
    <div
      v-else-if="bodyState === 'outOfRetention'"
      class="flex flex-col items-center gap-1.5 px-4 py-14 text-center"
    >
      <UIcon
        name="i-lucide-calendar-off"
        class="h-5 w-5 text-(--sk-ink-subtle)"
      />
      <p class="sk-body">
        보존 기간({{ retentionDays }}일) 밖입니다. 기간을 조정해 주세요.
      </p>
    </div>

    <div
      v-else-if="bodyState === 'noMatch'"
      class="flex flex-col items-center gap-1.5 px-4 py-14 text-center"
    >
      <UIcon
        name="i-lucide-file-question"
        class="h-5 w-5 text-(--sk-ink-subtle)"
      />
      <p class="sk-body">
        일치하는 측정이 없습니다.
      </p>
    </div>

    <div
      v-else
      class="min-h-0 flex-1 overflow-auto"
    >
      <table class="w-full border-collapse text-[12px]">
        <thead class="sticky top-0 z-10 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border-soft) text-left">
            <th
              class="w-8 px-3 py-1.5"
              @click.stop
            >
              <UCheckbox
                :model-value="allVisibleSelected"
                aria-label="현재 검색 결과 전체 선택"
                @update:model-value="toggleVisible"
              />
            </th>
            <th
              v-for="column in COLUMNS"
              :key="column.label"
              class="px-3 py-1.5"
              :class="{ 'sk-eyebrow': !column.sortKey }"
              :aria-sort="column.sortKey ? ariaSort(column.sortKey) : undefined"
            >
              <!-- Sortable headers are real <button>s rather than a click
                   handler on the <th>: the control has to be reachable and
                   operable from the keyboard, while aria-sort has to sit on the
                   <th> itself to be announced as the column's state. -->
              <button
                v-if="column.sortKey"
                type="button"
                class="group flex items-center gap-1 sk-eyebrow transition-colors hover:text-(--sk-ink)"
                :class="{ 'text-(--sk-ink)': sort.key === column.sortKey }"
                @click="emit('toggleSort', column.sortKey)"
              >
                {{ column.label }}
                <UIcon
                  :name="sortIcon(column.sortKey)"
                  class="h-3 w-3"
                  :class="sort.key === column.sortKey
                    ? 'opacity-100'
                    : 'opacity-0 transition-opacity group-hover:opacity-40'"
                />
              </button>
              <template v-else>
                {{ column.label }}
              </template>
            </th>
            <th class="px-3 py-1.5" />
          </tr>
        </thead>
        <tbody>
          <!-- msr_check "No" rows have no MSR file in MinIO (user-confirmed
               2026-08-19) -- no raw data to open or compare -- so they render
               without the click/checkbox affordances. They may also carry no
               msr value at all (OFFICE-VERIFY): measHistRowKey keeps such
               rows' v-for keys unique, since several '' keys would break
               keyed patching ("Duplicate keys found during update") and
               mis-render rows. -->
          <tr
            v-for="(row, index) in rows"
            :key="measHistRowKey(row, index)"
            class="border-b border-(--sk-border-soft) transition-colors last:border-0"
            :class="isAnalyzableMeasHist(row)
              ? ['cursor-pointer', 'hover:bg-(--sk-brand)/5', { 'bg-(--sk-brand)/5': isSelected(row.msr) }]
              : 'cursor-default'"
            @click="isAnalyzableMeasHist(row) && emit('open', row)"
          >
            <td
              class="px-3 py-2"
              @click.stop
            >
              <UTooltip
                :text="isAnalyzableMeasHist(row) ? undefined : 'MSR 파일이 저장되어 있지 않아(msr_check No) 선택할 수 없습니다'"
                :disabled="isAnalyzableMeasHist(row)"
              >
                <UCheckbox
                  :model-value="isSelected(row.msr)"
                  :disabled="!isAnalyzableMeasHist(row)"
                  :aria-label="`${row.full_name} 측정 선택`"
                  @update:model-value="emit('toggle', row)"
                />
              </UTooltip>
            </td>
            <td class="px-3 py-2 font-mono font-semibold text-zinc-900 dark:text-zinc-100">
              {{ row.lot_id }}
            </td>
            <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
              <!-- The row navigates on click, so a drag-select over the recipe
                   name ends in a click and opens the analysis view instead of
                   copying. The button is the escape hatch, and @click.stop is
                   what keeps pressing it from navigating too. -->
              <div class="flex items-center gap-1">
                <span>{{ row.full_name }}</span>
                <UTooltip text="레시피명 복사">
                  <UButton
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-copy"
                    :aria-label="`${row.full_name} 복사`"
                    @click.stop="copyRecipe(row.full_name)"
                  />
                </UTooltip>
              </div>
            </td>
            <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
              {{ row.eqp_id }}
            </td>
            <td class="px-3 py-2">
              <span class="rounded-(--sk-r-chip) bg-(--sk-chip-bg) px-1.5 py-0.5 font-mono text-[11px] text-(--sk-chip-text)">
                {{ row.fab_name }}
              </span>
            </td>
            <td class="px-3 py-2 font-mono text-(--sk-ink-muted)">
              {{ row.timestamp.slice(0, 16).replace('T', ' ') }}
            </td>
            <td class="px-3 py-2 text-right">
              <UIcon
                name="i-lucide-arrow-right"
                class="h-3.5 w-3.5 text-(--sk-ink-subtle)"
              />
            </td>
          </tr>
        </tbody>
      </table>

      <!-- The sort runs in the browser over the rows already fetched, so while
           results remain unloaded it has re-ordered a page and not the result
           set. Saying so is the whole reason this is safe to ship client-side:
           a `RECIPE ↑` header otherwise reads as authoritative over all
           `total` hits, and quietly answers "which recipe ran first" with the
           wrong row. -->
      <p
        v-if="sortIsPartial"
        class="border-t border-(--sk-border-soft) bg-amber-500/10 px-3 py-1.5 text-xs text-amber-700 dark:text-amber-400"
      >
        불러온 {{ rows.length }}건만 정렬했습니다. 전체 {{ total.toLocaleString() }}건 기준으로 정렬하려면 더 보기로 결과를 모두 불러오세요.
      </p>

      <div
        v-if="hasMore"
        class="border-t border-(--sk-border-soft) p-2"
      >
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          block
          :loading="pending"
          label="더 보기"
          @click="emit('loadMore')"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { MeasHistRow } from '~/composables/useMeasHistApi'
import type { MeasHistSort, MeasHistSortKey } from '~/utils/measHistSort'
import { copyTextToClipboard } from '~/utils/csvDownload'
import { isAnalyzableMeasHist, measHistRowKey } from '~/utils/measHistSelection'

const props = defineProps<{
  rows: MeasHistRow[]
  total: number
  capped: boolean
  outOfRetention: boolean
  searched: boolean
  pending: boolean
  error: string | null
  hasMore: boolean
  narrowText: string
  retentionDays: number
  selected: MeasHistRow[]
  sort: MeasHistSort
  sortIsPartial: boolean
}>()

const emit = defineEmits<{
  'open': [row: MeasHistRow]
  'toggle': [row: MeasHistRow]
  'selectRows': [rows: MeasHistRow[], enabled: boolean]
  'loadMore': []
  'retry': []
  'toggleSort': [column: MeasHistSortKey]
  'update:narrowText': [value: string]
}>()

// Declared here rather than in the template so the header order and the body's
// <td> order have one place to be checked against each other. FAB carries no
// sortKey on purpose: it is a coarse facet with its own dropdown filter, so
// ordering by it only groups rows, which filtering already does better.
const COLUMNS: { label: string, sortKey: MeasHistSortKey | null }[] = [
  { label: 'LOT', sortKey: 'lot' },
  { label: 'RECIPE', sortKey: 'recipe' },
  { label: 'EQ', sortKey: 'eq' },
  { label: 'FAB', sortKey: null },
  { label: 'CAPTURED', sortKey: 'timestamp' }
]

const ariaSort = (column: MeasHistSortKey) =>
  props.sort.key === column
    ? (props.sort.dir === 'asc' ? 'ascending' : 'descending')
    : 'none'

// The inactive columns still render an arrow (revealed on hover) so the header
// advertises that it is sortable before it is clicked; 'up' is the direction
// that first click would apply.
const sortIcon = (column: MeasHistSortKey) => {
  const dir = props.sort.key === column
    ? props.sort.dir
    : (column === 'timestamp' ? 'desc' : 'asc')
  return dir === 'asc' ? 'i-lucide-arrow-up' : 'i-lucide-arrow-down'
}

const toast = useToast()

// copyTextToClipboard, not navigator.clipboard: production is served over
// plain http, where the Clipboard API is absent because it is secure-context
// only. The util carries the execCommand fallback that keeps this working
// there.
const copyRecipe = async (recipe: string) => {
  const ok = await copyTextToClipboard(recipe)
  toast.add(
    ok
      ? { title: '레시피명이 복사되었습니다', description: recipe, icon: 'i-lucide-check', color: 'success' }
      : { title: '레시피명 복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

const selectedIds = computed(() => new Set(props.selected.map(row => row.msr)))
const isSelected = (msr: string) => selectedIds.value.has(msr)

// Rows without a stored MSR file can never join the selection, so "all
// selected" and select-all both range over the selectable rows only --
// otherwise one msr_check "No" row in view keeps the header checkbox
// permanently unchecked.
const selectableRows = computed(() => props.rows.filter(isAnalyzableMeasHist))
const allVisibleSelected = computed(() =>
  selectableRows.value.length > 0 && selectableRows.value.every(row => isSelected(row.msr))
)

const toggleVisible = () => {
  emit('selectRows', selectableRows.value, !allVisibleSelected.value)
}

// Five distinct states, in priority order. An error never masks rows that are
// already on screen — 'error' banner (above) layers on top of the table
// instead of replacing it. Only when there is nothing to fall back on does
// the body switch to a dedicated 'errorEmpty' prompt, which is deliberately
// distinct from 'outOfRetention' and 'noMatch': three different problems,
// three different fixes (retry vs. widen the date range vs. change terms).
type BodyState = 'loading' | 'default' | 'errorEmpty' | 'outOfRetention' | 'noMatch' | 'rows'

const bodyState = computed<BodyState>(() => {
  if (props.pending && !props.rows.length) return 'loading'
  if (!props.searched) return 'default'
  if (props.error && !props.rows.length) return 'errorEmpty'
  if (props.outOfRetention) return 'outOfRetention'
  if (!props.rows.length) return 'noMatch'
  return 'rows'
})
</script>
