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

    <div
      v-if="bodyState === 'loading'"
      class="flex items-center justify-center gap-2 px-4 py-12 sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      검색 중입니다.
    </div>

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
            <th class="px-3 py-1.5 sk-eyebrow">
              LOT
            </th>
            <th class="px-3 py-1.5 sk-eyebrow">
              RECIPE
            </th>
            <th class="px-3 py-1.5 sk-eyebrow">
              EQ
            </th>
            <th class="px-3 py-1.5 sk-eyebrow">
              FAB
            </th>
            <th class="px-3 py-1.5 sk-eyebrow">
              CAPTURED
            </th>
            <th class="px-3 py-1.5" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.msr"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors last:border-0 hover:bg-(--sk-brand)/5"
            :class="{ 'bg-(--sk-brand)/5': isSelected(row.msr) }"
            @click="emit('open', row)"
          >
            <td
              class="px-3 py-2"
              @click.stop
            >
              <UCheckbox
                :model-value="isSelected(row.msr)"
                :aria-label="`${row.full_name} 측정 선택`"
                @update:model-value="emit('toggle', row)"
              />
            </td>
            <td class="px-3 py-2 font-mono font-semibold text-zinc-900 dark:text-zinc-100">
              {{ row.lot_id }}
            </td>
            <td class="px-3 py-2 font-mono text-zinc-600 dark:text-zinc-300">
              {{ row.full_name }}
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
}>()

const emit = defineEmits<{
  'open': [row: MeasHistRow]
  'toggle': [row: MeasHistRow]
  'selectRows': [rows: MeasHistRow[], enabled: boolean]
  'loadMore': []
  'retry': []
  'update:narrowText': [value: string]
}>()

const selectedIds = computed(() => new Set(props.selected.map(row => row.msr)))
const isSelected = (msr: string) => selectedIds.value.has(msr)
const allVisibleSelected = computed(() =>
  props.rows.length > 0 && props.rows.every(row => isSelected(row.msr))
)

const toggleVisible = () => {
  emit('selectRows', props.rows, !allVisibleSelected.value)
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
