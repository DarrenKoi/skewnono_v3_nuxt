<template>
  <AfmCard
    icon="i-lucide-table-2"
    title="측정별 요약"
    flush
  >
    <template #actions>
      <span class="sk-meta">{{ block }} · {{ column }} · Excel 다운로드는 이 표를 그대로 냅니다</span>
    </template>
    <div class="overflow-x-auto">
      <table class="w-full border-collapse">
        <thead>
          <tr class="border-b border-(--sk-border)">
            <th
              v-for="h in HEADERS"
              :key="h.label"
              class="px-2.5 py-2 whitespace-nowrap sk-label"
              :class="h.num ? 'text-right' : 'text-left'"
            >
              {{ h.label }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.entry.key"
            class="cursor-pointer border-b border-(--sk-border-soft) hover:bg-(--sk-muted-surface)"
            :class="row.entry.key === selected ? 'bg-(--sk-muted-surface)' : ''"
            :aria-selected="row.entry.key === selected"
            @click="emit('select', row.entry.key)"
          >
            <td class="px-2.5 py-1.5 whitespace-nowrap sk-value-num text-(--sk-ink-muted)">
              {{ shortTime(row.entry.time) }}
            </td>
            <td
              class="px-2.5 py-1.5 whitespace-nowrap sk-value-num"
              :class="row.entry.key === selected ? 'font-semibold' : ''"
            >
              {{ row.entry.lot }} <span class="text-(--sk-ink-muted)">·{{ row.entry.slot }}</span>
              <span
                v-if="mixed"
                class="ml-1 font-sans sk-meta"
              >{{ row.entry.recipe }}</span>
            </td>
            <td
              class="px-2.5 py-1.5 text-right whitespace-nowrap sk-value-num"
              :class="row.stats?.n != null && row.stats.nValid! < row.stats.n ? 'text-(--sk-bad)' : ''"
            >
              {{ row.stats ? row.stats.n === null ? '–' : `${row.stats.n} (${row.stats.nValid})` : `– (${row.reason})` }}
            </td>
            <td
              v-for="item in STATS"
              :key="item"
              class="px-2.5 py-1.5 text-right whitespace-nowrap sk-value-num"
              :class="item === 'MEAN' ? ['font-semibold', meanOut(row) ? 'text-(--sk-brand)' : ''] : ''"
            >
              {{ fmt2(row.stats?.[item]) }}
            </td>
            <td
              class="px-2.5 py-1.5 text-right whitespace-nowrap sk-value-num"
              :class="row.out ? 'text-(--sk-brand)' : 'text-(--sk-ink-muted)'"
            >
              {{ row.delta === null ? '–' : formatSignedNm(row.delta, 2) }}
            </td>
            <td class="px-2.5 py-1.5">
              <UBadge
                v-if="row.state"
                :label="row.state"
                :color="STATE_BADGE[row.state] ?? 'neutral'"
                variant="subtle"
              />
              <span
                v-else
                class="sk-meta"
              >–</span>
            </td>
          </tr>
        </tbody>
        <tfoot v-if="foot.length">
          <tr
            v-for="f in foot"
            :key="f.label"
            class="border-t border-(--sk-border) bg-(--sk-muted-surface)"
          >
            <td
              colspan="3"
              class="px-2.5 py-1.5 text-xs font-semibold text-(--sk-ink)"
            >
              {{ f.label }}
            </td>
            <td
              v-for="(cell, i) in f.cells"
              :key="i"
              class="px-2.5 py-1.5 text-right sk-value-num"
              :class="i === 0 ? 'font-semibold' : ''"
            >
              {{ cell }}
            </td>
            <td
              colspan="2"
              class="px-2.5 py-1.5 sk-meta"
            >
              {{ f.note }}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
import type { TrendRow, TrendStat } from '~/utils/afmTrend'
import { mean } from '~/utils/stats'

const props = defineProps<{
  rows: TrendRow[]
  block: string
  column: string
  stat: TrendStat
  selected: string | null
  mixed: boolean
}>()
const emit = defineEmits<{ select: [key: string] }>()

const STATS: TrendStat[] = ['MEAN', 'STDEV', 'MIN', 'MAX', 'RANGE']
const HEADERS = [
  { label: '시각' }, { label: 'Lot · Slot' }, { label: 'n (유효)', num: true },
  ...STATS.map(label => ({ label, num: true })),
  { label: 'Δ μ', num: true }, { label: '상태' }
]

// MEAN is terracotta only when it is the statistic the limits were drawn for.
const meanOut = (row: TrendRow) => props.stat === 'MEAN' && row.out

// Group rows exist only for one recipe: across recipes the same column name
// may not be the same quantity.
const foot = computed(() => {
  if (props.mixed) return []
  const stats = props.rows.flatMap(row => row.stats ? [row.stats] : [])
  const means = stats.flatMap(s => s.MEAN ?? [])
  if (means.length < 2) return []
  const avg = (item: TrendStat) => fmt2(mean(stats.flatMap(s => s[item] ?? [])))
  const split = varianceSplit(stats)
  const min = Math.min(...means)
  const max = Math.max(...means)
  return [
    { label: `그룹 (${means.length}건)`, cells: [fmt2(mean(means)), fmt2(split?.lotSd), fmt2(min), fmt2(max), fmt2(max - min)], note: 'MEAN 열의 통계 · STDEV = lot 간 σ' },
    { label: 'wafer 내 평균', cells: ['', fmt2(split?.waferSd), avg('MIN'), avg('MAX'), avg('RANGE')], note: '각 측정의 STDEV·MIN·MAX·RANGE 평균' }
  ]
})
</script>
