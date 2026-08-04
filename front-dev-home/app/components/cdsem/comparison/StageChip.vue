<template>
  <span
    class="sk-badge tracking-wide ring-1"
    :class="[chipClass, { 'sk-badge-lg': large }]"
    :title="inferred ? 'stage 추출 실패 — EV cap 적용 중' : `stage: ${stage}`"
  >
    <span
      v-if="inferred"
      class="opacity-70"
    >?</span>
    <span v-else>{{ stage }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DevStage } from '~/utils/lotHealth'

const props = defineProps<{
  stage: DevStage
  inferred?: boolean
  /** 상세 헤더처럼 22px lot_cd 옆에 설 때. 카드 위에서는 기본 크기입니다. */
  large?: boolean
}>()

const chipClass = computed(() => {
  if (props.inferred) {
    return 'bg-zinc-100/70 text-(--sk-ink-muted) ring-zinc-200 dark:bg-zinc-800/70 dark:text-zinc-400 dark:ring-zinc-700'
  }
  switch (props.stage) {
    case 'EV':
      return 'bg-(--sk-brand-soft) text-(--sk-brand-ink) ring-(--sk-accent-border)'
    case 'TV':
      return 'bg-amber-100/80 text-amber-800 ring-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:ring-amber-800/50'
    case 'PV':
      return 'bg-emerald-100/70 text-emerald-800 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:ring-emerald-800/50'
    case 'Pool':
      return 'bg-sky-100/70 text-sky-800 ring-sky-200 dark:bg-sky-900/30 dark:text-sky-200 dark:ring-sky-800/50'
    default:
      return 'bg-zinc-100 text-(--sk-ink-muted) ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700'
  }
})
</script>
