<template>
  <section class="dashboard-surface flex h-full min-h-0 flex-col overflow-hidden rounded-(--sk-r-card)">
    <header class="border-b border-(--sk-border-soft) px-3 py-2.5">
      <p class="sk-eyebrow">
        RECENT ANALYSIS
      </p>
      <div class="mt-0.5 flex items-center justify-between gap-2">
        <div class="flex items-baseline gap-2">
          <h2 class="sk-title">
            최근 본 측정
          </h2>
          <span class="font-mono text-[10px] text-(--sk-ink-subtle)">{{ items.length }}</span>
        </div>
        <UButton
          v-if="items.length"
          color="neutral"
          variant="ghost"
          size="xs"
          label="전체 삭제"
          @click="emit('clear')"
        />
      </div>
      <p class="mt-1 sk-meta">
        단일 측정과 Time-Series 분석을 다시 엽니다.
      </p>
    </header>

    <p
      v-if="!items.length"
      class="px-4 py-10 text-center sk-body"
    >
      단일 측정 또는 Time-Series를 열면<br>최근 작업이 여기에 표시됩니다.
    </p>

    <div
      v-else
      class="min-h-0 flex-1 overflow-y-auto"
    >
      <div
        v-for="item in items"
        :key="item.id"
        class="group relative border-b border-(--sk-border-soft) px-3 py-3 last:border-0"
        :class="item.expired
          ? 'opacity-50'
          : 'cursor-pointer transition-colors hover:bg-(--sk-brand)/5'"
        @click="!item.expired && emit('open', item)"
      >
        <div class="flex items-start justify-between gap-2">
          <span
            class="rounded-(--sk-r-chip) px-1.5 py-0.5 font-mono text-[11px] font-semibold"
            :class="item.mode === 'time-series'
              ? 'bg-(--sk-brand-soft) text-(--sk-brand)'
              : 'bg-(--sk-chip-bg) text-(--sk-chip-text)'"
          >
            {{ item.mode === 'time-series' ? `Time-Series · ${item.measurements.length}` : '단일' }}
          </span>
          <button
            type="button"
            class="rounded p-0.5 text-(--sk-ink-subtle) opacity-0 transition group-hover:opacity-100 hover:bg-(--sk-bad)/10 hover:text-(--sk-bad)"
            aria-label="최근 항목 삭제"
            @click.stop="emit('remove', item.id)"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3.5 w-3.5"
            />
          </button>
        </div>
        <p class="mt-2 truncate font-mono text-[11px] font-semibold text-(--sk-ink)">
          {{ summarizeRecentValues(item.measurements.map(measurement => measurement.lot)) }}
        </p>
        <p class="mt-0.5 truncate font-mono text-[11px] text-(--sk-ink-muted)">
          {{ summarizeRecentValues(item.measurements.map(measurement => measurement.recipe)) }}
        </p>
        <p class="mt-0.5 truncate font-mono text-[11px] text-(--sk-ink-muted)">
          {{ summarizeRecentValues(item.measurements.map(measurement => measurement.eq)) }}
        </p>
        <div class="mt-2 flex items-center justify-between gap-2 font-mono text-[11px] text-(--sk-ink-subtle)">
          <span>{{ item.viewedAt.slice(0, 16).replace('T', ' ') }}</span>
          <span v-if="item.expired">보존 기간 만료</span>
          <span v-else-if="item.expiredCount">{{ item.expiredCount }}개 만료</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { SkewvoirRecentEntry } from '~/composables/useSkewvoirRecentlyViewed'
import { summarizeRecentValues } from '~/utils/skewvoirSearchUi'

defineProps<{
  items: SkewvoirRecentEntry[]
}>()

const emit = defineEmits<{
  open: [item: SkewvoirRecentEntry]
  remove: [id: string]
  clear: []
}>()
</script>
