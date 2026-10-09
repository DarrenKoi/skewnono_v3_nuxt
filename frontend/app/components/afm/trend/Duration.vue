<template>
  <AfmCard
    icon="i-lucide-timer"
    title="측정 소요시간"
    :count="rows.length"
    flush
  >
    <ul class="divide-y divide-(--sk-border-soft) border-b border-(--sk-border-soft)">
      <li
        v-for="item in recipes"
        :key="item.recipe"
        class="grid grid-cols-[minmax(0,1fr)_auto_auto_auto_auto] items-baseline gap-x-4 px-4 py-2"
      >
        <span class="truncate font-mono text-xs font-semibold text-(--sk-ink)">{{ item.recipe }}</span>
        <span class="sk-meta">계산 {{ item.counted }}/{{ item.total }}건</span>
        <span class="sk-meta">중앙값 <span class="font-mono tabular-nums text-(--sk-ink)">{{ span(item.median) }}</span></span>
        <span class="sk-meta">최소–최대 <span class="font-mono tabular-nums text-(--sk-ink)">{{ item.counted ? `${span(item.min)} – ${span(item.max)}` : '—' }}</span></span>
        <span class="sk-meta">포인트당 중앙값 <span class="font-mono tabular-nums text-(--sk-ink)">{{ item.medianPerPoint === null ? '—' : formatPerPoint(item.medianPerPoint) }}</span></span>
      </li>
    </ul>
    <ul class="max-h-[22rem] divide-y divide-(--sk-border-soft) overflow-y-auto">
      <li
        v-for="row in rows"
        :key="row.entry.key"
      >
        <button
          type="button"
          class="grid w-full grid-cols-[6.5rem_minmax(0,1fr)_auto] items-center gap-2.5 px-4 py-2 text-left hover:bg-(--sk-muted-surface)"
          :class="row.entry.key === selected ? 'bg-(--sk-muted-surface)' : ''"
          :aria-pressed="row.entry.key === selected"
          @click="emit('select', row.entry.key)"
        >
          <span class="sk-value-num text-(--sk-ink-muted)">{{ shortTime(row.entry.time) }}</span>
          <span class="flex min-w-0 items-center gap-1.5">
            <span
              class="truncate font-mono text-xs text-(--sk-ink)"
              :class="row.entry.key === selected ? 'font-semibold' : ''"
            >{{ row.entry.lot }}</span>
            <span class="shrink-0 font-mono text-xs text-(--sk-ink-muted)">·{{ row.entry.slot }}</span>
            <span class="truncate sk-meta">{{ row.entry.recipe }}</span>
          </span>
          <span
            v-if="row.duration.kind === 'ok'"
            class="font-mono text-xs tabular-nums text-(--sk-ink)"
          >
            <span class="font-semibold">{{ formatDuration(row.duration.seconds) }}</span>
            <span
              v-if="row.perPoint !== null"
              class="ml-2 text-(--sk-ink-muted)"
            >{{ row.points }}행 · 포인트당 {{ formatPerPoint(row.perPoint) }}</span>
            <span
              v-if="row.ratio !== null"
              class="ml-2 text-(--sk-ink-muted)"
            >중앙값의 {{ row.ratio.toFixed(1) }}배</span>
          </span>
          <span
            v-else
            class="text-xs text-(--sk-ink-muted)"
          >{{ DURATION_REASON_LABEL[row.duration.reason] }}</span>
        </button>
      </li>
    </ul>
  </AfmCard>
</template>

<script setup lang="ts">
import { shortTime } from '~/utils/afmTrend'
import { DURATION_REASON_LABEL, formatDuration, formatPerPoint, type DurationRow, type RecipeDuration } from '~/utils/afmDuration'

defineProps<{
  rows: DurationRow[]
  recipes: RecipeDuration[]
  selected: string | null
}>()
const emit = defineEmits<{ select: [key: string] }>()

const span = (seconds: number | null) => seconds === null ? '—' : formatDuration(seconds)
</script>
