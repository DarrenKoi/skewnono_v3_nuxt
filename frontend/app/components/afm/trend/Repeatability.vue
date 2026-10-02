<template>
  <AfmCard
    icon="i-lucide-repeat-2"
    title="재현성"
    :count="pairs.length"
  >
    <template #actions>
      <span class="sk-meta">같은 Sample ID 재측정</span>
    </template>
    <div class="flex flex-col gap-2">
      <div
        v-for="p in pairs"
        :key="`${p.recipe}:${p.sample}`"
        class="flex flex-col gap-1.5 rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3 py-2.5"
      >
        <span class="flex items-baseline justify-between gap-2">
          <span class="truncate font-mono text-xs font-semibold text-(--sk-ink)">{{ p.sample }}</span>
          <span class="shrink-0 sk-meta">{{ p.keys.length }}회 · {{ hoursLabel(p.hours) }}</span>
        </span>
        <span class="flex items-baseline gap-3.5">
          <span class="font-mono text-lg font-semibold tabular-nums text-(--sk-ink)">{{ fmt2(p.spread) }} nm</span>
          <span class="sk-meta">MEAN 간 차이{{ p.ratio === null ? '' : ` · wafer 내 σ̄의 ${p.ratio.toFixed(1)}배` }}</span>
        </span>
        <span
          v-if="p.ratio !== null"
          class="sk-meta"
        >{{ p.ratio < 1 ? '재측정 차이가 wafer 내 편차보다 작습니다. 장비 재현성은 문제가 아닙니다.' : '재측정 차이가 wafer 내 편차를 넘습니다. 팁·정렬을 먼저 봅니다.' }}</span>
      </div>
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
import type { RepeatPair } from '~/utils/afmTrend'

defineProps<{ pairs: RepeatPair[] }>()

const hoursLabel = (hours: number) => hours < 1 ? `${Math.round(hours * 60)}분 간격` : `${Math.round(hours)}시간 간격`
</script>
