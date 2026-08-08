<template>
  <div class="dashboard-surface rounded-2xl p-4">
    <div class="mb-3 flex flex-wrap items-center gap-2">
      <div class="flex h-8 items-center gap-1.5 rounded-lg border border-zinc-200 bg-white px-2.5 dark:border-zinc-800 dark:bg-zinc-950">
        <UIcon
          name="i-lucide-search"
          class="h-3.5 w-3.5 shrink-0 text-(--sk-ink-muted)"
        />
        <input
          v-model="paramSearch"
          type="search"
          autocomplete="off"
          placeholder="파라미터 검색 (예: WAFER)"
          aria-label="파라미터 검색"
          class="w-44 min-w-0 bg-transparent text-xs text-zinc-950 outline-none placeholder:text-(--sk-ink-muted) dark:text-zinc-50"
        >
      </div>
      <div class="flex items-center gap-1">
        <SkNavPill
          v-for="opt in filterOptions"
          :key="opt.value"
          size="sm"
          :label="`${opt.label} ${opt.count}`"
          :active="coverageFilter === opt.value"
          @click="coverageFilter = opt.value"
        />
      </div>
      <UButton
        size="xs"
        color="neutral"
        variant="outline"
        icon="i-lucide-check-check"
        label="공통 전체 선택"
        @click="selectCommon"
      />
      <span class="ml-auto sk-meta">{{ modelValue.length }}개 선택</span>
    </div>

    <div class="max-h-[300px] overflow-auto rounded-lg border border-zinc-200/70 dark:border-zinc-800/70">
      <table class="w-full border-collapse font-mono text-[11px]">
        <thead>
          <tr class="sticky top-0 z-10 bg-zinc-50/90 text-left text-(--sk-ink-muted) dark:bg-zinc-900/70">
            <th class="w-8 p-2" />
            <th class="px-2.5 py-2 font-medium tracking-wide">
              parameter
            </th>
            <th class="px-2.5 py-2 font-medium tracking-wide">
              coverage
            </th>
            <th
              v-for="col in columns"
              :key="recipePairKey(col.fab_name, col.recipe_id)"
              class="px-2 py-2 text-center font-medium"
              :title="col.recipe_id"
            >
              {{ shortId(col.recipe_id) }}
              <span
                v-if="multiFab"
                class="sk-fab-badge"
              >
                {{ col.fab_name }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in filteredRows"
            :key="row.parameter"
            class="transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/40"
          >
            <td class="p-2">
              <UCheckbox
                :model-value="modelValue.includes(row.parameter)"
                :aria-label="`${row.parameter} 비교 선택`"
                @update:model-value="toggleParam(row.parameter)"
              />
            </td>
            <td class="px-2.5 py-1.5 font-semibold text-zinc-900 dark:text-zinc-100">
              {{ row.parameter }}
            </td>
            <td class="px-2.5 py-1.5">
              <span
                class="rounded px-1.5 py-0.5 text-[11px] font-bold"
                :class="coverageClass(row.coverage)"
              >
                {{ coverageLabel(row) }}
              </span>
            </td>
            <td
              v-for="col in columns"
              :key="recipePairKey(col.fab_name, col.recipe_id)"
              class="px-2 py-1.5 text-center"
              :class="row.presentIn.includes(recipePairKey(col.fab_name, col.recipe_id)) ? 'text-emerald-500' : 'text-(--sk-ink-subtle)'"
            >
              {{ row.presentIn.includes(recipePairKey(col.fab_name, col.recipe_id)) ? '✓' : '—' }}
            </td>
          </tr>
          <tr v-if="filteredRows.length === 0">
            <td
              :colspan="3 + columns.length"
              class="px-3 py-6 text-center text-(--sk-ink-muted)"
            >
              일치하는 파라미터가 없습니다.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  type CompareColumn,
  type Coverage,
  type CoverageFilter,
  type OverlapRow,
  commonParameters,
  filterOverlap,
  spansFabs
} from '~/utils/recipeCompare'
import { recipePairKey } from '~/utils/recipePair'

const props = defineProps<{
  rows: OverlapRow[]
  columns: CompareColumn[]
}>()

// recipe_id alone collides when the same recipe name is compared across two
// fabs — the chip only earns its keep once that's actually happening.
const multiFab = computed(() => spansFabs(props.columns))

const modelValue = defineModel<string[]>({ required: true })

const paramSearch = ref('')
const coverageFilter = ref<CoverageFilter>('all')

const filterOptions = computed<{ value: CoverageFilter, label: string, count: number }[]>(() => [
  { value: 'all', label: '전체', count: props.rows.length },
  { value: 'common', label: '공통', count: props.rows.filter(r => r.coverage === 'all').length },
  { value: 'partial', label: '부분', count: props.rows.filter(r => r.coverage === 'partial').length },
  { value: 'unique', label: '고유', count: props.rows.filter(r => r.coverage === 'unique').length }
])

const filteredRows = computed(() => {
  const byCoverage = filterOverlap(props.rows, coverageFilter.value)
  const term = paramSearch.value.trim().toLowerCase()
  if (!term) return byCoverage
  return byCoverage.filter(r => r.parameter.toLowerCase().includes(term))
})

const toggleParam = (parameter: string) => {
  modelValue.value = modelValue.value.includes(parameter)
    ? modelValue.value.filter(p => p !== parameter)
    : [...modelValue.value, parameter]
}

const selectCommon = () => {
  const common = commonParameters(props.rows)
  const merged = new Set([...modelValue.value, ...common])
  modelValue.value = [...merged]
}

const shortId = (id: string) => (id.length > 12 ? `…${id.slice(-10)}` : id)

const coverageLabel = (row: OverlapRow) =>
  row.coverage === 'all' ? 'ALL' : `${row.count}/${row.total}`

const coverageClass = (coverage: Coverage) =>
  coverage === 'all'
    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
    : coverage === 'partial'
      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
      : 'bg-zinc-500/15 text-(--sk-ink-muted)'
</script>
