<template>
  <AfmCard
    icon="i-lucide-git-fork"
    title="변동 분해"
  >
    <p
      v-if="!split"
      class="sk-body"
    >
      {{ mixed ? 'recipe가 섞인 그룹에서는 나누지 않습니다. 같은 컬럼명이 같은 측정량인지 확인되지 않았습니다.' : 'MEAN과 STDEV가 있는 측정이 2건 이상이어야 나눌 수 있습니다.' }}
    </p>
    <div
      v-else
      class="flex flex-col gap-3"
    >
      <div class="flex h-3.5 overflow-hidden rounded-full bg-(--sk-border-soft)">
        <div :style="{ width: `${split.lotPct}%`, background: SK_SCALE[0] }" />
        <div :style="{ width: `${100 - split.lotPct}%`, background: SK_SCALE[1] }" />
      </div>
      <div class="grid grid-cols-2 gap-2.5">
        <div class="flex flex-col gap-0.5 rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3.5 py-3">
          <span class="sk-label">lot 간 σ</span>
          <span class="font-mono text-xl font-semibold tabular-nums text-(--sk-ink)">{{ fmt2(split.lotSd) }}</span>
          <span class="sk-meta">MEAN들의 표준편차 · {{ split.lotPct }}%</span>
        </div>
        <div class="flex flex-col gap-0.5 rounded-(--sk-r-nav) bg-(--sk-muted-surface) px-3.5 py-3">
          <span class="sk-label">wafer 내 σ̄</span>
          <span class="font-mono text-xl font-semibold tabular-nums text-(--sk-ink)">{{ fmt2(split.waferSd) }}</span>
          <span class="sk-meta">측정별 STDEV의 평균 · {{ 100 - split.lotPct }}%</span>
        </div>
      </div>
      <p class="sk-meta leading-relaxed">
        {{ verdict }}
      </p>
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
import type { VarianceSplit } from '~/utils/afmTrend'
import { SK_SCALE } from '~/utils/chartPalette'

const props = defineProps<{
  split: VarianceSplit | null
  mixed: boolean
}>()

const verdict = computed(() => {
  const pct = props.split?.lotPct ?? 50
  if (pct >= 60) return 'lot 간 변동이 큽니다. 공정(앞 단계) 쪽을 먼저 봅니다.'
  if (pct <= 40) return 'wafer 안 변동이 큽니다. 포인트 패턴(02)과 recipe 위치를 먼저 봅니다.'
  return '두 변동이 비슷합니다. 01의 관리선 밖 측정부터 봅니다.'
})
</script>
