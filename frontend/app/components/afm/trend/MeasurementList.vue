<template>
  <AfmCard
    icon="i-lucide-list-checks"
    title="선택한 측정"
    :count="rows.length"
    flush
  >
    <template #actions>
      <span class="sk-meta">행을 누르면 강조 · 기준 = 고정 기준에 포함</span>
    </template>
    <ul class="max-h-[22rem] divide-y divide-(--sk-border-soft) overflow-y-auto">
      <li
        v-for="row in rows"
        :key="row.entry.key"
        class="flex items-center hover:bg-(--sk-muted-surface)"
        :class="row.entry.key === selected ? 'bg-(--sk-muted-surface)' : ''"
      >
        <button
          type="button"
          class="grid min-w-0 flex-1 grid-cols-[6.5rem_minmax(0,1fr)_auto_3.5rem] items-center gap-2.5 py-2 pr-2.5 pl-4 text-left"
          :aria-pressed="row.entry.key === selected"
          @click="emit('select', row.entry.key)"
        >
          <span class="sk-value-num text-(--sk-ink-muted)">{{ shortTime(row.entry.time) }}</span>
          <span class="flex min-w-0 items-center gap-1.5">
            <span
              class="size-1.5 shrink-0 rounded-full"
              :class="STATE_DOT[row.state ?? ''] ?? 'bg-(--sk-ink-subtle)'"
            />
            <span
              class="truncate font-mono text-xs text-(--sk-ink)"
              :class="row.entry.key === selected ? 'font-semibold' : ''"
            >{{ row.entry.lot }}</span>
            <span class="shrink-0 font-mono text-xs text-(--sk-ink-muted)">·{{ row.entry.slot }}</span>
            <span
              v-if="mixed"
              class="truncate sk-meta"
            >{{ row.entry.recipe }}</span>
            <span
              v-if="!row.stats"
              class="shrink-0 text-xs font-semibold text-(--sk-warn)"
            >{{ row.reason }}</span>
            <span
              v-else-if="repeatKeys.has(row.entry.key)"
              class="shrink-0 text-xs font-semibold text-(--sk-ink-muted)"
            >재측정</span>
          </span>
          <span
            class="sk-value-num font-semibold"
            :class="row.out ? 'text-(--sk-brand)' : ''"
          >{{ fmt2(row.value) }}</span>
          <span
            class="text-right font-mono text-xs tabular-nums"
            :class="row.out ? 'text-(--sk-brand)' : 'text-(--sk-ink-muted)'"
          >{{ row.delta === null ? '' : formatSignedNm(row.delta, 2) }}</span>
        </button>
        <SkChip
          class="mr-4 shrink-0"
          size="sm"
          tone="ink"
          label="기준"
          :active="row.role === 'baseline'"
          :aria-label="`${row.entry.lot} ·${row.entry.slot} 고정 기준`"
          @click="emit('toggleBaseline', row.entry.key)"
        />
      </li>
    </ul>
    <template #footer>
      <p class="flex justify-between gap-3 sk-meta">
        <span>값 = 선택한 블록·항목의 {{ stat }}</span>
        <span>Δ = {{ rows.some(row => row.role === 'baseline') ? '고정 기준' : mixed ? 'recipe' : '그룹' }} 평균 대비</span>
      </p>
    </template>
  </AfmCard>
</template>

<script setup lang="ts">
import type { TrendRow, TrendStat } from '~/utils/afmTrend'

defineProps<{
  rows: TrendRow[]
  stat: TrendStat
  selected: string | null
  repeatKeys: Set<string>
  mixed: boolean
}>()
const emit = defineEmits<{ select: [key: string], toggleBaseline: [key: string] }>()
</script>
